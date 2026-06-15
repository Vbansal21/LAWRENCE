"""Elevation-gate tests (WS-R/R2) — the one channel slow/background output uses
to reach the foreground.

Pure policy, no model. Proves:
  • a better, confident, novel candidate elevates and emits exactly one event;
  • a sub-delta confidence gain OR a duplicate is blocked (no event);
  • the rolling-minute rate limit caps surfaced elevations at max_per_min;
  • BOTH shapes — a slow-loop refinement and a tick finding — route through the
    same gate (the shared path);
  • elevation is idempotent per turn-id (no double-surface of one refinement).
"""
import sys
sys.path.insert(0, "services")

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond: FAILS.append(name)
def section(t): print(f"\n=== {t} ===")

from lk.kernel.elevate import Elevator

# a controllable clock so the rate-limit window is deterministic
class Clock:
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t
    def advance(self, dt): self.t += dt

# ───────────────────────── gate passes: better & Δconf≥delta & novel ─────────────────────────
section("a better, confident, novel candidate elevates once")
emitted = []
el = Elevator(delta=0.15, max_per_min=5)
ok = el.elevate({"better": True, "delta": 0.2, "refined": "a clearly improved answer"},
                turn_id="t1", prior="the original fast answer", emit=emitted.append)
check("elevate returned True", ok is True)
check("emitted exactly one event", len(emitted) == 1 and "improved" in emitted[0]["refined"])
check("counter incremented", el.elevated == 1 and el.blocked == 0)

# ───────────────────────── gate blocks: Δconf below delta ─────────────────────────
section("a sub-delta confidence gain is blocked")
emitted = []
el = Elevator(delta=0.15, max_per_min=5)
ok = el.elevate({"better": True, "delta": 0.05, "refined": "marginally different"},
                turn_id="t1", emit=emitted.append)
check("blocked (Δconf<delta)", ok is False and emitted == [])
check("not-better is blocked too",
      el.elevate({"better": False, "delta": 0.9, "refined": "x"}, turn_id="t1") is False)

# ───────────────────────── gate blocks: duplicate ─────────────────────────
section("a near-duplicate of what's shown is blocked (idempotent per turn)")
emitted = []
el = Elevator(delta=0.0, max_per_min=5)
item = {"better": True, "delta": 0.5, "refined": "the same refined text"}
check("first elevation passes", el.elevate(item, turn_id="t7", emit=emitted.append) is True)
check("second identical elevation blocked", el.elevate(item, turn_id="t7", emit=emitted.append) is False)
check("only one event emitted", len(emitted) == 1)
check("duplicate of the prior fast answer blocked",
      el.elevate({"better": True, "delta": 0.5, "refined": "fast text"},
                 turn_id="t8", prior="FAST TEXT") is False)

# ───────────────────────── rate limit: ≤ max_per_min per rolling minute ─────────────────────────
section("rate limit caps surfaced elevations per minute")
clk = Clock()
el = Elevator(delta=0.0, max_per_min=2, now=clk)
r = [el.elevate({"better": True, "delta": 0.9, "refined": f"distinct answer number {i}"},
                turn_id=f"r{i}") for i in range(3)]
check("first two pass, third rate-limited", r == [True, True, False], f"r={r}")
clk.advance(61)   # roll past the window
r4 = el.elevate({"better": True, "delta": 0.9, "refined": "a fresh answer after the window"},
                turn_id="r4")
check("a new window allows elevation again", r4 is True)

# ───────────────────────── shared path: a finding AND a refinement ─────────────────────────
section("a tick finding and a slow refinement both route through one gate")
emitted = []
el = Elevator(delta=0.15, max_per_min=5)
# a finding has no 'better'/'delta' — defaults to eligible, gated on novelty+rate
finding = {"headline": "Heads-up", "insight": "a timely and useful unprompted fact"}
refine  = {"better": True, "delta": 0.3, "refined": "a materially better answer"}
ok_f = el.elevate(finding, turn_id="tick", emit=emitted.append)
ok_r = el.elevate(refine,  turn_id="t9",   emit=emitted.append)
check("finding elevated through the shared gate", ok_f is True)
check("refinement elevated through the shared gate", ok_r is True)
check("both emitted (two distinct foreground events)", len(emitted) == 2)
check("an empty candidate never elevates", el.elevate({"better": True, "delta": 0.9}, turn_id="z") is False)

# ───────────────────────── summary ─────────────────────────
section("RESULT")
if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\n  ALL ELEVATION-GATE CHECKS PASSED")
