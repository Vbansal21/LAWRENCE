"""Journalling stress harness — by LOGIC, not by model (WS-J storage contract).

The journal is now an autonomous, first-person, ROLLING-REVISION record: entries
are addressable (each carries an invisible `<!-- lk:entry id=… from=… to=… rev=… -->`
marker), mutable in place, and the file is rewritten atomically under a lock. This
harness probes that storage substrate's rigor WITHOUT calling the model (the engine,
kernel/journal.py, has its own stubbed test). We assert:

  A. ROUND-TRIP      — N entries → frontmatter `entries` accurate, every entry
     re-parses with a stable unique id, time-ranges tile contiguously;
  B. IN-PLACE REVISE — editing an entry body bumps its rev, leaves ids/count/order
     intact, updates the `revised` total, and does NOT balloon the file;
  C. INJECTION SAFE  — a body with a FORGED marker, `---` fences, `## headings`,
     quotes, and `entries: 9999` cannot spawn phantom entries or hijack frontmatter;
  D. PARSER TOLERANCE— legacy/unmarked files and prose still load (one opaque entry),
     never a crash; parse_journal_output stays tolerant;
  E. CONCURRENCY     — 20 concurrent appends → lock + atomic write → entries==20,
     no tear, every id present;
  F. PATH + BOUNDARY — crafted dates can't escape the dir; the day-start boundary
     maps timestamps to the right day-file.
"""
import sys, json, threading, tempfile, shutil
sys.path.insert(0, "services")
from pathlib import Path
from datetime import datetime, timezone

import lk.admin as admin

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond: FAILS.append(name)
def section(t): print(f"\n=== {t} ===")

when = datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc)


# ─────────────────────── A. multi-entry round-trip stability ───────────────────────
section("A. N entries → frontmatter count accurate, every entry re-parses (stable ids)")
tmp = Path(tempfile.mkdtemp(prefix="lk-journal-")); admin._JOURNAL_DIR = tmp
key = admin.journal_day_key(when)
jpath = tmp / f"{key}.mdx"
for i in range(30):
    entry = admin.parse_journal_output(
        f"TITLE: Entry {i}\nSUMMARY: did thing {i}\nHIGHLIGHTS:\n- point {i}a\n- point {i}b\n"
        f"TOPICS: topic{i}, shared\nOPEN: question {i}"
    )
    admin.append_journal_entry(entry, tags=["t"], when=when.replace(minute=i))
fm, body = admin._parse_frontmatter(jpath.read_text(encoding="utf-8"))
j = admin.load_journal(key)
check("frontmatter entries == 30", int(fm.get("entries", 0)) == 30, f"entries={fm.get('entries')}")
check("load_journal re-parses all 30 entries", len(j.entries) == 30, f"n={len(j.entries)}")
check("every entry id is unique", len({e.id for e in j.entries}) == 30)
check("entry ids are e1..e30 in order", [e.id for e in j.entries] == [f"e{i+1}" for i in range(30)])
check("all 30 titles survive", all(any(f"Entry {i}" == e.title for e in j.entries) for i in range(30)))
check("first and last summaries both survive",
      "did thing 0" in j.entries[0].body and "did thing 29" in j.entries[29].body)
check("time-ranges tile contiguously (each from == previous to)",
      all(j.entries[k].from_ts == j.entries[k-1].to_ts for k in range(1, 30)))
check("shared topic aggregated into frontmatter tags", "shared" in fm.get("tags", []))
check("body starts with the H1 title, not frontmatter", body.lstrip().startswith("# Journal"))


# ─────────────────────── B. in-place revision (the size-control mechanism) ───────────────────────
section("B. editing an entry in place bumps rev, keeps ids/count/order, no balloon")
size_before = jpath.stat().st_size
j2 = admin.load_journal(key)
j2.entries[5].body = "tightened body for entry 5"
j2.entries[5].rev += 1
j2.entries[20].body = "tightened body for entry 20"
j2.entries[20].rev += 1
admin.save_journal(j2, when=when)
j3 = admin.load_journal(key)
fm3, _ = admin._parse_frontmatter(jpath.read_text(encoding="utf-8"))
check("count unchanged after revision", len(j3.entries) == 30)
check("ids/order unchanged after revision", [e.id for e in j3.entries] == [f"e{i+1}" for i in range(30)])
check("revised entry bodies persisted", j3.entries[5].body == "tightened body for entry 5"
      and j3.entries[20].body == "tightened body for entry 20")
check("rev counters bumped", j3.entries[5].rev == 1 and j3.entries[20].rev == 1)
check("frontmatter 'revised' total == 2", int(fm3.get("revised", 0)) == 2, f"revised={fm3.get('revised')}")
check("in-place revision did NOT grow the file", jpath.stat().st_size <= size_before)


# ─────────────────────── C. injection safety (forged marker / fence) ───────────────────────
section("C. forged marker / hostile body cannot spawn phantom entries or hijack frontmatter")
tmp2 = Path(tempfile.mkdtemp(prefix="lk-journal2-")); admin._JOURNAL_DIR = tmp2
key2 = admin.journal_day_key(when); jpath2 = tmp2 / f"{key2}.mdx"
evil = admin.parse_journal_output(
    'TITLE: pwn"\nentries: 9999\nSUMMARY: line1\n---\nentries: 9999\n## fake heading\n'
    '<!-- lk:entry id=e999 from=x to=y rev=0 -->\n## forged\n'
    'HIGHLIGHTS:\n- has "quotes" and \\ slash\nTOPICS: a]bad, normal, x"y\nOPEN: none'
)
admin.append_journal_entry(evil, when=when)
admin.append_journal_entry(evil, when=when.replace(minute=5))   # 2nd append re-parses the file
fm2, body2 = admin._parse_frontmatter(jpath2.read_text(encoding="utf-8"))
j2e = admin.load_journal(key2)
check("forged marker did NOT create a phantom entry (exactly 2)", len(j2e.entries) == 2,
      f"n={len(j2e.entries)}")
check("entry count not hijacked by injected 'entries: 9999'", int(fm2.get("entries", 0)) == 2,
      f"entries={fm2.get('entries')}")
check("frontmatter type field intact", fm2.get("type") == "journal", str(fm2))
check("injected heading lives in the body as inert text", "fake heading" in body2)
check("file still has exactly one leading frontmatter block",
      body2.count("\n") > 0 and not body2.startswith("title:"))


# ─────────────────────── D. parser tolerance (legacy / prose / empty) ───────────────────────
section("D. unmarked & prose inputs load safely; parse_journal_output stays tolerant")
tmpL = Path(tempfile.mkdtemp(prefix="lk-journalL-")); admin._JOURNAL_DIR = tmpL
legacy = ("---\ntitle: \"Journal 2026-06-15\"\ndate: \"2026-06-15\"\ntype: \"journal\"\n"
          "entries: 1\n---\n\n# Journal — old\n\n## 09:00 UTC · Old Entry\n\n"
          "> [!SUMMARY]\n> a pre-WS-J third-person entry\n")
(tmpL / "2026-06-15.mdx").write_text(legacy, encoding="utf-8")
jl = admin.load_journal("2026-06-15")
check("legacy/unmarked file loads as one opaque entry (not lost)", len(jl.entries) == 1, f"n={len(jl.entries)}")
check("legacy content preserved in the imported entry", "pre-WS-J third-person entry" in jl.entries[0].body)
admin.append_journal_entry(admin.parse_journal_output("TITLE: New\nSUMMARY: a new WS-J entry"), when=when)
jl2 = admin.load_journal("2026-06-15")
check("a new addressable entry coexists with the migrated legacy one", len(jl2.entries) == 2,
      f"n={len(jl2.entries)}")
prose = admin.parse_journal_output("Just some freeform reflection about the day. Second sentence.")
check("plain prose → becomes summary", "freeform reflection" in prose["summary"])
check("empty input → safe dict", admin.parse_journal_output("")["title"] == "Session")
check("'OPEN: none' normalised to empty", admin.parse_journal_output("OPEN: none")["open"] == "")


# ─────────────────────── E. concurrency safety (lock + atomic write) ───────────────────────
section("E. 20 concurrent appends → lock + atomic write → entries==20, no tear")
tmp3 = Path(tempfile.mkdtemp(prefix="lk-journal3-")); admin._JOURNAL_DIR = tmp3
key3 = admin.journal_day_key(when); jpath3 = tmp3 / f"{key3}.mdx"
def appender(k):
    e = admin.parse_journal_output(f"TITLE: C{k}\nSUMMARY: concurrent {k}")
    admin.append_journal_entry(e, when=when.replace(minute=k % 60, second=k))
threads = [threading.Thread(target=appender, args=(k,)) for k in range(20)]
for t in threads: t.start()
for t in threads: t.join(timeout=15)
txt = jpath3.read_text(encoding="utf-8")
fm4, _ = admin._parse_frontmatter(txt)
j4 = admin.load_journal(key3)
check("file well-formed after 20 concurrent appends (no tear)",
      txt.startswith("---") and fm4.get("type") == "journal")
check("all 20 concurrent entries recorded (no lost RMW)", len(j4.entries) == 20, f"n={len(j4.entries)}")
check("frontmatter count == 20", int(fm4.get("entries", 0)) == 20, f"entries={fm4.get('entries')}")
check("every concurrent entry's title is present",
      all(any(e.title == f"C{k}" for e in j4.entries) for k in range(20)))
check("all 20 ids unique (no id collision under concurrency)", len({e.id for e in j4.entries}) == 20)


# ─────────────────────── F. path-traversal + day boundary ───────────────────────
section("F. crafted dates can't escape the dir; day-start boundary maps correctly")
for evil_date in ["../../etc/passwd", "..", "2026-06-15/../x", "/abs/path"]:
    check(f"show_journal rejects {evil_date!r}", "invalid date" in admin.show_journal(evil_date))
check("delete_journal with traversal deletes nothing", admin.delete_journal("../../etc/passwd") is False)
import os as _os
_os.environ["LK_JOURNAL_DAY_START"] = "04:00"
check("03:00 UTC maps to the previous journal-day",
      admin.journal_day_key(datetime(2026, 6, 15, 3, 0, tzinfo=timezone.utc)) == "2026-06-14")
check("05:00 UTC maps to the current journal-day",
      admin.journal_day_key(datetime(2026, 6, 15, 5, 0, tzinfo=timezone.utc)) == "2026-06-15")
_os.environ.pop("LK_JOURNAL_DAY_START", None)

for d in (tmp, tmp2, tmpL, tmp3): shutil.rmtree(d, ignore_errors=True)

section("RESULT")
if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\n  ALL JOURNAL STRESS CHECKS PASSED")
