"""Cognitive-tick tests (WS-C/C1) — the heartbeat / spine.

Proves the autonomy contract with every collaborator stubbed (offline, no server,
beats driven synchronously for determinism):
  • an empty beat makes ZERO model calls and backs the cadence off;
  • a non-empty beat above the floor takes EXACTLY ONE droppable action and snaps
    the cadence back; below the floor it takes none;
  • the action runs on the MOST significant drained event;
  • a raising act_fn (model down) is swallowed — the loop self-heals;
  • due intents fire (no model) via fire_fn;
  • the idle hook runs once every `idle_every` empty beats;
  • LK_TICK=0 disables every beat (config parity);
  • start()/stop() lifecycle is clean.
"""
import sys, os, time
sys.path.insert(0, "services")

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond: FAILS.append(name)
def section(t): print(f"\n=== {t} ===")

from lk.kernel.tick import CognitiveTick, enabled

os.environ.pop("LK_TICK", None)        # default-on
os.environ.pop("LK_TICK_FLOOR", None)  # default 0.5

def ev(sig): return {"clean": f"e{sig}", "significance": sig}

# ───────────────────────── idle beat → 0 model calls + back-off ─────────────────────────
section("idle beat is free and backs off")
acts = {"n": 0}
t = CognitiveTick(lambda: [], lambda e: acts.__setitem__("n", acts["n"] + 1),
                  interval=10.0, max_interval=40.0)
i0 = t._interval
t.beat()
check("empty beat takes no action", acts["n"] == 0)
check("empty beat counts as a beat", t.beats == 1)
check("cadence backed off toward max", t._interval > i0, f"{i0}->{t._interval}")
t.beat(); t.beat()
check("cadence keeps backing off, clamped at max", t._interval <= t._max_interval)

# ───────────────────────── high-sig beat → exactly one action + snap-back ─────────────────────────
section("significant beat acts once and snaps cadence back")
acts = {"n": 0, "seen": None}
def _act(events):
    acts["n"] += 1
    acts["seen"] = events
t = CognitiveTick(lambda: [ev(0.2), ev(0.9), ev(0.4)], _act, interval=10.0, max_interval=40.0)
t._interval = 40.0                      # pretend it had backed off
t.beat()
check("exactly one action", acts["n"] == 1 and t.actions == 1)
check("acted on the full drained batch", acts["seen"] is not None and len(acts["seen"]) == 3)
check("cadence snapped back to base", t._interval == 10.0, f"interval={t._interval}")

# ───────────────────────── below the floor → no action ─────────────────────────
section("sub-floor beat takes no action")
acts = {"n": 0}
t = CognitiveTick(lambda: [ev(0.1), ev(0.3)], lambda e: acts.__setitem__("n", acts["n"] + 1))
t.beat()
check("no action below LK_TICK_FLOOR", acts["n"] == 0 and t.actions == 0)
check("but the empty-run counter reset (events were drained)", t._empty_run == 0)

# ───────────────────────── C2 tier gating preferred over the floor ─────────────────────────
section("a graded C2 tier overrides the significance floor")
def evt(sig, tier): return {"clean": f"e{sig}", "significance": sig, "tier": tier}
# study-tier (2) acts even if significance is modest…
acts = {"n": 0}
t = CognitiveTick(lambda: [evt(0.55, 2)], lambda e: acts.__setitem__("n", acts["n"] + 1))
t.beat()
check("study-tier event acts", acts["n"] == 1)
# …and a merely note-worthy tier (1) does NOT, even with a high raw score.
acts = {"n": 0}
t = CognitiveTick(lambda: [evt(0.95, 1)], lambda e: acts.__setitem__("n", acts["n"] + 1))
t.beat()
check("note-tier event does not surface (despite sig=0.95)", acts["n"] == 0)
# the most-significant event is the one whose tier is consulted.
acts = {"n": 0}
t = CognitiveTick(lambda: [evt(0.40, 2), evt(0.99, 1)],
                  lambda e: acts.__setitem__("n", acts["n"] + 1))
t.beat()
check("top-by-significance is note-tier → no action", acts["n"] == 0)

# ───────────────────────── degraded path: act raises → swallowed ─────────────────────────
section("a raising act_fn is swallowed (model down → self-heal)")
def _boom(events): raise RuntimeError("model down")
t = CognitiveTick(lambda: [ev(0.9)], _boom)
try:
    t.beat()
    check("beat did not propagate the exception", True)
except Exception as e:
    check("beat did not propagate the exception", False, repr(e))
check("action not counted on failure", t.actions == 0)

# drain itself raising must also be safe
t2 = CognitiveTick(lambda: (_ for _ in ()).throw(ValueError("boom")), lambda e: None)
try:
    t2.beat(); check("a raising drain_fn is swallowed", True)
except Exception as e:
    check("a raising drain_fn is swallowed", False, repr(e))

# ───────────────────────── due intents fire without a model ─────────────────────────
section("due intents fire (temporal agency, no model)")
fired = []
t = CognitiveTick(lambda: [], None,
                  due_fn=lambda: ["remind-1", "remind-2"], fire_fn=fired.append)
t.beat()
check("every due intent fired", fired == ["remind-1", "remind-2"] and t.fires == 2)

# ───────────────────────── idle reflection hook cadence ─────────────────────────
section("idle hook runs once every idle_every empty beats")
ticks = {"n": 0}
t = CognitiveTick(lambda: [], None, idle_fn=lambda: ticks.__setitem__("n", ticks["n"] + 1),
                  idle_every=3)
for _ in range(6):
    t.beat()
check("idle hook fired twice over six empty beats", ticks["n"] == 2, f"n={ticks['n']}")

# ───────────────────────── LK_TICK=0 disables beats ─────────────────────────
section("LK_TICK=0 disables the tick (config parity)")
os.environ["LK_TICK"] = "0"
check("enabled() reflects the flag", enabled() is False)
acts = {"n": 0}
t = CognitiveTick(lambda: [ev(0.9)], lambda e: acts.__setitem__("n", acts["n"] + 1))
t.beat()
check("no action while disabled", acts["n"] == 0 and t.beats == 0)
os.environ.pop("LK_TICK", None)

# ───────────────────────── lifecycle: start/stop is clean ─────────────────────────
section("start()/stop() lifecycle")
seen = {"n": 0}
t = CognitiveTick(lambda: [ev(0.9)], lambda e: seen.__setitem__("n", seen["n"] + 1),
                  interval=0.02)
t.start()
time.sleep(0.12)
t.stop()
t.join(timeout=1.0)
check("thread stopped cleanly", not t.is_alive())
check("it beat at least once while running", seen["n"] >= 1, f"n={seen['n']}")

# ───────────────────────── summary ─────────────────────────
section("RESULT")
if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\n  ALL COGNITIVE-TICK CHECKS PASSED")
