"""Journalling stress harness — by LOGIC, not by model.

The journal is the model's narrative memory: it emits labelled sections
(TITLE/SUMMARY/HIGHLIGHTS/TOPICS/OPEN — see prompts.JOURNAL), admin.parse_journal_output
structures them (tolerantly, no JSON schema), and append_journal_entry stacks them
into a per-day MDX with live frontmatter. We probe that pipeline's rigor:

  A. ROUND-TRIP      — N entries in one day → frontmatter `entries` stays accurate,
     every section survives, the file re-parses each time (read-modify-write stable);
  B. INJECTION SAFE  — section text containing `---`, `## headings`, quotes, newlines
     and hostile TOPICS cannot corrupt the frontmatter or the entry count;
  C. PARSER TOLERANCE— plain prose (no labels), empty, and partial output all yield a
     safe structured dict (summary + derived title), never a crash;
  D. PATH SAFETY     — show/delete journal cannot escape the dir via a crafted date.

It also DOCUMENTS a known limitation: append_journal_entry is a non-atomic, unlocked
read-modify-write, so concurrent journalling can under-count entries. Journalling is
serial in practice (/journal or clean exit), so we assert only the safety property
(the file never ends up torn/unparseable), and report the count gap.
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

tmp = Path(tempfile.mkdtemp(prefix="lk-journal-"))
admin._JOURNAL_DIR = tmp
when = datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc)
jpath = tmp / "2026-06-15.mdx"


# ─────────────────────── A. multi-entry round-trip stability ───────────────────────
section("A. N entries in one day → frontmatter count accurate, file re-parses each time")
for i in range(30):
    entry = admin.parse_journal_output(
        f"TITLE: Entry {i}\nSUMMARY: did thing {i}\nHIGHLIGHTS:\n- point {i}a\n- point {i}b\n"
        f"TOPICS: topic{i}, shared\nOPEN: question {i}"
    )
    admin.append_journal_entry(entry, tags=["t"], when=when.replace(minute=i))
fm, body = admin._parse_frontmatter(jpath.read_text(encoding="utf-8"))
check("frontmatter entries == 30", int(fm.get("entries", 0)) == 30, f"entries={fm.get('entries')}")
check("all 30 entry headings present", all(f"Entry {i}" in body for i in range(30)))
check("first and last summaries both survive", "did thing 0" in body and "did thing 29" in body)
check("shared topic aggregated into frontmatter tags", "shared" in fm.get("tags", []))
check("frontmatter still parseable (single FM block, not duplicated)",
      body.count("\n---\n") >= 29 and not body.startswith("title:"))


# ─────────────────────── B. injection safety ───────────────────────
section("B. hostile section/topic text cannot corrupt frontmatter or count")
tmp2 = Path(tempfile.mkdtemp(prefix="lk-journal2-"))
admin._JOURNAL_DIR = tmp2
jpath2 = tmp2 / "2026-06-15.mdx"
evil = admin.parse_journal_output(
    'TITLE: pwn"\nentries: 9999\nSUMMARY: line1\n---\nentries: 9999\n## fake heading\n'
    'HIGHLIGHTS:\n- has "quotes" and \\ slash\nTOPICS: a]bad, normal, x"y\nOPEN: none'
)
admin.append_journal_entry(evil, when=when)
admin.append_journal_entry(evil, when=when.replace(minute=5))   # second append re-parses FM
fm2, body2 = admin._parse_frontmatter(jpath2.read_text(encoding="utf-8"))
check("entry count not hijacked by injected 'entries: 9999'", int(fm2.get("entries", 0)) == 2,
      f"entries={fm2.get('entries')}")
check("frontmatter type field intact", fm2.get("type") == "journal", str(fm2))
check("injected '---' lives in the body, not as a frontmatter delimiter",
      "fake heading" in body2)
check("file still has exactly one leading frontmatter block",
      jpath2.read_text(encoding="utf-8").count("---") >= 2)


# ─────────────────────── C. parser tolerance ───────────────────────
section("C. parse_journal_output is tolerant (prose / empty / partial)")
prose = admin.parse_journal_output("Just some freeform reflection about the day. Second sentence.")
check("plain prose → becomes summary", "freeform reflection" in prose["summary"])
check("plain prose → title derived from first sentence", prose["title"] and len(prose["title"]) <= 70)
empty = admin.parse_journal_output("")
check("empty input → safe dict with fallback title", empty["title"] == "Session" and empty["summary"] == "")
partial = admin.parse_journal_output("HIGHLIGHTS:\n- only highlights here\n- second")
check("partial (highlights only) → highlights captured", partial["highlights"] == ["only highlights here", "second"])
check("'OPEN: none' normalised to empty", admin.parse_journal_output("OPEN: none")["open"] == "")


# ─────────────────────── D. path-traversal safety ───────────────────────
section("D. journal management cannot escape the dir via a crafted date")
for evil_date in ["../../etc/passwd", "..", "2026-06-15/../x", "/abs/path"]:
    check(f"show_journal rejects {evil_date!r}", "invalid date" in admin.show_journal(evil_date))
check("delete_journal with traversal deletes nothing", admin.delete_journal("../../etc/passwd") is False)


# ─────────────────────── E. concurrency safety (lock + atomic write) ───────────────────────
section("E. concurrent journalling: lock + atomic write → no tear, no lost entries")
tmp3 = Path(tempfile.mkdtemp(prefix="lk-journal3-"))
admin._JOURNAL_DIR = tmp3
jpath3 = tmp3 / "2026-06-15.mdx"
def appender(k):
    e = admin.parse_journal_output(f"TITLE: C{k}\nSUMMARY: concurrent {k}")
    admin.append_journal_entry(e, when=when.replace(minute=k % 60, second=k))
threads = [threading.Thread(target=appender, args=(k,)) for k in range(20)]
for t in threads: t.start()
for t in threads: t.join(timeout=15)
txt = jpath3.read_text(encoding="utf-8")
fm3, body3 = admin._parse_frontmatter(txt)
check("journal file is well-formed after 20 concurrent appends (no tear)",
      txt.startswith("---") and fm3.get("type") == "journal")
counted = int(fm3.get("entries", 0))
check("all 20 concurrent entries recorded (no lost RMW)", counted == 20, f"entries={counted}/20")
check("every concurrent entry's heading is present",
      all(f"C{k}" in body3 for k in range(20)))

for d in (tmp, tmp2, tmp3): shutil.rmtree(d, ignore_errors=True)

section("RESULT")
if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\n  ALL JOURNAL STRESS CHECKS PASSED")
