"""ChatStore DAG tests (Phase-1 branching/edit — N-75 / P5-lite).

Proves the tree layered over the append-only event log, with NO mocks:

  A. REGEN siblings   — regenerating an assistant response appends a SIBLING (same
     parent), the new variant becomes active, and the old one stays browsable;
  B. HEAD switch      — set_head flips which variant is on the active path (no append);
  C. EDIT→diff        — edit_message appends an `edit` sibling carrying a real unified
     diff and never mutates the original line;
  D. BRANCH-OFF       — fork_chat seeds a NEW chat with the active-path prefix only;
  E. TREE             — tree() exposes every variant + the active path + head;
  F. LEGACY back-compat — a pre-DAG messages.jsonl (no parent/head) still walks linearly
     and exports unchanged.

Offline, stdlib-only, no model/server/DB.
"""
import sys, json, tempfile, shutil
sys.path.insert(0, "services")
from pathlib import Path

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond: FAILS.append(name)
def section(t): print(f"\n=== {t} ===")

from lk.ctx.chats import ChatStore

def texts(store, cid):
    return [m["text"] for m in store.path_messages(cid)]

# ───────────────────────── A. regenerate = sibling, active ─────────────────────────
section("A — regenerate appends a browsable sibling")
tmp = Path(tempfile.mkdtemp())
cs = ChatStore(mem_dir=tmp)
cid = cs.create_chat("branching")["id"]
q   = cs.append_message(cid, "user", "q1")
r1  = cs.append_message(cid, "assistant", "r1")
check("baseline path is q1→r1", texts(cs, cid) == ["q1", "r1"])
r2  = cs.add_variant(cid, r1, "assistant", "r2")
check("regen returns a new id", bool(r2) and r2 != r1)
check("log keeps BOTH variants (append-only)", {m["id"] for m in cs.messages(cid)} >= {r1, r2})
check("active path now shows the new variant r2", texts(cs, cid) == ["q1", "r2"])
check("r1 and r2 are siblings (same parent = q)",
      cs.parent_of(cid, r1) == q and cs.parent_of(cid, r2) == q)
r3  = cs.add_variant(cid, r2, "assistant", "r3")
check("third regen, all three siblings of q", cs.parent_of(cid, r3) == q)
check("latest variant active by default", texts(cs, cid) == ["q1", "r3"])
check("add_variant on unknown id is None", cs.add_variant(cid, "nope:9", "assistant", "x") is None)

# ───────────────────────── B. head switch (no append) ─────────────────────────
section("B — set_head flips the active variant")
n_before = len(cs.messages(cid))
check("set_head to r1 ok", cs.set_head(cid, q, r1) is True)
check("path follows the selected variant r1", texts(cs, cid) == ["q1", "r1"])
check("switching did NOT append", len(cs.messages(cid)) == n_before)
check("set_head with unknown child is False", cs.set_head(cid, q, "nope:9") is False)
cs.set_head(cid, q, r3)  # restore latest

# ───────────────────────── C. edit → diff ─────────────────────────
section("C — edit_message appends an edit sibling with a real diff")
res = cs.edit_message(cid, r3, "r3 edited line\nplus a new line")
check("edit returns id + diff + edit_of", res and res["id"] and res["edit_of"] == r3)
check("diff is a real unified diff", "@@" in res["diff"] and "+r3 edited line" in res["diff"])
edited = cs.get_by_id(cid, res["id"])
check("edit node records edit_of + stored diff", edited.get("edit_of") == r3 and edited.get("diff"))
check("original r3 text is untouched (no mutation)", cs.get_by_id(cid, r3)["text"] == "r3")
check("active path now shows the edited text", texts(cs, cid)[-1].startswith("r3 edited line"))
check("edit of unknown id is None", cs.edit_message(cid, "nope:9", "x") is None)

# ───────────────────────── D. branch-off into a new chat ─────────────────────────
section("D — fork_chat seeds a new chat with the path prefix")
# build a longer path on a fresh chat
cid2 = cs.create_chat("forkable")["id"]
a = cs.append_message(cid2, "user", "A")
b = cs.append_message(cid2, "assistant", "B")
c = cs.append_message(cid2, "user", "C")
d = cs.append_message(cid2, "assistant", "D")
new = cs.fork_chat(cid2, b, title="from B")
check("fork returns a new chat meta", new and new["id"] != cid2)
check("fork copies prefix up to & incl. B only", texts(cs, new["id"]) == ["A", "B"])
check("forked messages are branch-seed", all(m.get("kind") == "branch-seed" for m in cs.path_messages(new["id"])))
check("source chat is unchanged", texts(cs, cid2) == ["A", "B", "C", "D"])
check("fork at off-path id is None", cs.fork_chat(cid2, "nope:9") is None)

# ───────────────────────── E. tree view for the minimap ─────────────────────────
section("E — tree() exposes variants + active path + head")
tr = cs.tree(cid)
node_ids = {n["id"] for n in tr["nodes"]}
check("tree lists every variant", {r1, r2, r3} <= node_ids)
check("tree carries the active path", tr["path"] == [m["id"] for m in cs.path_messages(cid)])
check("tree exposes head selections", isinstance(tr["head"], dict) and tr["head"])
check("tree nodes carry kind + parent + snippet",
      all("kind" in n and "parent" in n and "snippet" in n for n in tr["nodes"]))
shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────────── F. legacy (pre-DAG) back-compat ─────────────────────────
section("F — legacy flat messages.jsonl walks linearly")
tmp = Path(tempfile.mkdtemp())
cs = ChatStore(mem_dir=tmp)
cid = cs.create_chat("legacy")["id"]
# hand-write a PRE-DAG transcript: no parent/kind fields, no head.json
mpath = cs.chat_dir(cid) / "messages.jsonl"
legacy = [
    {"seq": 1, "id": f"{cid}:1", "role": "user", "text": "old q", "ts": "t1"},
    {"seq": 2, "id": f"{cid}:2", "role": "assistant", "text": "old a", "ts": "t2"},
    {"seq": 3, "id": f"{cid}:3", "role": "user", "text": "old q2", "ts": "t3"},
]
mpath.write_text("".join(json.dumps(r) + "\n" for r in legacy), encoding="utf-8")
check("legacy path walks in seq order", texts(cs, cid) == ["old q", "old a", "old q2"])
check("legacy export still renders", "old q2" in cs.export_chat(cid))
# a NEW append onto a legacy chat chains cleanly to the legacy leaf
nid = cs.append_message(cid, "assistant", "new a2")
check("append onto legacy chains to the leaf", texts(cs, cid) == ["old q", "old a", "old q2", "new a2"])
check("new node parent is the legacy leaf", cs.parent_of(cid, nid) == f"{cid}:3")
shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────────── summary ─────────────────────────
section("RESULT")
if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\n  ALL CHATSTORE DAG CHECKS PASSED")
