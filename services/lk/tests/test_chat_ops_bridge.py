"""Bridge chat-ops tests (N-75 §2/§3a) — the regenerate/edit/head/branch/tree/note
handlers, driven for real against a live ChatStore.

The full DesktopBridge __init__ boots observers/model/UI, so we bind the REAL handler
methods onto a lightweight fake holding just the collaborators they touch (chats =
a real ChatStore, plus tiny stubs for memory/ctx/ui). No mocks of the logic under test;
the model-dependent ``turn`` is the only stub (it stands in for the LLM call and routes
back through the REAL ``_persist_turn`` so variant/edit storage is exercised end-to-end).
"""
import sys, tempfile, shutil, types
sys.path.insert(0, "services")
sys.path.insert(0, "apps/desktop/scripts")
from pathlib import Path

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond: FAILS.append(name)
def section(t): print(f"\n=== {t} ===")

import importlib.util
spec = importlib.util.spec_from_file_location("ui_bridge", "apps/desktop/scripts/ui_bridge.py")
ub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ub)
from lk.ctx.chats import ChatStore

DB = ub.DesktopBridge
BridgeError = ub.BridgeError

def raises(fn, status=None):
    try:
        fn(); return False
    except BridgeError as e:
        return (status is None or e.status == status)
    except Exception:
        return False

class _UI:
    def push_context_event(self, *a, **k): pass
    def push_status(self, *a, **k): pass
    def push_delta(self, *a, **k): pass
class _Mem:
    def upsert(self, *a, **k): pass
class _Ctx:
    def __init__(self): self.appended = []
    def append(self, *, ts, kind, compact, detailed): self.appended.append((kind, detailed))

def fresh():
    tmp = Path(tempfile.mkdtemp())
    fake = types.SimpleNamespace(
        chats=ChatStore(mem_dir=tmp), memory=_Mem(), ctx=_Ctx(), ui=_UI(),
        events=[], active_chat_id="", lock=None)
    # bind the REAL pure helpers regenerate() depends on (class attr + bound methods)
    fake._REGEN_PRESETS = DB._REGEN_PRESETS
    fake._regen_directive = types.MethodType(DB._regen_directive, fake)
    fake._persist_turn = types.MethodType(DB._persist_turn, fake)
    return tmp, fake

def texts(fake, cid):
    return [m["text"] for m in fake.chats.path_messages(cid)]

# ───────────────────────── message_edit (user edit → diff) ─────────────────────────
section("message_edit — user edit appends an edit variant + diff")
tmp, fake = fresh()
cid = fake.chats.create_chat("ops")["id"]
q = fake.chats.append_message(cid, "user", "first question")
r = fake.chats.append_message(cid, "assistant", "first answer")
res = DB.message_edit(fake, cid, r, {"text": "first answer, corrected"})
check("edit returns ok + id + diff", res["ok"] and res["id"] and "@@" in res["diff"])
check("active path shows the edited text", texts(fake, cid)[-1] == "first answer, corrected")
check("original untouched in the log", fake.chats.get_by_id(cid, r)["text"] == "first answer")
check("edit on missing text → 400", raises(lambda: DB.message_edit(fake, cid, r, {}), 400))
check("edit on unknown id → 404", raises(lambda: DB.message_edit(fake, cid, "x:9", {"text": "y"}), 404))

# ───────────────────────── variant_head (switch) ─────────────────────────
section("variant_head — switch the active variant")
r2 = fake.chats.add_variant(cid, r, "assistant", "a totally different answer")
check("latest variant active before switch", texts(fake, cid)[-1] == "a totally different answer")
hres = DB.variant_head(fake, cid, {"parent_id": q, "child_id": r})
check("switch returns tree", hres["ok"] and "nodes" in hres["tree"])
check("active path follows the chosen variant", texts(fake, cid)[-1] == "first answer")
check("switch missing child → 400", raises(lambda: DB.variant_head(fake, cid, {"parent_id": q}), 400))
check("switch unknown child → 404", raises(lambda: DB.variant_head(fake, cid, {"child_id": "x:9"}), 404))

# ───────────────────────── chat_branch (kind-2 fork) ─────────────────────────
section("chat_branch — branch-off into a new chat")
bres = DB.chat_branch(fake, cid, {"at_message_id": r, "title": "branched"})
check("branch returns a new active chat", bres["ok"] and bres["active"] != cid)
check("active pointer moved to the new chat", fake.active_chat_id == bres["active"])
check("new chat holds the prefix up to r", texts(fake, bres["active"]) == ["first question", "first answer"])
check("branch missing at → 400", raises(lambda: DB.chat_branch(fake, cid, {}), 400))
check("branch off-path id → 404", raises(lambda: DB.chat_branch(fake, cid, {"at_message_id": "x:9"}), 404))

# ───────────────────────── chat_tree ─────────────────────────
section("chat_tree — minimap feed")
tr = DB.chat_tree(fake, cid)
check("tree lists all variants", {r, r2} <= {n["id"] for n in tr["nodes"]})
check("tree unknown chat → 404", raises(lambda: DB.chat_tree(fake, "ghost"), 404))

# ───────────────────────── chat_note (no-response input) ─────────────────────────
section("chat_note — no-response input → logs + journal, NO model turn")
n_before = len(fake.chats.path_messages(cid))
note = DB.chat_note(fake, cid, {"text": "remember to revisit the grounding pass"})
check("note ok + responded:false", note["ok"] and note["responded"] is False and note["messageId"])
check("note appended to transcript", len(fake.chats.path_messages(cid)) == n_before + 1)
check("note routed into ctx (logs/journal feed)", any(k == "note" for k, _ in fake.ctx.appended))
check("note marked noResponse in meta", fake.chats.get_by_id(cid, note["messageId"])["meta"]["noResponse"] is True)
check("empty note → 400", raises(lambda: DB.chat_note(fake, cid, {"text": "  "}), 400))

# ───────────────────────── regenerate (§3a) — shaping + persist ─────────────────────────
section("regenerate — op directive shaping + variant/edit persistence")
tmp2, fk2 = fresh()
cid2 = fk2.chats.create_chat("regen")["id"]
uq = fk2.chats.append_message(cid2, "user", "explain quicksort")
ar = fk2.chats.append_message(cid2, "assistant", "Quicksort partitions around a pivot.")

captured = {}
def fake_turn(request):
    # stand in for the LLM: record the shaped request, then drive the REAL persistence
    captured["req"] = request
    regen = request.get("_regen") or {}
    answer = "REGENERATED: " + request["turn"]["text"][:24]
    u, a = DB._persist_turn(fk2, request["chatId"], "", answer, "regenerate", regen)
    return {"answer": answer, "assistantMsgId": a, "chatId": request["chatId"], "controls": {}, "events": []}
fk2.turn = fake_turn

# informed → sibling variant (not edit)
out = DB.regenerate(fk2, cid2, {"message_id": ar, "op": "informed", "guidance": "add complexity analysis"})
check("informed carries guidance into the directive", "add complexity analysis" in captured["req"]["turn"]["text"])
check("informed reconstructs the originating query", captured["req"]["turn"]["text"].startswith("explain quicksort"))
check("informed is NOT an in-place edit", captured["req"]["_regen"]["as_edit"] is False)
check("informed appends a sibling of the response", fk2.chats.parent_of(cid2, out["assistantMsgId"]) == uq)
check("informed result echoes op", out["op"] == "informed")

# preset (shorter) → directive from preset table
DB.regenerate(fk2, cid2, {"message_id": ar, "op": "preset", "preset": "shorter"})
check("preset 'shorter' injects its template", "much shorter" in captured["req"]["turn"]["text"])

# preset extend with n → {n} substitution
DB.regenerate(fk2, cid2, {"message_id": ar, "op": "preset", "preset": "extend", "n": 3})
check("preset 'extend' substitutes n", "roughly 3 additional" in captured["req"]["turn"]["text"])

# selective → in-place edit (as_edit) carrying a diff
out2 = DB.regenerate(fk2, cid2, {"message_id": ar, "op": "selective", "section": "pivot"})
check("selective is an in-place edit", captured["req"]["_regen"]["as_edit"] is True)
check("selective scopes to the section", "«pivot»" in captured["req"]["turn"]["text"])
check("selective surfaces a diff for the inline view", "@@" in (out2.get("diff") or ""))
check("selective records editOf", out2.get("editOf") == ar)

# guards
check("regenerate missing message_id → 400", raises(lambda: DB.regenerate(fk2, cid2, {"op": "informed"}), 400))
check("regenerate unknown message → 404", raises(lambda: DB.regenerate(fk2, cid2, {"message_id": "x:9"}), 404))
check("regenerate of a USER message → 400", raises(lambda: DB.regenerate(fk2, cid2, {"message_id": uq}), 400))

shutil.rmtree(tmp, ignore_errors=True)
shutil.rmtree(tmp2, ignore_errors=True)

# ───────────────────────── summary ─────────────────────────
section("RESULT")
if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\n  ALL BRIDGE CHAT-OPS CHECKS PASSED")
