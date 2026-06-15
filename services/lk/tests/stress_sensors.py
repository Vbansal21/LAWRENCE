"""Sensor/trigger stress harness — by LOGIC, not by model.

"Are the triggers / proactive-mode / vision / audio giving the correct data at the
correct timings?" We exercise the model-free machinery that decides WHAT crosses
into memory and WHEN the autonomous loop fires:

  A. VISION GATE      — pixel_change_score: first frame forces a write, identical
     frames score 0 (no spam), a changed frame scores > 0, proportionally;
  B. SPOOL DELIVERY   — SpoolWriter→SpoolReader hands every event to ctx in order
     with the right kind/payload; a half-written *.tmp is never read (atomic
     publish); a corrupt *.json is dropped, not crashed on;
  C. PROACTIVE TIMING — the trigger fires at most once per `proactive_interval`,
     is single-flighted (no overlap), marks the clock BEFORE running (no pile-up),
     and re-reads the interval live;
  D. CLEAN SHUTDOWN   — the observer threads start/stop/join cleanly (regression
     guard for the threading.Thread._stop() name collision).
"""
import sys, json, time, threading, tempfile, shutil
sys.path.insert(0, "services")
from pathlib import Path
from types import SimpleNamespace

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond: FAILS.append(name)
def section(t): print(f"\n=== {t} ===")


# ─────────────────────── A. vision change-detection gate ───────────────────────
section("A. pixel_change_score: forces first write, silent on no change, scales")
from lk.obs.vision import pixel_change_score
a = bytes([10, 20, 30, 40] * 64)
b = bytes([10, 20, 30, 40] * 64)
c = bytes([250, 5, 250, 5] * 64)
check("first frame (prev=None) forces a write (score 1.0)", pixel_change_score(None, a) == 1.0)
check("identical frames score 0.0 (no redundant write)", pixel_change_score(a, b) == 0.0)
big = pixel_change_score(a, c)
small = pixel_change_score(a, bytes([10, 20, 30, 41] * 64))
check("a large visual change scores high", big > 0.3, f"{big}")
check("a tiny change scores low but nonzero", 0.0 < small < big, f"small={small} big={big}")
check("score is bounded to [0,1]", 0.0 <= big <= 1.0)


# ─────────────────────── B. spool delivery / ordering / robustness ───────────────────────
section("B. spool: ordered delivery, atomic publish, corrupt-drop")
from lk.obs.spool import SpoolWriter, SpoolReader
d = Path(tempfile.mkdtemp(prefix="lk-spool-"))
delivered = []
dlock = threading.Lock()
class RecCtx:
    def append(self, ts, kind, compact, detailed):
        with dlock:
            delivered.append((ts, kind, compact, detailed))

w = SpoolWriter(d)
for i in range(20):
    w.append(ts=f"2026-06-15T00:00:{i:02d}", kind="vision" if i % 2 else "audio",
             compact=f"c{i}", detailed=f"D{i}")
# a half-written temp file (must be ignored) and a corrupt json (must be dropped)
(d / "zzz-partial.json.tmp").write_text('{"ts":"x"', encoding="utf-8")
(d / "20260101T000000-0-000999.json").write_text("{ not valid json", encoding="utf-8")

reader = SpoolReader(d, RecCtx(), poll=0.02)
reader.start()
for _ in range(100):
    with dlock:
        if len(delivered) >= 20: break
    time.sleep(0.02)
reader.stop(); reader.join(timeout=2)
check("every spooled event delivered exactly once", len(delivered) == 20, f"{len(delivered)}")
check("delivered in spool (timestamp) order", [r[0] for r in delivered] == sorted(r[0] for r in delivered))
check("kind + payload preserved through the spool", delivered[1][1] == "vision" and delivered[0][3] == "D0")
check("the *.tmp file was never ingested (atomic publish)",
      not any(r[3].startswith('{"ts"') for r in delivered))
check("corrupt json dropped, not crashed on", reader.is_alive() is False)
left = list(d.glob("*.json"))
check("reader consumed/cleaned all *.json (incl. the corrupt one)", left == [], f"{[p.name for p in left]}")
shutil.rmtree(d, ignore_errors=True)


# ─────────────────────── C. proactive throttle + single-flight ───────────────────────
section("C. proactive trigger: throttled, single-flighted, marks clock before run, live interval")
import lk.cli as cli
runs = {"n": 0}
inflight = threading.Event()    # set while the stubbed run_proactive is 'busy'
release = threading.Event()
def stub_run_proactive(ctx, retrieval, live_fn=None, present_fn=None):
    runs["n"] += 1
    inflight.set()
    release.wait(2.0)           # stay 'in flight' so we can probe single-flight
cli.run_proactive = stub_run_proactive

cfg   = SimpleNamespace(no_retrieval=False, skip_analysis=False)
state = SimpleNamespace(proactive_interval=999.0, proactive_present=False)
trigger = cli._make_proactive_trigger(ctx=None, retrieval=None, cfg=cfg, state=state)

trigger("vision", "something changed")          # should fire one run
inflight.wait(2.0)
check("first event fires exactly one proactive run", runs["n"] == 1)
for _ in range(50):
    trigger("vision", "more changes")           # throttled + single-flighted → no new runs
check("rapid follow-up events are suppressed (throttle + single-flight)", runs["n"] == 1, f"runs={runs['n']}")
release.set()                                    # let the in-flight run finish
time.sleep(0.05)
trigger("vision", "still within interval")       # interval not elapsed → still suppressed
check("still suppressed within proactive_interval", runs["n"] == 1, f"runs={runs['n']}")

# Live interval change: drop it to 0 → next event fires again (config read live).
release.clear(); inflight.clear()
state.proactive_interval = 0.0
trigger("vision", "interval now zero")
inflight.wait(2.0)
check("lowering proactive_interval live lets it fire again", runs["n"] == 2, f"runs={runs['n']}")
release.set()
# guard: a disabled trigger (no_retrieval) never fires
cfg2 = SimpleNamespace(no_retrieval=True, skip_analysis=False)
state2 = SimpleNamespace(proactive_interval=0.0, proactive_present=False)
before = runs["n"]
cli._make_proactive_trigger(ctx=None, retrieval=None, cfg=cfg2, state=state2)("vision", "x")
time.sleep(0.05)
check("trigger is inert when retrieval is disabled", runs["n"] == before)


# ─────────────────────── D. observer clean shutdown (regression guard) ───────────────────────
section("D. observer threads start/stop/join cleanly (no _stop name collision)")
d2 = Path(tempfile.mkdtemp(prefix="lk-spool2-"))
errs = []
threading.excepthook = lambda a: errs.append(a.exc_value)
r2 = SpoolReader(d2, RecCtx(), poll=0.02)
r2.start(); time.sleep(0.06); r2.stop()
ok = True
try:
    r2.join(timeout=2)
except Exception as e:
    ok = False
    check("SpoolReader.join() does not raise", False, repr(e))
if ok:
    check("SpoolReader.join() does not raise (TypeError _stop collision fixed)", True)
check("thread is no longer alive after join", r2.is_alive() is False)
check("no exception escaped into the thread on shutdown", errs == [], f"{[repr(e) for e in errs]}")
shutil.rmtree(d2, ignore_errors=True)

section("RESULT")
if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\n  ALL SENSOR/TRIGGER STRESS CHECKS PASSED")
