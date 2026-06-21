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
check("tree nodes carry summary + detail for the graph minimap (N-80 #1)",
      all("summary" in n and "detail" in n and n["summary"] for n in tr["nodes"]))
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

# ───────────────────────── G. trash bin (N-81 B1) ─────────────────────────
section("G — trash / restore / purge (soft-delete distinct from archive)")
tmp = Path(tempfile.mkdtemp())
cs = ChatStore(mem_dir=tmp)
a = cs.create_chat("keep")["id"]
b = cs.create_chat("toss")["id"]
cs.set_active(b)
check("both chats listed normally", {a, b} <= {c["id"] for c in cs.list_chats()})
check("trash_chat moves to the bin", cs.trash_chat(b) is True)
check("trashed chat leaves the normal list", b not in {c["id"] for c in cs.list_chats()})
check("trashed chat NOT counted as archived", b not in {c["id"] for c in cs.list_chats(include_archived=True)})
check("trashed chat appears in the trash view", b in {c["id"] for c in cs.list_trash()})
check("trashing the active chat clears the active pointer", cs.active_chat() != b)
check("restore brings it back out of trash", cs.restore_chat(b) is True and b in {c["id"] for c in cs.list_chats()})
check("restored chat no longer in trash", b not in {c["id"] for c in cs.list_trash()})
# archive is still its own state, and restore clears it too
cs.delete_chat(a, hard=False)
check("archive is distinct from trash", a in {c["id"] for c in cs.list_chats(include_archived=True)}
      and a not in {c["id"] for c in cs.list_trash()})
check("restore clears archived too", cs.restore_chat(a) and a in {c["id"] for c in cs.list_chats()})
# purge = permanent
cs.trash_chat(b)
check("purge_chat permanently removes", cs.purge_chat(b) is True
      and b not in {c["id"] for c in cs.list_chats(include_archived=True, include_trashed=True)})
check("purged chat dir is gone", not cs.chat_dir(b).exists())
# bulk empty-trash
c1 = cs.create_chat("t1")["id"]; c2 = cs.create_chat("t2")["id"]
cs.trash_chat(c1); cs.trash_chat(c2)
check("purge_trashed empties the whole bin", cs.purge_trashed() == 2 and cs.list_trash() == [])
shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────────── H. search (N-81 B2) ─────────────────────────
section("H — search across chats (text / regex / scope)")
tmp = Path(tempfile.mkdtemp())
cs = ChatStore(mem_dir=tmp)
c1 = cs.create_chat("alpha")["id"]
cs.append_message(c1, "user", "how does quicksort partition work")
cs.append_message(c1, "assistant", "It pivots around an element; O(n log n) average.")
c2 = cs.create_chat("beta")["id"]
cs.append_message(c2, "user", "explain mergesort stability")
hits = cs.search("quicksort")
check("substring search finds the message", len(hits) == 1 and hits[0]["chatId"] == c1)
check("hit carries chat + message + snippet", hits[0]["messageId"] and hits[0]["snippet"]
      and "quicksort" in hits[0]["snippet"].lower())
check("search is case-insensitive", len(cs.search("QUICKSORT")) == 1)
check("search spans multiple chats", len(cs.search("sort")) >= 2)
check("scope to one chat restricts results", all(h["chatId"] == c2 for h in cs.search("sort", chat_id=c2)))
check("regex search works", len(cs.search(r"merge\w+", regex=True)) == 1)
check("bad regex never raises (returns [])", cs.search("(", regex=True) == [])
check("empty query → no hits", cs.search("   ") == [])
# trashed chats excluded by default, archived included
cs.trash_chat(c2)
check("trashed chat excluded from search", cs.search("mergesort") == [])
check("trashed chat included when asked", len(cs.search("mergesort", include_trashed=True)) == 1)
shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────────── I — temporary chats (N-81 B4) ─────────────────────────
section("I — temporary chats: ttl timer + sweep_expired → trash")
import json as _json
tmp = Path(tempfile.mkdtemp())
cs = ChatStore(mem_dir=tmp)

# create with a ttl ⇒ ephemeral + a future expires_at
tmpc = cs.create_chat("temp", ttl_minutes=30)["id"]
meta = cs.chat_meta(tmpc)
check("create_chat(ttl_minutes) marks the chat ephemeral", meta.get("ephemeral") is True)
check("ephemeral chat carries ttl_minutes + expires_at", meta.get("ttl_minutes") == 30 and meta.get("expires_at"))

# a normal chat is permanent
perm = cs.create_chat("perm")["id"]
check("a chat without ttl is permanent", not cs.chat_meta(perm).get("ephemeral"))

# set_ttl arms a permanent chat; sweep does not touch a not-yet-expired chat
cs.set_ttl(perm, 15)
check("set_ttl(>0) makes a chat temporary", cs.chat_meta(perm).get("ephemeral") is True)
check("sweep leaves a not-yet-expired chat alone", cs.sweep_expired() == [])
check("still listed (not trashed) before expiry", perm in {c["id"] for c in cs.list_chats()})

# set_ttl(off) clears the timer entirely
cs.set_ttl(perm, None)
check("set_ttl(None) clears ephemeral/ttl/expires_at",
      not cs.chat_meta(perm).get("ephemeral") and "expires_at" not in cs.chat_meta(perm))

# force expiry by back-dating expires_at, then sweep → it lands in the trash
rows = _json.loads((tmp / "chats" / "index.json").read_text())
for r in rows:
    if r["id"] == tmpc:
        r["expires_at"] = "2000-01-01T00:00:00+00:00"
(tmp / "chats" / "index.json").write_text(_json.dumps(rows))
cs.set_active(tmpc)
expired = cs.sweep_expired()
check("sweep_expired retires the past-due chat", expired == [tmpc])
check("expired chat is now in the trash bin", tmpc in {c["id"] for c in cs.list_trash()})
check("expired chat dropped from the live list", tmpc not in {c["id"] for c in cs.list_chats()})
check("active pointer cleared when the active chat expired", cs.active_chat() != tmpc)
check("a swept chat is restorable (expiry → trash is reversible)",
      cs.restore_chat(tmpc) and tmpc in {c["id"] for c in cs.list_chats()})
check("set_ttl on an unknown chat → None", cs.set_ttl("ghost", 5) is None)
shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────── J — insert_after / summary anchor (N-81 B5) ───────────────
section("J — insert_after: leaf inline vs mid-path branch (summary anchor)")
tmp = Path(tempfile.mkdtemp())
cs = ChatStore(mem_dir=tmp)
cid = cs.create_chat("dest")["id"]
m1 = cs.append_message(cid, "user", "first")
m2 = cs.append_message(cid, "assistant", "second")
m3 = cs.append_message(cid, "user", "third")          # m3 is the leaf

# inserting after the leaf extends the active path inline
ins_leaf = cs.insert_after(cid, m3, "assistant", "SUMMARY-LEAF", kind="summary")
path_ids = [m["id"] for m in cs.path_messages(cid)]
check("insert_after a leaf returns a new id", bool(ins_leaf))
check("leaf insert lands inline on the active path", path_ids[-1] == ins_leaf)
check("leaf insert carries kind=summary",
      cs.get_by_id(cid, ins_leaf).get("kind") == "summary")

# inserting after a MID-path node must NOT hijack the existing path (sibling branch)
ins_mid = cs.insert_after(cid, m1, "assistant", "SUMMARY-MID", kind="summary",
                          meta={"summary": True, "fromChat": "src"})
path_after = [m["id"] for m in cs.path_messages(cid)]
check("mid-path insert returns a new id", bool(ins_mid))
check("mid-path insert does NOT disrupt the active path", ins_mid not in path_after)
check("mid-path insert keeps the original continuation", m2 in path_after and m3 in path_after)
check("mid-path insert is reachable as a node in the tree",
      ins_mid in {n["id"] for n in cs.tree(cid)["nodes"]})
check("mid-path insert is parented on the chosen anchor",
      cs.parent_of(cid, ins_mid) == m1)
check("insert_after preserves meta", cs.get_by_id(cid, ins_mid).get("meta", {}).get("fromChat") == "src")
check("insert_after an unknown anchor → None", cs.insert_after(cid, "ghost:9", "assistant", "x") is None)

# set_head=False path leaves head untouched for the original child slot
check("append_message(set_head=False) does not repoint head",
      cs.append_message(cid, "assistant", "branchx", parent=m1, set_head=False) not in
      [m["id"] for m in cs.path_messages(cid)])
shutil.rmtree(tmp, ignore_errors=True)

# ──────────────── K — backup_all / restore_bundle (N-81 catalog #4) ───────────────
section("K — full backup → restore (import + merge-conflict resolution)")
src = Path(tempfile.mkdtemp())
cs = ChatStore(mem_dir=src)
a = cs.create_chat("alpha")["id"]
am1 = cs.append_message(a, "user", "hello")
am2 = cs.append_message(a, "assistant", "world")
b = cs.create_chat("beta")["id"]
bm1 = cs.append_message(b, "user", "only in beta")
cs.set_active(a)
bundle = cs.backup_all()
check("backup is the right kind/version", bundle["kind"] == "lawrence-chat-backup" and bundle["version"] == 1)
check("backup records every chat", bundle["count"] == 2)
check("backup carries the full event log", len(bundle["chats"][0]["messages"]) >= 1)
check("backup captures the active pointer", bundle["active"] == a)
check("backup includes the head cursor per chat", all("head" in c for c in bundle["chats"]))

# 1) restore into an EMPTY workspace → clean, lossless, id-preserving import
dst = Path(tempfile.mkdtemp())
cd = ChatStore(mem_dir=dst)
rep = cd.restore_bundle(bundle, on_conflict="skip")
check("restore into empty workspace imports every chat", set(rep["imported"]) == {a, b})
check("imported chat ids are preserved verbatim", cd.chat_meta(a) is not None)
check("imported transcript round-trips exactly",
      [m["id"] for m in cd.messages(a)] == [am1, am2])
check("imported titles survive", cd.chat_meta(a).get("title") == "alpha")
check("imported message text survives", cd.get_by_id(a, am2).get("text") == "world")

# 2) re-restore with on_conflict="skip" → existing chats untouched
rep2 = cd.restore_bundle(bundle, on_conflict="skip")
check("skip leaves existing chats alone", set(rep2["skipped"]) == {a, b} and not rep2["imported"])
check("skip did not duplicate messages", len(cd.messages(a)) == 2)

# 3) on_conflict="rename" → conflicting chats imported as fresh, internally-consistent copies
rep3 = cd.restore_bundle(bundle, on_conflict="rename")
check("rename re-imports conflicts under new ids", len(rep3["renamed"]) == 2)
new_a = next(r["to"] for r in rep3["renamed"] if r["from"] == a)
check("renamed copy is a distinct chat", new_a != a and cd.chat_meta(new_a) is not None)
copy_msgs = cd.messages(new_a)
check("renamed copy re-ids messages to the new chat",
      all(str(m["id"]).startswith(f"{new_a}:") for m in copy_msgs))
check("renamed copy keeps internal parent links consistent",
      all((m.get("parent") is None) or str(m["parent"]).startswith(f"{new_a}:") for m in copy_msgs))
check("renamed copy preserves message text", copy_msgs[1].get("text") == "world")

# 4) on_conflict="merge" → union new content; identical messages deduped; conflicts kept
dst2 = Path(tempfile.mkdtemp())
cm = ChatStore(mem_dir=dst2)
cm.restore_bundle(bundle, on_conflict="skip")          # seed with alpha+beta
# build a mutated bundle: alpha gains a new message; am2's text changes (a conflict)
mut = json.loads(json.dumps(bundle))
for entry in mut["chats"]:
    if entry["meta"]["id"] == a:
        for m in entry["messages"]:
            if m["id"] == am2:
                m["text"] = "CHANGED"                   # same id, different text → conflict
        entry["messages"].append({
            "seq": 3, "id": f"{a}:3", "role": "user", "text": "fresh tail",
            "ts": "2026-06-21T00:00:00+00:00", "parent": am2, "kind": "turn"})
repm = cm.restore_bundle(mut, on_conflict="merge")
merged = next(x for x in repm["merged"] if x["id"] == a)
check("merge reports added messages", merged["added"] == 2)       # CHANGED-variant + fresh tail
check("merge flags the same-id/different-text conflict", merged["conflicts"] == 1)
texts = [m.get("text") for m in cm.messages(a)]
check("merge keeps BOTH the original and the conflicting text", "world" in texts and "CHANGED" in texts)
check("merge adds the genuinely-new message", "fresh tail" in texts)
check("merge is non-destructive to the active path (head unchanged)",
      [m["id"] for m in cm.path_messages(a)] == [am1, am2])

# 5) guards
try:
    cm.restore_bundle({"chats": []}, on_conflict="bogus"); _bad = False
except ValueError:
    _bad = True
check("restore rejects a bad on_conflict policy", _bad)
try:
    cm.restore_bundle({"nope": 1}); _bad2 = False
except ValueError:
    _bad2 = True
check("restore rejects a bundle with no chats list", _bad2)
for d in (src, dst, dst2):
    shutil.rmtree(d, ignore_errors=True)

# ───────────────────────── L. B7 semantic search + B8 pins/bookmarks ─────────────────────────
section("L — B7 semantic search (ranked, FTS5/BM25) + B8 pins/bookmarks")
lt = Path(tempfile.mkdtemp())
ls = ChatStore(mem_dir=lt)
c1 = ls.create_chat("kernel notes")["id"]
ls.append_message(c1, "user", "how does the retrieval ranker score documents")
m_rank = ls.append_message(c1, "assistant", "ranking blends BM25 with vector similarity scores")
c2 = ls.create_chat("cooking")["id"]
ls.append_message(c2, "user", "best way to bake sourdough bread at home")

# B7 — semantic search
hits = ls.semantic_search("ranking documents")
check("semantic search returns ranked hits", bool(hits))
check("semantic hit carries a score field", "score" in hits[0])
check("semantic ranks the relevant chat first", hits[0]["chatId"] == c1)
# morphology: 'scoring' should still hit 'score'/'scores' via porter stemming (vs B2 substring)
stem = ls.semantic_search("scoring")
exact = ls.search("scoring")   # B2 substring finds nothing ('scoring' not a literal substring)
check("semantic (porter) matches a morphological variant B2 misses",
      bool(stem) and not exact)
check("empty query → no semantic hits", ls.semantic_search("") == [])
check("semantic scope to one chat restricts results",
      all(h["chatId"] == c2 for h in ls.semantic_search("bread", chat_id=c2)))

# B8 — pin / favorite
upd_before = ls.chat_meta(c2).get("updated")
ls.pin_chat(c2, True)
ordered = [r["id"] for r in ls.list_chats()]
check("pinning floats a chat to the top of the listing", ordered[0] == c2)
check("pin meta flag is set", ls.chat_meta(c2).get("pinned") is True)
check("pin does NOT bump updated (org action, not edit)",
      ls.chat_meta(c2).get("updated") == upd_before)
ls.pin_chat(c2, False)
check("un-pin clears the flag", "pinned" not in ls.chat_meta(c2))
check("pin an unknown chat → None", ls.pin_chat("ghost", True) is None)

# B8 — message bookmarks
bm = ls.add_bookmark(c1, m_rank, note="key ranking line")
check("bookmark a real message returns the bookmark", bm is not None)
check("bookmark stores the note (a pinned snippet)", bm["note"] == "key ranking line")
check("bookmark a missing message → None", ls.add_bookmark(c1, f"{c1}:999") is None)
ls.add_bookmark(c1, m_rank, note="updated note")
allbm = ls.list_bookmarks()
check("re-bookmarking is idempotent (updates, not duplicates)", len(allbm) == 1)
check("re-bookmark updated the note", allbm[0]["note"] == "updated note")
check("list_bookmarks scoped to a chat", ls.list_bookmarks(chat_id=c2) == [])
check("remove_bookmark drops it", ls.remove_bookmark(c1, m_rank) and ls.list_bookmarks() == [])
check("remove a non-existent bookmark → False", ls.remove_bookmark(c1, m_rank) is False)
# hard-delete cleans up dangling bookmarks
ls.add_bookmark(c1, m_rank)
ls.delete_chat(c1, hard=True)
check("hard-deleting a chat removes its bookmarks", ls.list_bookmarks() == [])
shutil.rmtree(lt, ignore_errors=True)

# ─────────────── M. organization: tags + folders + sort + bulk (N-81 B9c) ───────────────
section("M — B9c organization (tags / folders / sort / bulk)")
mt = Path(tempfile.mkdtemp())
ms = ChatStore(mem_dir=mt)
a = ms.create_chat("alpha")["id"]
b = ms.create_chat("bravo")["id"]
g = ms.create_chat("gamma")["id"]

# tags
ms.set_tags(a, ["Work", "urgent"])
check("set_tags stores normalised tags", ms.chat_meta(a).get("tags") == ["Work", "urgent"])
ms.add_tag(a, "WORK")            # case-insensitive de-dupe, first casing kept
check("add_tag is idempotent (case-insensitive)", ms.chat_meta(a).get("tags") == ["Work", "urgent"])
ms.add_tag(a, "later")
check("add_tag appends a new tag", "later" in ms.chat_meta(a).get("tags"))
ms.remove_tag(a, "URGENT")       # case-insensitive removal
check("remove_tag drops a tag (case-insensitive)", "urgent" not in [t.lower() for t in ms.chat_meta(a).get("tags")])
ms.set_tags(b, ["work"])
facets = {f["tag"].lower(): f["count"] for f in ms.all_tags()}
check("all_tags counts work across chats (case-insensitive)", facets.get("work") == 2)
ms.set_tags(a, [])
check("set_tags([]) clears the field", "tags" not in ms.chat_meta(a))

# org actions do not bump updated
ms.set_tags(b, ["work"])
upd = ms.chat_meta(b).get("updated")
ms.add_tag(b, "keep")
check("tagging does NOT bump updated (org action)", ms.chat_meta(b).get("updated") == upd)

# folders
ms.set_folder(a, "Projects")
ms.set_folder(b, "Projects")
check("set_folder files a chat", ms.chat_meta(a).get("folder") == "Projects")
infolder = {r["id"] for r in ms.list_chats(folder="Projects")}
check("list_chats(folder=) filters to that folder", infolder == {a, b})
unfiled = {r["id"] for r in ms.list_chats(folder="none")}
check("list_chats(folder='none') returns the unfiled chats", g in unfiled and a not in unfiled)
fols = {f["folder"]: f["count"] for f in ms.all_folders()}
check("all_folders counts members", fols.get("Projects") == 2)
ms.set_folder(a, "")
check("set_folder('') unfiles the chat", "folder" not in ms.chat_meta(a))

# tag filter
ms.set_tags(g, ["work"])
bytag = {r["id"] for r in ms.list_chats(tag="work")}
check("list_chats(tag=) filters by tag", bytag == {b, g})

# sort
import time as _t
# title sort is alphabetical regardless of recency
titles = [r.get("title") for r in ms.list_chats(sort="title")]
check("sort=title is alphabetical", titles == sorted(titles, key=str.lower))
# messages sort: give 'a' more messages, it should lead (no pins set)
ms.append_message(a, "user", "one"); ms.append_message(a, "assistant", "two")
top_msgs = ms.list_chats(sort="messages")[0]["id"]
check("sort=messages puts the busiest chat first", top_msgs == a)
# pinned always floats regardless of sort key
ms.pin_chat(g, True)
check("pinned floats to top even under sort=messages", ms.list_chats(sort="messages")[0]["id"] == g)
ms.pin_chat(g, False)

# bulk ops
res = ms.bulk([a, b], "tag", value="batch")
check("bulk tag reports all ok", res["ok"] == [a, b] and not res["failed"])
check("bulk tag actually applied", "batch" in (ms.chat_meta(a).get("tags") or []))
res = ms.bulk([a, "ghost"], "pin")
check("bulk pin succeeds for real, fails for unknown", res["ok"] == [a] and res["failed"] == ["ghost"])
res = ms.bulk([a, b], "folder", value="Archive2026")
check("bulk folder files all", ms.chat_meta(b).get("folder") == "Archive2026")
res = ms.bulk([b], "trash")
check("bulk trash moves to trash", b in {c["id"] for c in ms.list_trash()})
try:
    ms.bulk([a], "frobnicate")
    check("bulk rejects an unknown op", False)
except ValueError:
    check("bulk rejects an unknown op", True)
shutil.rmtree(mt, ignore_errors=True)

# ───────────────────────── summary ─────────────────────────
section("RESULT")
if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\n  ALL CHATSTORE DAG CHECKS PASSED")
