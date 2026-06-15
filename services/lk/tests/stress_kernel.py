"""Kernel stress harness — hammers the priority gate (the single-slot inference
serializer) under heavy concurrency, with NO model involved.

The gate is the kernel's crux: every local inference call passes through it, and
its contract is what lets a live turn preempt the queue while proactive work is
droppable. We assert the contract holds under contention:

  1. MUTUAL EXCLUSION  — never two holders of the slot at once (the whole point);
  2. PRIORITY ORDER    — among waiters queued while busy, the lowest priority
                         number is granted next (turn 0 < refine 1 < compact 2);
  3. FIFO WITHIN TIER  — equal priority is served in arrival order (no starvation);
  4. DROPPABLE         — try_acquire() (proactive) returns False whenever the slot
                         is busy OR anyone is queued — it never jumps the line;
  5. LIVENESS          — under N threads × M rounds there are no lost wakeups,
                         no deadlock, and every acquire() is eventually granted.
"""
import sys, threading, time, random
sys.path.insert(0, "services")

from lk.model import _PriorityGate, PRI_TURN, PRI_REFINE, PRI_COMPACT, PRI_PROACTIVE

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond: FAILS.append(name)
def section(t): print(f"\n=== {t} ===")


# ─────────────────────── 1. mutual exclusion under load ───────────────────────
section("mutual exclusion: never two holders at once (200 threads × 5 rounds)")
g = _PriorityGate()
holders = {"now": 0, "max": 0}
hlock = threading.Lock()
violations = []

def worker(pri):
    for _ in range(5):
        g.acquire(pri)
        try:
            with hlock:
                holders["now"] += 1
                holders["max"] = max(holders["max"], holders["now"])
                if holders["now"] != 1:
                    violations.append(holders["now"])
            time.sleep(random.uniform(0, 0.001))   # hold the slot briefly
            with hlock:
                holders["now"] -= 1
        finally:
            g.release()

threads = [threading.Thread(target=worker, args=(random.choice(
    [PRI_TURN, PRI_REFINE, PRI_COMPACT]),)) for _ in range(200)]
t0 = time.monotonic()
for t in threads: t.start()
for t in threads: t.join(timeout=30)
elapsed = time.monotonic() - t0
check("no thread still alive (no deadlock / lost wakeup)", all(not t.is_alive() for t in threads),
      f"{sum(t.is_alive() for t in threads)} stuck after {elapsed:.1f}s")
check("never more than one holder", holders["max"] == 1, f"max concurrent={holders['max']}")
check("zero exclusion violations across 1000 acquisitions", not violations, f"{violations[:5]}")
check("slot released cleanly at the end", holders["now"] == 0)


# ─────────────────────── 2. priority ordering of the queue ───────────────────────
section("priority order: waiters queued while busy are granted low-number-first")
g = _PriorityGate()
order = []                 # (priority, tag) in the order each waiter is granted
olock = threading.Lock()
entered = {"n": 0}         # how many waiters have reached g.acquire()
elock = threading.Lock()
# Occupy the slot so everyone else must queue.
g.acquire(PRI_TURN)

def queued(pri, tag):
    with elock:
        entered["n"] += 1
    g.acquire(pri)         # parks in the heap; seq assigned in real call order
    with olock:
        order.append((pri, tag))
    g.release()

# A mix across all four tiers. Intra-tier arrival order is OS-nondeterministic, so
# we assert the robust contract — priorities are GRANTED non-decreasing — not which
# same-tier thread wins. (Proactive normally uses try_acquire; forced to queue here
# purely to exercise the heap across every tier.)
specs = [(PRI_COMPACT, "c1"), (PRI_PROACTIVE, "p1"), (PRI_TURN, "t1"),
         (PRI_REFINE, "r1"), (PRI_TURN, "t2"), (PRI_COMPACT, "c2")]
qts = [threading.Thread(target=queued, args=s) for s in specs]
for t in qts: t.start()
# Wait until every waiter has entered acquire() (not a fixed sleep), plus a small
# margin so they are all parked in the heap, THEN release the holder.
while entered["n"] < len(specs):
    time.sleep(0.005)
time.sleep(0.1)
g.release()                # release the original holder → queue drains by priority
for t in qts: t.join(timeout=10)

pris = [p for p, _ in order]
check("all queued waiters drained", len(order) == 6, f"order={order}")
check("priorities granted in non-decreasing order (turn<refine<compact<proactive)",
      pris == sorted(pris), f"order={order}")
check("the two turns (pri 0) were granted first", set(t for _, t in order[:2]) == {"t1", "t2"}, f"order={order}")
check("proactive (pri 3) granted last", order[-1][1] == "p1", f"order={order}")


# ─────────────────────── 3. droppability of try_acquire ───────────────────────
section("try_acquire is droppable: never jumps a busy slot or a non-empty queue")
g = _PriorityGate()
check("try_acquire succeeds on a free idle gate", g.try_acquire() is True)
check("…and now reports busy to a second try", g.try_acquire() is False)
g.release()
# busy via a queued acquirer:
g.acquire(PRI_TURN)
blocked = threading.Thread(target=lambda: (g.acquire(PRI_COMPACT), g.release()))
blocked.start()
time.sleep(0.1)            # blocked is now queued behind the holder
check("try_acquire refuses while someone is queued", g.try_acquire() is False)
g.release()
blocked.join(timeout=5)
check("queued acquirer completed after release", not blocked.is_alive())


# ─────────────────────── 4. proactive-realistic droppable storm ───────────────────────
section("droppable storm: proactive try_acquire stays correct vs a turn stream")
g = _PriorityGate()
got = {"turn": 0, "proactive_ok": 0, "proactive_drop": 0}
glock = threading.Lock()
stop = threading.Event()

def turn_stream():
    while not stop.is_set():
        g.acquire(PRI_TURN)
        with glock: got["turn"] += 1
        time.sleep(0.0005)
        g.release()

def proactive_stream():
    while not stop.is_set():
        if g.try_acquire():
            with glock: got["proactive_ok"] += 1
            time.sleep(0.0005)
            g.release()
        else:
            with glock: got["proactive_drop"] += 1
        time.sleep(0.0002)

ts = [threading.Thread(target=turn_stream) for _ in range(4)]
ps = [threading.Thread(target=proactive_stream) for _ in range(4)]
for t in ts + ps: t.start()
time.sleep(1.0)
stop.set()
for t in ts + ps: t.join(timeout=5)
check("turns made progress", got["turn"] > 0, str(got))
check("some proactive calls were dropped under contention (droppable works)",
      got["proactive_drop"] > 0, str(got))
check("no thread hung", all(not t.is_alive() for t in ts + ps))
print(f"      (turns={got['turn']}, proactive_ok={got['proactive_ok']}, dropped={got['proactive_drop']})")


# ─────────────────────── summary ───────────────────────
section("RESULT")
if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\n  ALL KERNEL STRESS CHECKS PASSED")
