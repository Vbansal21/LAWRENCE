"""Notification storm control + window-probe caching (host process-bloat fix).

The Windows host showed 100+ aspnet_compiler.exe + powershells + msiexec after a
run. Root cause: every desktop notification spawned a fresh powershell.exe that
loads System.Windows.Forms (→ .NET compiler/installer cascade), and the vision
observer re-spawned a WinForms-loading powershell on every poll. These tests pin
the fix: notify dedupes/throttles/caps the spawns, and screen_windows() caches.

Typed contract (input → output · when it fires · when it must NOT):
  notify(title, body):
    - input:  title/body strings; gated by policy + dedupe/throttle/cap.
    - output: True iff a balloon was actually spawned this call, else False.
    - FIRES a spawn:    first call, or after the throttle window, under the cap,
                        for a not-recently-seen (title,body).
    - must NOT spawn:   identical (title,body) within dedupe window · within the
                        throttle interval · when >= _MAX_INFLIGHT balloons alive.
  screen_windows(force=False):
    - FIRES a probe:    first call, after TTL expiry, or force=True.
    - must NOT probe:   within the TTL of the previous probe (returns the cache).
"""
import sys

sys.path.insert(0, "services")

from lk import debuglog
from lk import notify as N
from lk.obs import regions as R

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond:
        FAILS.append(name)
def section(t): print(f"\n=== {t} ===")


class FakeProc:
    """Stand-in for a powershell.exe balloon process with controllable liveness."""
    def __init__(self): self.alive = True
    def poll(self): return None if self.alive else 0


def install_notify_fakes():
    """Force the powershell branch and capture spawns without touching the OS."""
    spawned = []
    N.subprocess.Popen = lambda *a, **k: spawned.append(FakeProc()) or spawned[-1]  # type: ignore
    N.shutil.which = lambda name: "/fake/powershell.exe" if name == "powershell.exe" else None  # type: ignore
    # allow notifications regardless of ambient policy state
    class _Dec:
        allowed = True
        reason = "test"
    class _Pol:
        @staticmethod
        def current():
            return type("P", (), {"allow": staticmethod(lambda _kind: _Dec())})
    N.PolicyState = _Pol  # type: ignore
    N.audit = lambda *a, **k: None  # type: ignore
    # reset gate state
    N._last_fired = 0.0
    N._recent.clear()
    N._inflight.clear()
    return spawned


section("A. notify dedupe — identical (title,body) within the window spawns once")
debuglog.reset()
spawned = install_notify_fakes()
N._MIN_INTERVAL_S, N._DEDUPE_S, N._MAX_INFLIGHT = 0.0, 100.0, 99
r1 = N.notify("Finding", "the same thing")
r2 = N.notify("Finding", "the same thing")
check("first identical notify spawns + returns True", r1 is True and len(spawned) == 1)
check("second identical notify is deduped (no spawn, returns False)", r2 is False and len(spawned) == 1)
check("dedupe counter incremented", debuglog.snapshot().get("notify.deduped", 0) >= 1)


section("B. notify throttle — distinct messages too close together are spaced out")
spawned = install_notify_fakes()
N._MIN_INTERVAL_S, N._DEDUPE_S, N._MAX_INFLIGHT = 100.0, 0.0, 99
a = N.notify("A", "1")
b = N.notify("B", "2")      # distinct (dedupe off) but within the throttle window
check("first notify spawns", a is True and len(spawned) == 1)
check("second notify within interval is throttled", b is False and len(spawned) == 1)


section("C. notify cap — never more than _MAX_INFLIGHT live balloons at once")
spawned = install_notify_fakes()
N._MIN_INTERVAL_S, N._DEDUPE_S, N._MAX_INFLIGHT = 0.0, 0.0, 2
results = [N.notify(f"T{i}", f"b{i}") for i in range(4)]
check("cap holds spawns at _MAX_INFLIGHT", len(spawned) == 2, f"spawned={len(spawned)}")
check("over-cap calls return False", results.count(False) == 2)
# now let the live ones finish → the cap frees up and a new balloon may spawn
for p in spawned:
    p.alive = False
freed = N.notify("T-after", "b-after")
check("finished balloons are reaped so new ones can spawn", freed is True and len(spawned) == 3)


section("D. screen_windows() caches within TTL, re-probes after force/expiry")
probes = {"n": 0}
def fake_probe():
    probes["n"] += 1
    return ([], (0, 0, 100, 100))
R._powershell_windows = fake_probe          # type: ignore
R._wmctrl_windows = lambda: None            # type: ignore
R._SW_TTL = 100.0
R._sw_cache = None
R.screen_windows()
R.screen_windows()
check("second call within TTL reuses the cache (one probe)", probes["n"] == 1, f"probes={probes['n']}")
R.screen_windows(force=True)
check("force=True bypasses the cache (re-probes)", probes["n"] == 2)
R._SW_TTL = 0.0
R._sw_cache = None
R.screen_windows()
R.screen_windows()
check("TTL=0 disables caching (probes every call)", probes["n"] == 4)


print()
if FAILS:
    print(f"  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("  ALL NOTIFY/REGIONS BLOAT-CONTROL CHECKS PASSED")
