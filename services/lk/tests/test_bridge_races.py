"""Concurrency / feature-conflict harness for the desktop bridge.

The bridge runs under ThreadingHTTPServer (one thread per request), so two UI
actions fired within K milliseconds execute concurrently. This suite answers the
user's question directly: "if I press button X then immediately button W within K
seconds, will it hold?"

Typed contract (the invariant that must survive any toggle storm):

  INPUT    a storm of concurrent set_observer / set_voice_listen calls (random
           on/off, overlapping in time) from many threads.
  OUTPUT   NO leaked observer — the number of started-but-not-stopped fake
           observers always equals (1 if the bridge thinks it's on else 0).
           Exactly one proactive run is ever in flight (no double-spawn).
  WHEN OK  every lifecycle transition serializes through the observer lock.
  WHEN FAIL (pre-fix) interleaved check-then-act leaks a running observer while
           self.vision/self.audio is None (the bloat class).

Pure stdlib, offline. Fake observers (no screen/mic). No model, no server.
"""
import importlib.util
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, "services")

FAILS: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    print(f"{'PASS' if cond else 'FAIL'}: {name}" + (f"  [{extra}]" if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


# ── load the bridge module by path (it lives outside the lk package) ──────────
_bridge_path = Path("apps/desktop/scripts/ui_bridge.py").resolve()
spec = importlib.util.spec_from_file_location("ui_bridge", _bridge_path)
UB = importlib.util.module_from_spec(spec)
spec.loader.exec_module(UB)


class _Live:
    """Global start/stop ledger shared by all fake observers."""
    lock = threading.Lock()
    started = 0
    stopped = 0

    @classmethod
    def reset(cls):
        with cls.lock:
            cls.started = cls.stopped = 0

    @classmethod
    def live(cls):
        with cls.lock:
            return cls.started - cls.stopped


class FakeObserver:
    def __init__(self, *a, **k):
        self._on = False

    def start(self):
        # tiny sleep widens the race window the lock must close
        time.sleep(0.0005)
        with _Live.lock:
            _Live.started += 1
        self._on = True

    def stop(self):
        time.sleep(0.0005)
        with _Live.lock:
            _Live.stopped += 1
        self._on = False


class _NullUI:
    def push_status(self, *a, **k): pass
    def push_voice(self, *a, **k): pass
    def push_context_event(self, *a, **k): pass
    def _push(self, *a, **k): pass


def _bare_bridge():
    """A bridge with ONLY the fields the lifecycle paths touch (skip __init__)."""
    b = UB.DesktopBridge.__new__(UB.DesktopBridge)
    b._observer_lock = threading.RLock()
    b._proactive_lock = threading.Lock()
    b.vision = None
    b.audio = None
    b.voice_enabled = False
    b._voice_config = {}
    b.proactive_enabled = True
    b.tmp_path = Path("/tmp")
    b.ctx = None
    b.ui = _NullUI()
    b._voice_pending = None
    b._voice_pending_lock = threading.Lock()
    b.proactive_interval = 600.0
    b._last_proactive = 0.0
    b._proactive_busy = False
    return b


# patch the observer classes the bridge instantiates
UB.VisionObserver = FakeObserver
UB.AudioObserver = FakeObserver

# ── A — vision toggle storm: on/off from many threads, no leak ────────────────
_Live.reset()
b = _bare_bridge()
N = 60


def storm_vision(i):
    for j in range((i % 3) + 1):
        b.set_observer({"observer": "vision", "enabled": (i + j) % 2 == 0})
        time.sleep(0.0003)


threads = [threading.Thread(target=storm_vision, args=(i,)) for i in range(N)]
for t in threads:
    t.start()
for t in threads:
    t.join()
expected = 1 if b.vision else 0
check("A vision storm leaks no observer", _Live.live() == expected,
      f"live={_Live.live()} expected={expected} (self.vision={'set' if b.vision else 'None'})")

# settle: turn off, must end at zero live
b.set_observer({"observer": "vision", "enabled": False})
check("A2 vision off settles to zero live", _Live.live() == 0, f"live={_Live.live()}")

# ── B — audio toggle storm via BOTH entry points (set_observer + voice) ───────
_Live.reset()
b = _bare_bridge()


def storm_audio(i):
    if i % 2 == 0:
        b.set_observer({"observer": "audio", "enabled": i % 4 == 0})
    else:
        b.set_voice_listen({"enabled": i % 3 == 0, "config": {}})
    time.sleep(0.0003)


threads = [threading.Thread(target=storm_audio, args=(i,)) for i in range(N)]
for t in threads:
    t.start()
for t in threads:
    t.join()
expected = 1 if b.audio else 0
check("B audio storm across both controls leaks no observer",
      _Live.live() == expected, f"live={_Live.live()} expected={expected}")
b.set_observer({"observer": "audio", "enabled": False})
b.set_voice_listen({"enabled": False, "config": {}})
check("B2 audio off settles to zero live", _Live.live() == 0, f"live={_Live.live()}")

# ── C — idempotence: redundant 'on' / 'off' never double-acts ─────────────────
_Live.reset()
b = _bare_bridge()
r1 = b.set_observer({"observer": "vision", "enabled": True})
r2 = b.set_observer({"observer": "vision", "enabled": True})   # already on
check("C1 first 'on' reports changed", r1["changed"] is True)
check("C2 redundant 'on' reports not-changed", r2["changed"] is False)
check("C3 redundant 'on' did not start a second observer", _Live.live() == 1)
r3 = b.set_observer({"observer": "vision", "enabled": False})
r4 = b.set_observer({"observer": "vision", "enabled": False})  # already off
check("C4 redundant 'off' reports not-changed", r4["changed"] is False and r3["changed"] is True)
check("C5 settled to zero", _Live.live() == 0)

# ── D — proactive trigger never double-spawns under concurrent events ─────────
b = _bare_bridge()
b._last_proactive = -10_000.0     # ensure the interval gate is open
spawned = {"n": 0}
spawn_lock = threading.Lock()
_real_thread = threading.Thread


class _CountingThread(_real_thread):
    def start(self):
        # Count the spawn but LEAVE the slot claimed (busy stays True), simulating
        # an in-flight run_proactive — so any concurrent caller must see busy and
        # skip. Exactly one spawn may occur for the whole storm.
        with spawn_lock:
            spawned["n"] += 1


UB.threading.Thread = _CountingThread
try:
    barrier = threading.Barrier(20)

    def hit():
        barrier.wait()
        b._maybe_proactive()

    # use the REAL Thread class for the test's own threads (UB.threading.Thread is
    # the same shared module object we just patched for _maybe_proactive's spawn).
    ts = [_real_thread(target=hit) for _ in range(20)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    check("D concurrent events spawn proactive at most once", spawned["n"] <= 1,
          f"spawned={spawned['n']}")
finally:
    UB.threading.Thread = _real_thread

print()
if FAILS:
    print(f"FAILED ({len(FAILS)}): " + ", ".join(FAILS))
    sys.exit(1)
print("test_bridge_races OK")
