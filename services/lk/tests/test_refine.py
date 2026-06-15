"""Slow-loop tests (WS-R/R1) — the alter-ego that may improve the fast answer.

Two layers, both offline:
  • `run_refine` against a stubbed model (`lk.model._post`): a clean verdict dict,
    a coerced `better=false` when no refined text, and the degraded None paths;
  • `dispatch_refine` orchestration with an injected `slow_fn` (no model at all):
    OFF by default (identical to today); the fast answer is never blocked; an
    elevating verdict calls `on_refine` once; a not-better/raising verdict calls it
    zero times; the slow loop runs the refine exactly once (bounded depth 1).
"""
import sys, os
sys.path.insert(0, "services")

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond: FAILS.append(name)
def section(t): print(f"\n=== {t} ===")

import lk.model as M
from lk.kernel import refine as R
from lk.kernel.elevate import Elevator

os.environ.pop("LK_SLOW_LOOP", None)

def _stub_post(seq):
    box = list(seq)
    def post(payload, timeout):
        return {"choices": [{"message": {"content": box.pop(0)}}]}
    return post

# ───────────────────────── run_refine: clean verdict + delta ─────────────────────────
section("run_refine distils a verdict and computes Δconfidence")
M.configure_backend(kind="local")
M._post = _stub_post(['{"better": true, "confidence": 0.9, "critique": "missed an edge case", "refined": "a better answer"}'])
v = R.run_refine("what is X?", "the fast answer", fast_confidence=0.6)
check("returned a verdict", bool(v) and v["refined"] == "a better answer")
check("better is true", v["better"] is True)
check("confidence clamped/parsed", abs(v["confidence"] - 0.9) < 1e-9)
check("delta = conf - fast_conf", abs(v["delta"] - 0.3) < 1e-9, f"delta={v['delta']}")

# ───────────────────────── better with no refined text → coerced false ─────────────────────────
section("a 'better' verdict with no refined text is not better")
M._post = _stub_post(['{"better": true, "confidence": 0.9, "refined": ""}'])
v = R.run_refine("q", "fast", fast_confidence=0.5)
check("better coerced to False (nothing to swap in)", v is not None and v["better"] is False)

# ───────────────────────── degraded paths → None ─────────────────────────
section("degraded paths return None (fast answer stands)")
M._post = _stub_post(['not json at all'])
check("unparseable model output → None", R.run_refine("q", "fast") is None)
def _boom(payload, timeout): raise RuntimeError("model down")
M._post = _boom
check("model exception → None", R.run_refine("q", "fast") is None)
check("empty input → None (no model call)", R.run_refine("", "fast") is None and R.run_refine("q", "") is None)

# ───────────────────────── dispatch: OFF by default ─────────────────────────
section("dispatch_refine is a no-op unless slow_loop:on")
os.environ.pop("LK_SLOW_LOOP", None)
calls = {"slow": 0, "refine": 0}
def stub_slow(u, a, **kw):
    calls["slow"] += 1
    return {"better": True, "delta": 0.5, "refined": "improved", "confidence": 0.9}
on_refine = lambda v: calls.__setitem__("refine", calls["refine"] + 1)
th = R.dispatch_refine("q", "fast", slow_fn=stub_slow, on_refine=on_refine)
check("returns None when disabled", th is None)
check("slow_fn never ran", calls["slow"] == 0 and calls["refine"] == 0)

# ───────────────────────── dispatch: ON, better → elevate once ─────────────────────────
section("slow_loop:on — an elevating verdict surfaces once")
os.environ["LK_SLOW_LOOP"] = "1"
calls = {"slow": 0, "refine": 0}
got = []
def on_ref(v): calls["refine"] += 1; got.append(v)
th = R.dispatch_refine("q", "the fast answer", fast_confidence=0.4,
                       slow_fn=stub_slow, on_refine=on_ref,
                       elevator=Elevator(delta=0.15, max_per_min=5), turn_id="t1")
check("dispatch returned a thread (fast not blocked)", th is not None)
th.join(timeout=2.0)
check("slow loop ran exactly once (bounded depth 1)", calls["slow"] == 1, f"slow={calls['slow']}")
check("on_refine called once with the refined answer",
      calls["refine"] == 1 and got and got[0]["refined"] == "improved")

# ───────────────────────── dispatch: ON, not-better → no surface ─────────────────────────
section("a not-better verdict leaves the fast answer standing")
calls = {"slow": 0, "refine": 0}
def stub_nobetter(u, a, **kw):
    calls["slow"] += 1
    return {"better": False, "refined": "", "confidence": 0.5}
th = R.dispatch_refine("q", "fast", slow_fn=stub_nobetter,
                       on_refine=lambda v: calls.__setitem__("refine", calls["refine"] + 1),
                       turn_id="t2")
th.join(timeout=2.0)
check("slow ran", calls["slow"] == 1)
check("on_refine NOT called", calls["refine"] == 0)

# ───────────────────────── dispatch: ON, slow raises → no crash ─────────────────────────
section("a raising slow loop self-heals (no crash, no surface)")
calls = {"refine": 0}
def stub_raise(u, a, **kw): raise RuntimeError("refine exploded")
th = R.dispatch_refine("q", "fast", slow_fn=stub_raise,
                       on_refine=lambda v: calls.__setitem__("refine", calls["refine"] + 1),
                       turn_id="t3")
th.join(timeout=2.0)
check("no surface on failure", calls["refine"] == 0)
check("thread finished cleanly", not th.is_alive())
os.environ.pop("LK_SLOW_LOOP", None)

# ───────────────────────── summary ─────────────────────────
section("RESULT")
if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\n  ALL SLOW-LOOP CHECKS PASSED")
