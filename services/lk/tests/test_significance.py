"""Graded-significance tests (WS-C/C2) — running mean±σ → action tier.

Proves the spine's "how much does this matter?" policy (pure math, no model):
  • three synthetic events land in the three tiers (log / note / study);
  • the tier→action mapping holds and is exhaustive;
  • thresholds are config-driven (env knobs change the verdict);
  • the running mean/σ updates as scores arrive (Welford);
  • adaptive thresholds never drop below the configured floors (conservative);
  • a missing/None score (model down) grades to the lowest tier — never surfaces;
  • the Extractor attaches a `tier` and uses it (not a flat floor) to mint notes.
"""
import sys, os, tempfile, shutil
sys.path.insert(0, "services")
from pathlib import Path

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond: FAILS.append(name)
def section(t): print(f"\n=== {t} ===")

for _k in ("LK_SIG_WARMUP", "LK_SIG_K", "LK_NOTE_FLOOR", "LK_SIG_ACT_FLOOR"):
    os.environ.pop(_k, None)

from lk.ctx.significance import Grader, TIER_LOG, TIER_NOTE, TIER_STUDY, TIER_ACTION

# ───────────────────────── cold start: fixed conservative floors ─────────────────────────
section("cold start grades on fixed floors (note=0.6, act=0.8)")
g = Grader(warmup=5)                       # no samples yet → fixed floors
check("low score → LOG",   g.classify(0.30) == TIER_LOG)
check("mid score → NOTE",  g.classify(0.65) == TIER_NOTE)
check("high score → STUDY", g.classify(0.90) == TIER_STUDY)
check("None (model down) → LOG", g.classify(None) == TIER_LOG)
check("garbage score → LOG", g.classify("nope") == TIER_LOG)

# ───────────────────────── tier→action mapping ─────────────────────────
section("tier→action mapping is total and stable")
check("LOG→log",   TIER_ACTION[TIER_LOG] == "log")
check("NOTE→note", TIER_ACTION[TIER_NOTE] == "note")
check("STUDY→study", TIER_ACTION[TIER_STUDY] == "study")
check("exactly three tiers", set(TIER_ACTION) == {0, 1, 2})

# ───────────────────────── three synthetic events → three tiers ─────────────────────────
section("a warmed band sorts three events into the three tiers")
g = Grader(warmup=4, k=1.0, note_floor=0.0, act_floor=0.0)   # let the band rule
for s in (0.50, 0.50, 0.50, 0.50):  g.update(s)              # mean≈0.5, σ≈0
# σ is ~0 so push some spread, then re-evaluate against mean+kσ
g = Grader(warmup=4, k=1.0, note_floor=0.0, act_floor=0.0)
for s in (0.20, 0.40, 0.60, 0.80):  g.update(s)              # mean=0.5, σ≈0.258
lo, hi = g.thresholds()
check("note threshold == mean", abs(lo - g.mean) < 1e-9, f"lo={lo} mean={g.mean}")
check("act threshold == mean+kσ", abs(hi - (g.mean + g.k * g.std)) < 1e-9, f"hi={hi}")
check("below-mean → LOG",   g.classify(0.30) == TIER_LOG)
check("around-mean → NOTE", g.classify(0.55) == TIER_NOTE)
check("well-above → STUDY", g.classify(0.95) == TIER_STUDY)

# ───────────────────────── running mean/σ updates ─────────────────────────
section("running mean/σ track the stream (Welford)")
g = Grader(warmup=0)
g.update(0.0); g.update(1.0)
check("mean of {0,1} == 0.5", abs(g.mean - 0.5) < 1e-9, f"mean={g.mean}")
check("sample std of {0,1} == 0.707", abs(g.std - (0.5 ** 0.5)) < 1e-9, f"std={g.std}")
check("n counted", g.n == 2)

# ───────────────────────── conservative: thresholds never fall below floors ─────────────────────────
section("a calm stream cannot lower the bar below the floors")
g = Grader(warmup=3, k=1.0, note_floor=0.6, act_floor=0.8)
for s in (0.05, 0.05, 0.05, 0.05):  g.update(s)              # very low, calm mean
lo, hi = g.thresholds()
check("note threshold clamped at floor", lo == 0.6, f"lo={lo}")
check("act threshold clamped at floor", hi == 0.8, f"hi={hi}")
check("a 0.5 score stays LOG (no spam)", g.classify(0.5) == TIER_LOG)

# ───────────────────────── config-driven: env knobs change the verdict ─────────────────────────
section("thresholds are config-driven (env)")
g = Grader()                               # all live from env
os.environ["LK_NOTE_FLOOR"] = "0.9"        # raise the note bar very high
check("0.7 is below a 0.9 note floor → LOG", g.classify(0.7) == TIER_LOG)
os.environ["LK_NOTE_FLOOR"] = "0.2"        # drop it low
check("0.7 clears a 0.2 note floor → NOTE", g.classify(0.7) == TIER_NOTE)
os.environ.pop("LK_NOTE_FLOOR", None)

# ───────────────────────── grade() classifies THEN learns ─────────────────────────
section("grade() classifies against history, then folds the sample in")
g = Grader(warmup=0, note_floor=0.0, act_floor=10.0)   # act unreachable → never STUDY
t0 = g.grade(0.4)
check("first grade used the empty band", t0 in (TIER_LOG, TIER_NOTE))
check("grade incremented n", g.n == 1)

# ───────────────────────── extractor attaches tier + gates notes on it ─────────────────────────
section("Extractor uses the tier (not a flat floor) for notes")
from lk.ctx import Extractor, NoteStore
tmp = Path(tempfile.mkdtemp())
ns = NoteStore(mem_dir=tmp)
# pin a deterministic band: note≥0.6, act≥0.8, no warmup wobble
g = Grader(warmup=0, note_floor=0.6, act_floor=0.8)
def fn_hi(s, k): return {"clean": "a notable thing", "significance": 0.85, "tags": []}
ex = Extractor(fn_hi, note_store=ns, grader=g)
r = ex.extract("a brand new and distinct observation to extract", "vision")
check("result carries a tier", r.get("tier") == TIER_STUDY, f"tier={r.get('tier')}")
check("study-tier minted a note", r.get("note_id") and ex.notes_written == 1)
shutil.rmtree(tmp, ignore_errors=True)

tmp = Path(tempfile.mkdtemp())
ns = NoteStore(mem_dir=tmp)
g = Grader(warmup=0, note_floor=0.6, act_floor=0.8)
def fn_lo(s, k): return {"clean": "ambient chrome", "significance": 0.2, "tags": []}
ex = Extractor(fn_lo, note_store=ns, grader=g)
r = ex.extract("a different low-value distinct ambient frame here", "vision")
check("log-tier minted NO note", r.get("tier") == TIER_LOG and "note_id" not in r and ex.notes_written == 0)
shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────────── summary ─────────────────────────
section("RESULT")
if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\n  ALL GRADED-SIGNIFICANCE CHECKS PASSED")
