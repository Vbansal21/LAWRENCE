"""Bridge chat-ops tests (N-75 §2/§3a) — the regenerate/edit/head/branch/tree/note
handlers, driven for real against a live ChatStore.

The full DesktopBridge __init__ boots observers/model/UI, so we bind the REAL handler
methods onto a lightweight fake holding just the collaborators they touch (chats =
a real ChatStore, plus tiny stubs for memory/ctx/ui). No mocks of the logic under test;
the model-dependent ``turn`` is the only stub (it stands in for the LLM call and routes
back through the REAL ``_persist_turn`` so variant/edit storage is exercised end-to-end).
"""
import sys, tempfile, shutil, types, json
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
from lk.ctx.notes import NoteStore

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
class _MemRec(_Mem):
    """Records the B9b delete-penalty toggles so we can assert the wiring."""
    def __init__(self): self.deleted = set()
    def mark_deleted(self, nid): self.deleted.add(nid)
    def clear_deleted(self, nid): self.deleted.discard(nid)
class _Ctx:
    def __init__(self): self.appended = []
    def append(self, *, ts, kind, compact, detailed): self.appended.append((kind, detailed))

def fresh():
    tmp = Path(tempfile.mkdtemp())
    fake = types.SimpleNamespace(
        chats=ChatStore(mem_dir=tmp), notes=NoteStore(mem_dir=tmp),
        memory=_Mem(), ctx=_Ctx(), ui=_UI(),
        events=[], active_chat_id="", lock=None, _chat_ctx={})
    # bind the REAL pure helpers regenerate() depends on (class attr + bound methods)
    fake._REGEN_PRESETS = DB._REGEN_PRESETS
    fake._regen_directive = types.MethodType(DB._regen_directive, fake)
    fake._persist_turn = types.MethodType(DB._persist_turn, fake)
    fake._build_regen_turn = types.MethodType(DB._build_regen_turn, fake)
    fake._enrich_regen_result = types.MethodType(DB._enrich_regen_result, fake)
    fake._link_node = types.MethodType(DB._link_node, fake)        # B3: link endpoints
    fake._SUMMARY_PROMPT = DB._SUMMARY_PROMPT                       # B5: summarize→context
    fake._build_summary_turn = types.MethodType(DB._build_summary_turn, fake)
    fake._recall_suppress = types.MethodType(DB._recall_suppress, fake)  # B9b: delete-penalty wiring
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

# ───────────────────────── trash bin (N-81 B1) ─────────────────────────
section("trash bin — chat_trash / chat_purge / chat_empty_trash + index split")
tmp3, fk3 = fresh()
k = fk3.chats.create_chat("keep")["id"]
t = fk3.chats.create_chat("toss")["id"]
fk3.active_chat_id = t; fk3.chats.set_active(t)
res = DB.chat_trash(fk3, t)
check("chat_trash ok + reassigns active off the trashed chat", res["ok"] and fk3.active_chat_id != t)
idx = DB.chats_index(fk3)
check("index lists keep, hides trashed, surfaces it in trash",
      k in {c["id"] for c in idx["items"]} and t not in {c["id"] for c in idx["items"]}
      and t in {c["id"] for c in idx["trash"]})
check("chat_restore pulls it back to the list",
      DB.chat_restore(fk3, t)["ok"] and t in {c["id"] for c in DB.chats_index(fk3)["items"]})
DB.chat_trash(fk3, t)
check("chat_purge permanently removes from the bin",
      DB.chat_purge(fk3, t)["ok"] and t not in {c["id"] for c in DB.chats_index(fk3)["trash"]})
check("chat_trash unknown → 404", raises(lambda: DB.chat_trash(fk3, "ghost"), 404))
x = fk3.chats.create_chat("x")["id"]; DB.chat_trash(fk3, x)
check("chat_empty_trash empties the whole bin",
      DB.chat_empty_trash(fk3, {})["purged"] >= 1 and DB.chats_index(fk3)["trash"] == [])
shutil.rmtree(tmp3, ignore_errors=True)

# ───────────────────────── search (N-81 B2) ─────────────────────────
section("chat_search — query/scope/regex param handling")
tmp4, fk4 = fresh()
s1 = fk4.chats.create_chat("s1")["id"]
fk4.chats.append_message(s1, "user", "find the needle here")
s2 = fk4.chats.create_chat("s2")["id"]
fk4.chats.append_message(s2, "user", "another needle in s2")
fk4.active_chat_id = s1; fk4.chats.set_active(s1)
allhits = DB.chat_search(fk4, {"q": ["needle"], "scope": ["all"]})
check("scope=all searches every chat", allhits["count"] == 2 and allhits["ok"])
cur = DB.chat_search(fk4, {"q": ["needle"], "scope": ["current"]})
check("scope=current restricts to the active chat",
      cur["count"] == 1 and all(h["chatId"] == s1 for h in cur["hits"]))
byid = DB.chat_search(fk4, {"q": ["needle"], "scope": [s2]})
check("scope=<chatId> restricts to that chat", all(h["chatId"] == s2 for h in byid["hits"]))
rx = DB.chat_search(fk4, {"q": [r"need\w+"], "regex": ["1"]})
check("regex param honored", rx["regex"] is True and rx["count"] == 2)
check("empty query → zero hits, no error", DB.chat_search(fk4, {"q": [""]})["count"] == 0)
shutil.rmtree(tmp4, ignore_errors=True)

# ───────────────────────── link-at-message + backlinks (N-81 B3) ─────────────────────────
section("create_link / links_for — message↔chat, message↔note, idempotent, backlinks")
tmp5, fk5 = fresh()
a = fk5.chats.create_chat("a")["id"]
b = fk5.chats.create_chat("b")["id"]
qa = fk5.chats.append_message(a, "user", "question in a")            # id "a:1"
ra = fk5.chats.append_message(a, "assistant", "answer in a")         # id "a:2"
qb = fk5.chats.append_message(b, "user", "question in b")            # id "b:1"

# message → another chat's message (src given as {chatId,msgId}, dst as a raw node id)
lk1 = DB.create_link(fk5, {"src": {"chatId": a, "msgId": ra}, "dst": qb})
check("create_link normalizes src to a node id", lk1["src"] == ra and lk1["ok"])
check("create_link reports a freshly created edge", lk1["created"] is True)
check("create_link is idempotent (no dup edge)",
      DB.create_link(fk5, {"src": {"chatId": a, "msgId": ra}, "dst": qb})["created"] is False)

# message → note (dst as {noteId}); write_note returns the id string
note_id = fk5.notes.write_note("thought", "a thought") or "note-x"
DB.create_link(fk5, {"src": {"chatId": a, "msgId": ra}, "dst": {"noteId": note_id}})

# links_for on the source message: both peers surface as outgoing edges
nb = DB.links_for(fk5, a, ra)
peers = {e["peer"] for e in nb["edges"]}
check("links_for returns the node neighborhood", nb["ok"] and nb["node"] == ra)
check("links_for lists every outgoing peer", {qb, note_id} <= peers)
check("links_for marks direction out for source-side edges",
      all(e["dir"] == "out" for e in nb["edges"]))

# links_for on the TARGET message: the reverse edge appears as incoming (backlink)
nb_in = DB.links_for(fk5, b, qb)
check("links_for surfaces the reverse edge as incoming",
      ra in {e["peer"] for e in nb_in["edges"] if e["dir"] == "in"})

# guards
check("create_link missing dst → 400", raises(lambda: DB.create_link(fk5, {"src": {"chatId": a, "msgId": ra}}), 400))
check("create_link self-loop is not created",
      DB.create_link(fk5, {"src": ra, "dst": ra})["created"] is False)
shutil.rmtree(tmp5, ignore_errors=True)

# ───────────────────────── temporary chats (N-81 B4) ─────────────────────────
section("chat_create(ttl) / chat_set_ttl — temporary-chat timer through the bridge")
tmp6, fk6 = fresh()
# create a temporary chat via the bridge (ttlMinutes)
cr = DB.chat_create(fk6, {"title": "temp", "ttlMinutes": 45})
tc = cr["chat"]["id"]
check("chat_create with ttlMinutes makes an ephemeral chat",
      cr["chat"].get("ephemeral") is True and cr["chat"].get("ttl_minutes") == 45)
check("a plain chat_create stays permanent",
      not DB.chat_create(fk6, {"title": "plain"})["chat"].get("ephemeral"))
# set_ttl arms / clears via the bridge
on = DB.chat_set_ttl(fk6, tc, {"minutes": 10})
check("chat_set_ttl(minutes>0) keeps it temporary + re-arms expiry",
      on["chat"]["ephemeral"] is True and on["chat"]["ttl_minutes"] == 10 and on["chat"]["expires_at"])
off = DB.chat_set_ttl(fk6, tc, {"minutes": 0})
check("chat_set_ttl(0) makes it permanent", not off["chat"].get("ephemeral"))
check("chat_set_ttl unknown chat → 404", raises(lambda: DB.chat_set_ttl(fk6, "ghost", {"minutes": 5}), 404))
# chats_index sweeps expired temp chats into the trash
exp = DB.chat_create(fk6, {"title": "doomed", "ttlMinutes": 1})["chat"]["id"]
fk6.chats.set_ttl(exp, None)                                  # then back-date manually
rows = json.loads((tmp6 / "chats" / "index.json").read_text())
for r in rows:
    if r["id"] == exp:
        r.update({"ephemeral": True, "ttl_minutes": 1, "expires_at": "2000-01-01T00:00:00+00:00"})
(tmp6 / "chats" / "index.json").write_text(json.dumps(rows))
idx = DB.chats_index(fk6)
check("chats_index sweeps an expired temp chat out of the live list",
      exp not in {c["id"] for c in idx["items"]})
check("the swept chat shows up in the trash bin", exp in {c["id"] for c in idx["trash"]})
shutil.rmtree(tmp6, ignore_errors=True)

# ───────────────────────── summarize → context (N-81 B5) ─────────────────────────
section("summarize_chat — model turn (no-persist) → note + inline + cross-chat anchor")
tmp7, fk7 = fresh()
src = fk7.chats.create_chat("source")["id"]
fk7.chats.append_message(src, "user", "what is a B-tree?")
fk7.chats.append_message(src, "assistant", "A B-tree is a self-balancing search tree.")
dst = fk7.chats.create_chat("dest")["id"]
d1 = fk7.chats.append_message(dst, "user", "notes chat")
d2 = fk7.chats.append_message(dst, "assistant", "ok")          # leaf in dest

# a fake model turn: honors _noPersist (writes nothing), returns a summary, and
# records that it was asked NOT to persist + which chat it ran over.
seen = {}
def fake_turn(request):
    seen["req"] = request
    seen["active_during"] = fk7.active_chat_id
    if not request.get("_noPersist"):
        # if this ever fires, the no-persist contract is broken — make it visible
        DB._persist_turn(fk7, request["chatId"], "", "LEAK", "summarize", {})
    return {"answer": "SUMMARY: a B-tree is a balanced tree.", "controls": {}, "events": [],
            "chatId": request["chatId"]}
fk7.turn = fake_turn

# run with the active chat = dest, summarizing src → active must NOT flip to src
fk7.active_chat_id = dst; fk7.chats.set_active(dst)
src_before = len(fk7.chats.messages(src))
out = DB.summarize_chat(fk7, src, {"guidance": "keep it short",
                                   "target": {"chatId": dst, "msgId": d2}})

check("summarize returns ok + the summary text", out["ok"] and out["summary"].startswith("SUMMARY:"))
check("summarize ran with _noPersist set (no chat pollution from the turn)",
      seen["req"].get("_noPersist") is True)
check("summary turn carries retrieval off + guidance",
      seen["req"]["turn"]["config"].get("retrieval") is False and "keep it short" in seen["req"]["turn"]["text"])
check("summary prompt includes the source transcript",
      "B-tree" in seen["req"]["turn"]["text"])
# #12a durable note auto-linked back to the source chat
check("#12a writes a durable summary note", bool(out.get("noteId")))
check("#12a note is kind=summary", fk7.notes.read_note(out["noteId"])["kind"] == "summary")
check("#12a note auto-linked back into the source chat (chat node or its summary msg)",
      any(p == src or str(p).startswith(f"{src}:")
          for p in {e["peer"] for e in fk7.notes.edges_for(out["noteId"])}))
# #12b inline recap appended to the SOURCE chat
check("#12b appends one inline summary message to the source",
      len(fk7.chats.messages(src)) == src_before + 1)
inline = fk7.chats.get_by_id(src, out["messageId"])
check("#12b inline message is kind=summary", inline.get("kind") == "summary")
check("#12b inline message lands on the source's active path",
      out["messageId"] in {m["id"] for m in fk7.chats.path_messages(src)})
# #13 cross-chat anchored insert (dest leaf → inline)
check("#13 reports the insertion point", out["insertedAt"]["chatId"] == dst and out["insertedAt"]["anchor"] == d2)
ins_id = out["insertedAt"]["messageId"]
check("#13 inserts after the chosen anchor in dest",
      fk7.chats.parent_of(dst, ins_id) == d2)
check("#13 inserted block is kind=summary with fromChat",
      fk7.chats.get_by_id(dst, ins_id).get("kind") == "summary"
      and fk7.chats.get_by_id(dst, ins_id)["meta"]["fromChat"] == src)
# the no-pollution contract: the active chat is restored to dest, and no LEAK landed
check("active chat is NOT flipped to the summarized chat", fk7.active_chat_id == dst)
check("no LEAK message was persisted by the turn",
      "LEAK" not in [m["text"] for m in fk7.chats.messages(src)])

# guards
check("summarize unknown chat → 404", raises(lambda: DB.summarize_chat(fk7, "ghost", {}), 404))
empty = fk7.chats.create_chat("empty")["id"]
check("summarize empty chat → 400", raises(lambda: DB.summarize_chat(fk7, empty, {}), 400))
check("summarize with an unknown target anchor → 404",
      raises(lambda: DB.summarize_chat(fk7, src, {"target": {"chatId": dst, "msgId": "dest:99"}}), 404))
shutil.rmtree(tmp7, ignore_errors=True)

# ──────────────── backup / restore bundle (N-81 catalog #4) ───────────────────────
section("chat_backup + chat_restore_bundle — full backup, import, merge-conflict")
tmp8, fk8 = fresh()
a8 = fk8.chats.create_chat("alpha")["id"]
fk8.chats.append_message(a8, "user", "hi")
fk8.chats.append_message(a8, "assistant", "there")
b8 = fk8.chats.create_chat("beta")["id"]
fk8.chats.append_message(b8, "user", "solo")
fk8.active_chat_id = a8; fk8.chats.set_active(a8)

bk = DB.chat_backup(fk8)
check("chat_backup ok + counts every chat", bk["ok"] and bk["count"] == 2)
check("chat_backup wraps the lossless store bundle", bk["bundle"]["kind"] == "lawrence-chat-backup")

# restore into a fresh bridge → clean import
tmp9, fk9 = fresh()
fk9.active_chat_id = ""
rb = DB.chat_restore_bundle(fk9, {"bundle": bk["bundle"], "onConflict": "skip"})
check("restore imports both chats", rb["ok"] and set(rb["imported"]) == {a8, b8})
check("restore lands the UI on a valid active chat", fk9.chats.chat_meta(rb["active"]) is not None)
check("restored transcript round-trips", texts(fk9, a8) == ["hi", "there"])

# re-restore skip → no dups; rename → conflict copies; merge → union
check("restore skip leaves existing alone",
      set(DB.chat_restore_bundle(fk9, {"bundle": bk["bundle"]})["skipped"]) == {a8, b8})
ren = DB.chat_restore_bundle(fk9, {"bundle": bk["bundle"], "onConflict": "rename"})
check("restore rename re-imports conflicts under new ids", len(ren["renamed"]) == 2)
mrg = DB.chat_restore_bundle(fk9, {"bundle": bk["bundle"], "onConflict": "merge"})
check("restore merge dedups identical messages (0 added)",
      all(m["added"] == 0 and m["conflicts"] == 0 for m in mrg["merged"]))

# the bundle may be passed bare (no wrapper) too
bare = DB.chat_restore_bundle(fk9, bk["bundle"])
check("restore accepts a bare bundle (no wrapper key)", bare["ok"])

# guards
check("restore with no chats list → 400",
      raises(lambda: DB.chat_restore_bundle(fk9, {"bundle": {"nope": 1}}), 400))
check("restore with a bad onConflict → 400",
      raises(lambda: DB.chat_restore_bundle(fk9, {"bundle": bk["bundle"], "onConflict": "bogus"}), 400))
shutil.rmtree(tmp8, ignore_errors=True)
shutil.rmtree(tmp9, ignore_errors=True)

# ───────────────────────── B7 semantic search + B8 pins/bookmarks ─────────────────────────
section("chat_semantic_search + chat_pin + bookmarks — B7/B8 endpoints")
tmpA, fkA = fresh()
ca = fkA.chats.create_chat("alpha")["id"]
fkA.chats.append_message(ca, "user", "explain the retrieval ranker scoring")
ma = fkA.chats.append_message(ca, "assistant", "the ranker scores chunks with BM25")
cb = fkA.chats.create_chat("beta")["id"]
fkA.chats.append_message(cb, "user", "weather forecast for tomorrow")
fkA.active_chat_id = ca

# B7 — semantic search endpoint
ss = DB.chat_semantic_search(fkA, {"q": "ranker scoring"})
check("chat_semantic_search ok + semantic flag", ss["ok"] and ss["semantic"] is True)
check("semantic endpoint ranks alpha first", ss["hits"][0]["chatId"] == ca)
check("semantic scope=current restricts to active chat",
      all(h["chatId"] == ca for h in DB.chat_semantic_search(fkA, {"q": "ranker", "scope": "current"})["hits"]))
check("semantic empty query → no hits", DB.chat_semantic_search(fkA, {"q": ""})["count"] == 0)

# B8 — pin/favorite endpoint
pn = DB.chat_pin(fkA, cb, {"pinned": True})
check("chat_pin sets pinned", pn["ok"] and pn["pinned"] is True)
check("pinned chat floats to the top", [r["id"] for r in fkA.chats.list_chats()][0] == cb)
check("chat_pin off un-pins", DB.chat_pin(fkA, cb, {"pinned": False})["pinned"] is False)
check("chat_pin unknown chat → 404", raises(lambda: DB.chat_pin(fkA, "ghost", {}), 404))

# B8 — bookmark endpoints
ab = DB.chat_add_bookmark(fkA, {"chatId": ca, "messageId": ma, "note": "key line"})
check("chat_add_bookmark returns the bookmark", ab["ok"] and ab["bookmark"]["note"] == "key line")
check("chat_bookmarks lists it", DB.chat_bookmarks(fkA, {})["count"] == 1)
check("chat_bookmarks scopes by chat", DB.chat_bookmarks(fkA, {"chat": cb})["count"] == 0)
check("add bookmark needs ids → 400", raises(lambda: DB.chat_add_bookmark(fkA, {"chatId": ca}), 400))
check("bookmark unknown message → 404",
      raises(lambda: DB.chat_add_bookmark(fkA, {"chatId": ca, "messageId": "x:9"}), 404))
rb2 = DB.chat_remove_bookmark(fkA, {"chatId": ca, "messageId": ma})
check("chat_remove_bookmark drops it", rb2["removed"] and DB.chat_bookmarks(fkA, {})["count"] == 0)
shutil.rmtree(tmpA, ignore_errors=True)

# ───────────────────────── chat_promote (B9a: message → durable note) ─────────────────────────
section("chat_promote — promote a message into a durable note + link back-edge")
tmpP, fkP = fresh()
cp = fkP.chats.create_chat("recall")["id"]
fkP.chats.append_message(cp, "user", "what is the retrieval ranker?")
mp = fkP.chats.append_message(cp, "assistant", "it fuses lexical + vector + graph arms")
fkP.active_chat_id = cp
pr = DB.chat_promote(fkP, cp, {"messageId": mp})
check("chat_promote ok + returns a noteId", pr["ok"] and bool(pr["noteId"]))
note = fkP.notes.read_note(pr["noteId"])
check("promoted note is kind='excerpt'", note and note["kind"] == "excerpt")
check("note body carries the message text", "lexical + vector + graph" in note["body"])
check("note tagged promoted/chat-excerpt", set(["promoted", "chat-excerpt"]) <= set(note["tags"]))
edges = fkP.notes.edges_for(pr["noteId"])
check("back-edge links note ↔ message with kind='link'",
      any(e["peer"] == mp and e.get("kind") == "link" for e in edges))
check("linked message earns the +G boost (in _linked_nodes set)",
      mp in {x for e in fkP.notes._read_edges() if e.get("kind", "link") == "link"
             for x in (e.get("src"), e.get("dst"))})
pr2 = DB.chat_promote(fkP, cp, {"messageId": mp, "note": "core ranker fact"})
check("annotation is prepended to the note body",
      fkP.notes.read_note(pr2["noteId"])["body"].startswith("core ranker fact"))
check("promote without a messageId → 400", raises(lambda: DB.chat_promote(fkP, cp, {}), 400))
check("promote an unknown message → 404",
      raises(lambda: DB.chat_promote(fkP, cp, {"messageId": "x:9"}), 404))
me = fkP.chats.append_message(cp, "assistant", "   ")
check("promote an empty message → 422",
      raises(lambda: DB.chat_promote(fkP, cp, {"messageId": me}), 422))
shutil.rmtree(tmpP, ignore_errors=True)

# ───────────────────────── B9b: weighted relevance — delete penalty wiring ─────────────────────────
section("delete penalty (−P) — trash/restore/purge toggle MemoryIndex suppression")
tmpW, fkW = fresh()
fkW.memory = _MemRec()
cw = fkW.chats.create_chat("suppressme")["id"]
m1 = fkW.chats.append_message(cw, "user", "first")
m2 = fkW.chats.append_message(cw, "assistant", "second")
fkW.active_chat_id = cw
DB.chat_trash(fkW, cw)
check("trash suppresses the chat node + every message (−P)",
      {cw, m1, m2} <= fkW.memory.deleted)
DB.chat_restore(fkW, cw)
check("restore lifts the −P penalty (clear_deleted)",
      not ({cw, m1, m2} & fkW.memory.deleted))
# purge collects ids BEFORE the messages vanish
DB.chat_trash(fkW, cw)
fkW.memory.deleted.clear()
DB.chat_purge(fkW, cw)
check("purge suppresses ids before the hard delete", {cw, m1, m2} <= fkW.memory.deleted)
# hard delete on a fresh chat
cx = fkW.chats.create_chat("hardgone")["id"]
mx = fkW.chats.append_message(cx, "user", "doomed")
fkW.memory.deleted.clear()
DB.chat_delete(fkW, cx, {"hard": True})
check("hard delete suppresses the chat + its messages", {cx, mx} <= fkW.memory.deleted)
# graceful degrade: a memory without mark_deleted must not crash the op
fkW.memory = _Mem()
cz = fkW.chats.create_chat("nopenalty")["id"]
DB.chat_trash(fkW, cz)
check("trash still works when memory lacks mark_deleted (I4 degrade)",
      fkW.chats.chat_meta(cz) is not None)
shutil.rmtree(tmpW, ignore_errors=True)

# ───────────────────────── B9c: organization endpoints ─────────────────────────
section("chat_tags / chat_folder / chat_bulk + chats_index facets & filters")
tmpO, fkO = fresh()
ca = fkO.chats.create_chat("alpha")["id"]
cb = fkO.chats.create_chat("bravo")["id"]
cc = fkO.chats.create_chat("gamma")["id"]

# tags endpoint — set / add / remove
tg = DB.chat_tags(fkO, ca, {"tags": ["Work", "urgent"]})
check("chat_tags set returns the tag list", tg["ok"] and tg["tags"] == ["Work", "urgent"])
check("chat_tags add appends", "later" in DB.chat_tags(fkO, ca, {"add": "later"})["tags"])
check("chat_tags remove drops", "urgent" not in DB.chat_tags(fkO, ca, {"remove": "urgent"})["tags"])
check("chat_tags with no field → 400", raises(lambda: DB.chat_tags(fkO, ca, {}), 400))
check("chat_tags unknown chat → 404", raises(lambda: DB.chat_tags(fkO, "ghost", {"tags": []}), 404))

# folder endpoint — set / clear
fl = DB.chat_folder(fkO, ca, {"folder": "Projects"})
check("chat_folder files the chat", fl["ok"] and fl["folder"] == "Projects")
check("chat_folder '' unfiles", DB.chat_folder(fkO, ca, {"folder": ""})["folder"] == "")
check("chat_folder unknown chat → 404", raises(lambda: DB.chat_folder(fkO, "ghost", {"folder": "x"}), 404))

# index carries facets + honours filters/sort
DB.chat_tags(fkO, cb, {"tags": ["work"]})
DB.chat_folder(fkO, cb, {"folder": "Projects"})
idx = DB.chats_index(fkO)
check("chats_index exposes the tags facet", any(t["tag"].lower() == "work" for t in idx["tags"]))
check("chats_index exposes the folders facet", any(f["folder"] == "Projects" for f in idx["folders"]))
filtered = DB.chats_index(fkO, {"folder": ["Projects"]})
check("chats_index folder filter restricts items",
      {c["id"] for c in filtered["items"]} == {cb})
bytag = DB.chats_index(fkO, {"tag": ["work"]})
# both ca ("Work") and cb ("work") carry the tag case-insensitively; cc does not.
check("chats_index tag filter restricts items (case-insensitive)",
      {c["id"] for c in bytag["items"]} == {ca, cb})
titles = [c.get("title") for c in DB.chats_index(fkO, {"sort": ["title"]})["items"]]
check("chats_index sort=title is alphabetical", titles == sorted(titles, key=str.lower))

# bulk endpoint
bk = DB.chat_bulk(fkO, {"ids": [ca, cc], "op": "tag", "value": "batch"})
check("chat_bulk tag reports ok", bk["ok"] == [ca, cc] and not bk["failed"])
check("chat_bulk tag applied", "batch" in (fkO.chats.chat_meta(ca).get("tags") or []))
bk2 = DB.chat_bulk(fkO, {"ids": [ca, "ghost"], "op": "pin"})
check("chat_bulk reports per-id ok/failed", bk2["ok"] == [ca] and bk2["failed"] == ["ghost"])
check("chat_bulk empty ids → 400", raises(lambda: DB.chat_bulk(fkO, {"ids": [], "op": "pin"}), 400))
check("chat_bulk bad op → 400", raises(lambda: DB.chat_bulk(fkO, {"ids": [ca], "op": "frob"}), 400))
bk3 = DB.chat_bulk(fkO, {"ids": [cc], "op": "trash"})
check("chat_bulk trash moves to trash", cc in {c["id"] for c in DB.chats_index(fkO)["trash"]})
shutil.rmtree(tmpO, ignore_errors=True)

# ───────────────────────── summary ─────────────────────────
section("RESULT")
if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\n  ALL BRIDGE CHAT-OPS CHECKS PASSED")
