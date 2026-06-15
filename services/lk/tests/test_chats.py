"""Chat/session store tests (WS-U Track 1) — first-class, addressable chats.

Proves: chat CRUD round-trip (create/list/rename/archive/hard-delete); durable
transcript append with stable ids ``<chatId>:<seq>`` + auto-title; active-chat
pointer survives a fresh store (restart); ensure_default() degrades to a single
'scratch' chat when the workspace is empty; export renders browseable MDX. Then
Track 2: the NoteStore edge graph — a message↔message edge is bidirectional,
idempotent, survives reload, and composes with the note graph. Offline,
stdlib-only, no model/server/DB.
"""
import sys, tempfile, shutil
sys.path.insert(0, "services")
from pathlib import Path

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond: FAILS.append(name)
def section(t): print(f"\n=== {t} ===")

from lk.ctx.chats import ChatStore
from lk.ctx import NoteStore

# ───────────────────────── chat CRUD round-trip ─────────────────────────
section("chat CRUD round-trip")
tmp = Path(tempfile.mkdtemp())
cs = ChatStore(mem_dir=tmp)
check("empty workspace lists nothing", cs.list_chats() == [])
a = cs.create_chat("Build the bridge")
check("create returns id + title", bool(a["id"]) and a["title"] == "Build the bridge")
b = cs.create_chat()
check("untitled chat allowed", b["title"] == "")
check("list shows both", len(cs.list_chats()) == 2)
check("rename works", cs.rename_chat(b["id"], "Second thread") and cs.chat_meta(b["id"])["title"] == "Second thread")
check("archive hides from default list", cs.delete_chat(b["id"]) and len(cs.list_chats()) == 1)
check("archived still visible with flag", any(r["id"] == b["id"] for r in cs.list_chats(include_archived=True)))
check("hard delete removes dir", cs.delete_chat(b["id"], hard=True) and not cs.chat_dir(b["id"]).exists())
check("unknown chat rename is False", cs.rename_chat("nope", "x") is False)

# ───────────────────────── durable transcript + stable ids ─────────────────────────
section("durable transcript + addressable message ids")
m1 = cs.append_message(a["id"], "user", "How do per-chat memories work?")
m2 = cs.append_message(a["id"], "assistant", "Short-term is per-chat; long-term is shared.")
check("message id is <chatId>:<seq>", m1 == f"{a['id']}:1" and m2 == f"{a['id']}:2")
msgs = cs.messages(a["id"])
check("both messages persisted in order", [m["text"][:3] for m in msgs] == ["How", "Sho"])
check("count tracked in registry", cs.chat_meta(a["id"])["messages"] == 2)
check("get_message by seq", cs.get_message(a["id"], 1)["id"] == m1)
check("get_message bad seq is None", cs.get_message(a["id"], 99) is None)

# auto-title: a fresh untitled chat takes its title from the first user message
c = cs.create_chat()
cs.append_message(c["id"], "user", "Investigate the launcher shutdown bug please")
check("auto-title from first user message", cs.chat_meta(c["id"])["title"].startswith("Investigate the launcher"))

# ───────────────────────── active pointer survives restart ─────────────────────────
section("active-chat pointer survives a fresh store")
check("set_active works", cs.set_active(a["id"]) and cs.active_chat() == a["id"])
check("set_active rejects unknown id", cs.set_active("ghost") is False)
cs2 = ChatStore(mem_dir=tmp)              # simulate a process restart
check("active id persists across restart", cs2.active_chat() == a["id"])

# ───────────────────────── ensure_default (degraded path) ─────────────────────────
section("ensure_default — single 'scratch' chat when empty")
tmp2 = Path(tempfile.mkdtemp())
cs3 = ChatStore(mem_dir=tmp2)
did = cs3.ensure_default()
check("default chat created when empty", bool(did) and cs3.chat_meta(did)["title"] == "Scratch")
check("ensure_default is idempotent", cs3.ensure_default() == did and len(cs3.list_chats()) == 1)
# deleting the active chat clears the pointer; ensure_default recovers
cs3.delete_chat(did, hard=True)
check("active pointer cleared on active delete", cs3.active_chat() is None)
rec = cs3.ensure_default()
check("ensure_default recreates a usable active chat after delete",
      bool(rec) and cs3.active_chat() == rec and cs3.chat_meta(rec) is not None)
shutil.rmtree(tmp2, ignore_errors=True)

# ───────────────────────── export to MDX ─────────────────────────
section("export renders browseable MDX")
mdx = cs.export_chat(a["id"])
check("export has frontmatter + title", mdx.startswith("---") and "# Build the bridge" in mdx)
check("export contains both turns", "## You" in mdx and "## LAWRENCE" in mdx and "per-chat memories" in mdx)
check("export of unknown chat is empty", cs.export_chat("ghost") == "")

# ───────────────────────── stats ─────────────────────────
section("stats")
st = cs.stats()
check("stats counts chats + messages", st["chats"] >= 2 and st["messages"] >= 2, f"stats={st}")
shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────────── Track 2: cross-chat graph edges ─────────────────────────
section("Track 2 — NoteStore edges: message↔message graph")
tmp = Path(tempfile.mkdtemp())
ns = NoteStore(mem_dir=tmp)
src, dst = "20260615-100000:3", "20260614-090000:1"
check("add_edge returns True for a new edge", ns.add_edge(src, dst, kind="reference") is True)
check("duplicate edge is idempotent", ns.add_edge(src, dst, kind="reference") is False)
check("self-loop rejected", ns.add_edge(src, src) is False)
check("empty endpoint rejected", ns.add_edge(src, "") is False)
nb_src = ns.neighborhood(src)
nb_dst = ns.neighborhood(dst)
check("edge visible outbound from src", dst in nb_src["out"])
check("edge visible inbound at dst (bidirectional)", src in nb_dst["in"])
check("edges_for annotates direction", any(e["dir"] == "out" and e["peer"] == dst for e in ns.edges_for(src)))

# edges survive a reload + compose with the note graph (a message links to a note)
note_id = ns.write_note("idea", "A durable insight worth linking from a chat.")
ns.add_edge(src, note_id, kind="cites")
ns2 = NoteStore(mem_dir=tmp)              # reload from disk
check("edges persist across reload", note_id in ns2.neighborhood(src)["out"])
nb_note = ns2.neighborhood(note_id)
check("note node surfaces inbound message edge", src in nb_note["in"])
check("note node still exposes its note links/backlinks keys", "backlinks" in nb_note)
shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────────── summary ─────────────────────────
section("RESULT")
if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\n  ALL CHAT/SESSION + GRAPH CHECKS PASSED")
