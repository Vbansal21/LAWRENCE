"""LIVE smoke test of the fast/slow loop (WS-R) — needs network + a real backend.

NOT part of `make check` (it makes real model calls). Run explicitly:
    python3 services/lk/tests/smoke_slow_loop.py

It wires the configured backend exactly as the app does (config.apply_to_env),
then proves end-to-end what the offline suites could only stub:
  1. FAST  — a schema-constrained RESPONSE call returns valid JSON with answer_text;
  2. SLOW  — run_refine() critiques a deliberately-WRONG fast answer and returns a
     well-formed verdict {better, confidence, critique, refined, delta};
  3. WIRING— dispatch_refine() (LK_SLOW_LOOP=on) runs the slow loop off-thread and,
     via the shared Elevator, fires on_refine exactly when the verdict elevates.
Structure is hard-asserted; the model's semantic verdict is reported (not forced).
"""
import sys, os, json, threading, time
sys.path.insert(0, "services")

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond: FAILS.append(name)
def section(t): print(f"\n=== {t} ===")

from lk import config, model
from lk.kernel import prompts, schemas
from lk.kernel.invoke import _build_messages, _extract_json
from lk.kernel.refine import run_refine, dispatch_refine, enabled
from lk.kernel.elevate import Elevator

# ── wire the real backend (gemini per .runtime/lk.json) ───────────────────────
applied = config.apply_to_env()
section("backend")
print("  applied:", {k: v for k, v in applied.items() if "route" in k or k == "backend"})
print("  describe:", model.describe_backend())
check("backend reachable (health)", model.health(timeout=10))
if FAILS:
    print("\n  backend unreachable — aborting live smoke test"); sys.exit(1)


# ── 1. FAST loop: schema-constrained answer ───────────────────────────────────
section("1. fast loop — RESPONSE call returns valid JSON with answer_text")
q = "What is 17 multiplied by 23? Answer with just the number and a one-line check."
raw = model.call_model(
    _build_messages(prompts.RESPONSE, f"USER QUESTION: {q}", [], []),
    max_tokens=400, temperature=0.1, schema=schemas.RESPONSE, role="response",
)
fast = _extract_json(raw.get("text", "")) or {}
fast_answer = str(fast.get("answer_text", "")).strip()
check("fast response parsed as JSON", bool(fast))
check("fast answer_text non-empty", bool(fast_answer), repr(raw.get("text", ""))[:200])
print("  fast answer:", fast_answer[:160].replace("\n", " "))


# ── 2. SLOW loop: critique a WRONG fast answer ────────────────────────────────
section("2. slow loop — run_refine critiques a deliberately wrong fast answer")
wrong = "17 × 23 = 380."   # actually 391 — the refiner should catch this
verdict = run_refine(q, wrong, fast_confidence=0.4, timeout=60)
check("run_refine returned a verdict (not None)", verdict is not None)
if verdict:
    print("  verdict:", json.dumps({k: (v[:120] if isinstance(v, str) else v)
                                     for k, v in verdict.items()}, ensure_ascii=False))
    check("verdict has all contract keys",
          set(verdict) >= {"better", "confidence", "critique", "refined", "delta"})
    check("'better' is a bool", isinstance(verdict["better"], bool))
    check("confidence in [0,1]", 0.0 <= float(verdict["confidence"]) <= 1.0)
    check("delta is numeric", isinstance(verdict["delta"], float))
    if verdict["better"]:
        check("a 'better' verdict carries refined text", bool(verdict["refined"].strip()))
        has_391 = "391" in verdict["refined"]
        print(f"  → refiner judged it improvable; refined contains '391': {has_391}")
    else:
        print("  → refiner let the fast answer stand (better=false)")


# ── 3. WIRING: dispatch_refine → Elevator → on_refine ─────────────────────────
section("3. end-to-end — dispatch_refine (slow_loop ON) fires on_refine via the gate")
os.environ["LK_SLOW_LOOP"] = "on"
check("enabled() reflects LK_SLOW_LOOP=on", enabled() is True)
fired = []
gate = Elevator()
th = dispatch_refine(q, wrong, fast_confidence=0.3,
                     on_refine=lambda item: fired.append(item),
                     elevator=gate, turn_id="t-smoke")
check("dispatch_refine spawned a worker thread (not None when enabled)", th is not None)
if th:
    th.join(timeout=70)
    check("slow-loop thread finished", not th.is_alive())
print(f"  elevator: elevated={gate.elevated} blocked={gate.blocked}; on_refine fired={len(fired)}")
# The gate fires iff the verdict was better+novel+confident — report, don't force.
if fired:
    item = fired[0]
    check("elevated item carries refined text + turn_id",
          bool(str(item.get("refined", "")).strip()) and item.get("turn_id") == "t-smoke")
    print("  elevated answer:", str(item.get("refined", ""))[:160].replace("\n", " "))
else:
    print("  (no elevation — verdict was not better/novel/confident enough; stand-down is valid)")
check("end-to-end ran without error and gate accounted for the verdict",
      (gate.elevated + gate.blocked) >= 1)

section("RESULT")
if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\n  SLOW-LOOP LIVE SMOKE TEST PASSED")
