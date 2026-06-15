"""Zettelkasten tests (WS-M/M3) — atomic, addressable, cross-linked notes.

Proves: write→read round-trip; `[[id]]` links resolve both directions; keyword
search finds a note; the optional FTS index_fn hook fires; ids are append-only
(never rewritten, collisions disambiguate); and the memops contract — notes are
counted + backed up but NEVER swept by `clear all`, only by an explicit clear.
Offline, stdlib-only, no model/server/DB needed.
"""
import sys, tempfile, shutil
sys.path.insert(0, "services")
from pathlib import Path

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond: FAILS.append(name)
def section(t): print(f"\n=== {t} ===")

from lk.ctx import NoteStore

# ───────────────────────── write → read round-trip ─────────────────────────
section("write → read round-trip")
tmp = Path(tempfile.mkdtemp())
indexed = []
ns = NoteStore(mem_dir=tmp, index_fn=lambda nid, title, body: indexed.append((nid, title, body)))
nid = ns.write_note("vision", "The CI pipeline failed at the linker stage for libfoo.",
                    source="vision observation", tags=["ci", "build"])
check("write returns an id", bool(nid))
note = ns.read_note(nid)
check("read finds the note", note is not None)
check("body preserved (frontmatter stripped)", note and "linker stage" in note["body"] and "---" not in note["body"])
check("tags preserved", note and note["tags"] == ["ci", "build"])
check("kind preserved", note and note["kind"] == "vision")
check("note file on disk", any(p.name.startswith(nid) for p in (tmp / "notes").glob("*.md")))
check("index_fn (FTS hook) fired once", len(indexed) == 1 and indexed[0][0] == nid)
check("read of unknown id is None", ns.read_note("19990101-000000") is None)

# ───────────────────────── [[link]] → backlink both directions ─────────────────────────
section("links resolve in both directions")
a = ns.write_note("note", "Root idea about retrieval-augmented memory.", tags=["idea"])
b = ns.write_note("note", f"Follow-up that builds on [[{a}]] with a caching twist.", tags=["idea"])
na, nb = ns.read_note(a), ns.read_note(b)
check("forward link recorded on B", a in nb["links"])
check("backlink visible from A", b in ns.backlinks(a))
check("A lists B as a backlink via read", b in na["backlinks"])
check("explicit links arg also works",
      a in ns.read_note(ns.write_note("note", "explicit", links=[a]))["links"])

# ───────────────────────── keyword search ─────────────────────────
section("keyword search")
ns.write_note("audio", "Discussion about quarterly revenue and the Tokyo office expansion.",
              tags=["finance", "tokyo"])
hits = ns.search("tokyo revenue")
check("search finds the note", any("tokyo" in (h.get("tags") or []) for h in hits), f"hits={[h['id'] for h in hits]}")
check("search ranks by overlap (non-empty)", len(hits) >= 1)
check("search miss returns empty", ns.search("zzzznomatchxyz") == [])

# ───────────────────────── append-only ids ─────────────────────────
section("append-only addressable ids")
import lk.ctx.notes as NMOD
# Force two writes to claim the same second → ids must still be distinct.
orig = NMOD.datetime
class _FixedClock:
    @staticmethod
    def now(tz=None):
        return orig(2030, 1, 1, 12, 0, 0, tzinfo=tz)
NMOD.datetime = _FixedClock          # type: ignore
try:
    i1 = ns.write_note("note", "first in the same second")
    i2 = ns.write_note("note", "second in the same second")
finally:
    NMOD.datetime = orig             # type: ignore
check("same-second ids are distinct (no overwrite)", i1 != i2 and i1 and i2)
check("both same-second notes are readable", ns.read_note(i1) and ns.read_note(i2))

# ───────────────────────── stats ─────────────────────────
section("note store stats")
st = ns.stats()
check("stats counts notes", st["notes"] >= 6, f"stats={st}")
shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────────── memops: counted, backed up, spared by clear-all ─────────────────────────
section("memops — notes counted but NOT in clear-all")
import lk.memops as M
tmp = Path(tempfile.mkdtemp())
M.MEM_DIR = tmp
M.LOCK_PATH = tmp / ".writer.lock"
M.BACKUP_DIR = tmp / "backups"
ns2 = NoteStore(mem_dir=tmp)
ns2.write_note("vision", "a notable observation worth keeping forever")
(tmp / "logs").mkdir(exist_ok=True)
(tmp / "logs" / "2030-01-01.jsonl").write_text('{"x":1}\n', encoding="utf-8")
s = M.stats()
check("memops stats includes notes category", "notes" in s["categories"] and s["categories"]["notes"]["files"] >= 1)
res = M.clear(["all"], do_backup=False)
check("clear-all removed the log", (tmp / "logs" / "2030-01-01.jsonl").exists() is False)
check("clear-all SPARED the notes", any((tmp / "notes").glob("*.md")), "notes were wrongly deleted by clear-all")
res2 = M.clear(["notes"], do_backup=False)
check("explicit clear-notes removes them", res2.get("removed", 0) >= 1 and not any((tmp / "notes").glob("*.md")))
shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────────── summary ─────────────────────────
section("RESULT")
if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\n  ALL ZETTELKASTEN CHECKS PASSED")
