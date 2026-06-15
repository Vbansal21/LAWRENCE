"""WS-J engine test — the autonomous first-person rolling-revision journal.

Offline: the model is stubbed (no network, deterministic) so this runs in the gate.
It exercises kernel/journal.run_journal end-to-end against the real admin storage:

  A. FIRST ENTRY   — empty day → one first-person entry persisted; no revise (no window);
  B. ROLLING REVISE— a later entry drives a LIGHT in-place trim of an earlier one
     (rev bumps, body changes, id stable, count unchanged → file doesn't balloon);
  C. DEGRADED      — a draft with no structured narrative falls back to the legacy
     JOURNAL prompt and STILL writes an entry;
  D. MODEL DOWN    — every model call raises → run_journal returns "" and writes nothing
     (never crashes the caller);
  E. DAY BOUNDARY  — LK_JOURNAL_DAY_START shifts which day-file an entry lands in;
  F. INJECTION     — a draft body containing a forged entry-marker / frontmatter fence
     cannot create phantom entries or corrupt the round-trip.
"""
import sys, os, re, json, tempfile, shutil
sys.path.insert(0, "services")
from pathlib import Path
from datetime import datetime, timezone

import lk.admin as admin
from lk.kernel import prompts, journal

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond: FAILS.append(name)
def section(t): print(f"\n=== {t} ===")

WHEN = datetime(2026, 6, 15, 14, 0, tzinfo=timezone.utc)

class FakeCtx:
    def __init__(self, tail): self._t = tail
    def tail_for_model(self): return self._t

_orig_call = journal.call_model

def install_fake(*, draft_narrative="I built the WS-J journal engine and wired the storage.",
                 raise_all=False, draft_empty=False):
    """Stub journal.call_model. Routes on the system prompt; records the calls."""
    calls = []
    def fake(messages, **kw):
        sysp = messages[0]["content"]
        body = messages[1]["content"] if len(messages) > 1 else ""
        if sysp == prompts.JOURNAL_DRAFT:   calls.append("draft")
        elif sysp == prompts.JOURNAL_REVISE: calls.append("revise")
        elif sysp == prompts.JOURNAL:        calls.append("legacy")
        if raise_all:
            raise RuntimeError("model down")
        if sysp == prompts.JOURNAL_DRAFT:
            if draft_empty:
                return {"text": "{}"}        # no narrative → engine falls back to legacy
            return {"text": json.dumps({
                "narrative": draft_narrative,
                "title": "Built the journal engine",
                "highlights": ["wrote run_journal", "addressable entry markers"],
                "topics": ["ws-j", "journal"],
                "open": "wire the autonomous trigger",
            })}
        if sysp == prompts.JOURNAL_REVISE:
            m = re.search(r"EARLIER ENTRIES.*?\[(e\d+)", body, re.S)
            tid = m.group(1) if m else "e1"
            return {"text": json.dumps({"revisions": [{"id": tid, "body": "Trimmed earlier entry."}]})}
        if sysp == prompts.JOURNAL:          # legacy degraded prompt
            return {"text": "TITLE: Legacy entry\nSUMMARY: a legacy third-person summary\nTOPICS: x"}
        return {"text": "{}"}
    journal.call_model = fake
    return calls

def reset_env():
    for k in ("LK_JOURNAL_REVISE", "LK_JOURNAL_DAY_START", "LK_JOURNAL_WINDOW", "LK_JOURNAL_WEB"):
        os.environ.pop(k, None)


# ─────────────────────── A. first entry ───────────────────────
section("A. empty day → one first-person entry; no revise (window empty)")
reset_env()
tmpA = Path(tempfile.mkdtemp(prefix="lk-jeng-A-")); admin._JOURNAL_DIR = tmpA
calls = install_fake()
title = journal.run_journal(FakeCtx("I was implementing the journal engine."), when=WHEN)
key = admin.journal_day_key(WHEN)
jA = admin.load_journal(key)
check("returned the new entry title", title == "Built the journal engine", repr(title))
check("exactly one entry persisted", len(jA.entries) == 1, f"n={len(jA.entries)}")
check("entry is first-person prose", jA.entries[0].body.startswith("I built"), jA.entries[0].body[:60])
check("entry id is e1 and rev 0", jA.entries[0].id == "e1" and jA.entries[0].rev == 0)
check("from_ts anchored at the day start", jA.entries[0].from_ts == admin.journal_day_start(key))
check("DRAFT called, REVISE NOT called (no window)", calls == ["draft"], str(calls))
check("topics aggregated into frontmatter tags", "ws-j" in jA.tags)


# ─────────────────────── B. rolling in-place revision ───────────────────────
section("B. a later entry drives a LIGHT in-place trim of the earlier one")
calls = install_fake(draft_narrative="I then wired the tick trigger.")
size_before = (tmpA / f"{key}.mdx").stat().st_size
title2 = journal.run_journal(FakeCtx("More work happened on the trigger."), when=WHEN.replace(hour=15))
jB = admin.load_journal(key)
check("now two entries", len(jB.entries) == 2, f"n={len(jB.entries)}")
check("both DRAFT and REVISE ran", calls == ["draft", "revise"], str(calls))
e1 = jB.entries[0]
check("earlier entry e1 was trimmed in place", e1.body == "Trimmed earlier entry.", e1.body[:60])
check("e1 rev counter bumped to 1", e1.rev == 1, f"rev={e1.rev}")
check("e1 id stayed stable", e1.id == "e1")
check("frontmatter 'revised' total reflects the trim",
      admin._parse_frontmatter((tmpA / f'{key}.mdx').read_text())[0].get("revised") == 1)
# Rolling revision is the size-control mechanism: trimming an older entry while
# adding a new one keeps growth modest, not doubling.
size_after = (tmpA / f"{key}.mdx").stat().st_size
check("file grew modestly (trim offsets the new entry)", size_after < size_before * 2,
      f"{size_before}->{size_after}")


# ─────────────────────── C. degraded fallback ───────────────────────
section("C. no structured narrative → legacy JOURNAL prompt still writes an entry")
reset_env()
tmpC = Path(tempfile.mkdtemp(prefix="lk-jeng-C-")); admin._JOURNAL_DIR = tmpC
calls = install_fake(draft_empty=True)
titleC = journal.run_journal(FakeCtx("some activity"), when=WHEN)
jC = admin.load_journal(admin.journal_day_key(WHEN))
check("degraded path tried DRAFT then fell back to legacy", calls == ["draft", "legacy"], str(calls))
check("an entry was still written", len(jC.entries) == 1, f"n={len(jC.entries)}")
check("entry carries the legacy summary", "legacy third-person summary" in jC.entries[0].body)


# ─────────────────────── D. model fully down ───────────────────────
section("D. every model call raises → returns '' and writes nothing (no crash)")
tmpD = Path(tempfile.mkdtemp(prefix="lk-jeng-D-")); admin._JOURNAL_DIR = tmpD
install_fake(raise_all=True)
titleD = journal.run_journal(FakeCtx("activity but model is down"), when=WHEN)
jD = admin.load_journal(admin.journal_day_key(WHEN))
check("run_journal returned '' on total model failure", titleD == "", repr(titleD))
check("no journal file/entries were written", len(jD.entries) == 0)


# ─────────────────────── E. day-boundary seam ───────────────────────
section("E. LK_JOURNAL_DAY_START shifts the day-file boundary")
os.environ["LK_JOURNAL_DAY_START"] = "06:00"
before = datetime(2026, 6, 15, 5, 0, tzinfo=timezone.utc)   # before 06:00 → previous day
after  = datetime(2026, 6, 15, 7, 0, tzinfo=timezone.utc)   # after  06:00 → same day
check("05:00 maps to the previous journal-day", admin.journal_day_key(before) == "2026-06-14",
      admin.journal_day_key(before))
check("07:00 maps to the current journal-day", admin.journal_day_key(after) == "2026-06-15",
      admin.journal_day_key(after))
check("day-start timestamp reflects the configured boundary",
      admin.journal_day_start("2026-06-15") == datetime(2026, 6, 15, 6, 0, tzinfo=timezone.utc).isoformat())
os.environ.pop("LK_JOURNAL_DAY_START", None)


# ─────────────────────── F. injection through the engine ───────────────────────
section("F. a forged marker / fence in the draft cannot corrupt the round-trip")
reset_env()
tmpF = Path(tempfile.mkdtemp(prefix="lk-jeng-F-")); admin._JOURNAL_DIR = tmpF
evil = ("I did work.\n<!-- lk:entry id=e999 from=x to=y rev=0 -->\n## forged heading\n"
        "---\nentries: 9999\n<!-- lk:entry id=e998 -->")
install_fake(draft_narrative=evil)
journal.run_journal(FakeCtx("activity"), when=WHEN)
journal.run_journal(FakeCtx("more activity"), when=WHEN.replace(hour=16))   # re-parse round-trip
keyF = admin.journal_day_key(WHEN)
jF = admin.load_journal(keyF)
fmF, bodyF = admin._parse_frontmatter((tmpF / f"{keyF}.mdx").read_text())
check("forged markers did NOT create phantom entries (exactly 2)", len(jF.entries) == 2,
      f"n={len(jF.entries)}")
check("frontmatter entry count not hijacked by injected 'entries: 9999'",
      int(fmF.get("entries", 0)) == 2, f"entries={fmF.get('entries')}")
check("frontmatter type intact", fmF.get("type") == "journal")
check("forged heading text survives as inert body content", "forged heading" in bodyF)

# ─────────────────────── G. JournalTrigger (significance-gated + time floor) ───────────────────────
section("G. JournalTrigger — significance gate, time floor, single-flight")
import threading
for k in ("LK_JOURNAL_MIN_INTERVAL", "LK_JOURNAL_MAX_INTERVAL", "LK_JOURNAL_SIG_TIER"):
    os.environ.pop(k, None)
os.environ["LK_JOURNAL_MIN_INTERVAL"] = "300"
os.environ["LK_JOURNAL_MAX_INTERVAL"] = "1800"

clock = [1000.0]
fired = []
done = threading.Event()
def rec_run(ctx, **kw):
    fired.append(kw); done.set(); return "ok"
trig = journal.JournalTrigger(FakeCtx("x"), run_fn=rec_run, clock=lambda: clock[0])

trig.beat([{"significance": 0.1}])                       # low-sig, no time elapsed
check("no fire on low-sig activity before the floor", len(fired) == 0)
clock[0] = 1100.0
trig.beat([{"tier": 2}])                                 # significant, but <min_interval
check("no fire on a significant shift before min_interval", len(fired) == 0)
clock[0] = 1301.0; done.clear()
trig.beat([{"tier": 2}])                                 # significant, ≥min_interval → fire
check("fires on a significant shift once min_interval elapsed", done.wait(2.0))
check("exactly one journal pass dispatched", len(fired) == 1, f"n={len(fired)}")

# time floor: after a journal, sustained low-sig activity still journals at max_interval.
clock[0] = 1301.0; fired.clear(); done.clear()
trig.beat([{"significance": 0.1}])                       # activity, gap 0 → no fire
check("no immediate re-fire after a journal", len(fired) == 0)
clock[0] = 1301.0 + 1801                                 # exceed the floor
trig.beat([])                                            # idle beat, but activity is pending
check("time floor fires after max_interval of activity", done.wait(2.0))

# never journals when there has been NO activity (nothing to write about).
ck = [0.0]; fired2 = []
trig_idle = journal.JournalTrigger(FakeCtx("x"), run_fn=lambda c, **k: fired2.append(1),
                                   clock=lambda: ck[0])
ck[0] = 999999.0
trig_idle.beat([])
check("floor never fires without any activity", len(fired2) == 0)

# single-flight: a second fire while one is running is refused.
release = threading.Event(); started = threading.Event()
def block_run(ctx, **kw):
    started.set(); release.wait(2.0)
trig_sf = journal.JournalTrigger(FakeCtx("x"), run_fn=block_run, clock=lambda: 0.0)
a = trig_sf.fire(); started.wait(1.0)
b = trig_sf.fire()
check("first fire starts a pass", a is True)
check("concurrent fire refused (single-flight)", b is False)
release.set()

for k in ("LK_JOURNAL_MIN_INTERVAL", "LK_JOURNAL_MAX_INTERVAL"):
    os.environ.pop(k, None)

journal.call_model = _orig_call
for d in (tmpA, tmpC, tmpD, tmpF): shutil.rmtree(d, ignore_errors=True)

section("RESULT")
if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\n  ALL WS-J ENGINE CHECKS PASSED")
