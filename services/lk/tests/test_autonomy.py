"""Unattended retry contract: failed work never consumes a long cooldown."""
import importlib.util
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, "services")

from lk.kernel.journal import JournalTrigger


def wait_until(done, seconds=2.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if done():
            return
        time.sleep(0.01)
    raise AssertionError("background autonomy attempt did not finish")


bridge_path = Path("apps/desktop/scripts/ui_bridge.py").resolve()
spec = importlib.util.spec_from_file_location("ui_bridge_autonomy", bridge_path)
bridge_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge_module)

bridge = bridge_module.DesktopBridge.__new__(bridge_module.DesktopBridge)
bridge.proactive_interval = 600.0
bridge._last_proactive = 0.0
bridge._proactive_busy = False
bridge.ctx = bridge.retrieval = bridge.engine = bridge.memory = object()
bridge._present_finding = lambda finding: None

class NullUI:
    def push_context_event(self, *_args):
        pass

bridge.ui = NullUI()
attempts = []
outcomes = iter((False, True))
real_run = bridge_module.run_proactive
bridge_module.run_proactive = lambda *_args, **_kwargs: (
    attempts.append(time.monotonic()) or next(outcomes)
)
try:
    bridge._maybe_proactive()
    wait_until(lambda: not bridge._proactive_busy)
    assert bridge._last_proactive == 0.0

    bridge._maybe_proactive()
    wait_until(lambda: not bridge._proactive_busy)
    assert bridge._last_proactive > 0.0

    bridge._maybe_proactive()
    time.sleep(0.05)
    assert len(attempts) == 2
finally:
    bridge_module.run_proactive = real_run


os.environ["LK_JOURNAL_MIN_INTERVAL"] = "0"
clock = [100.0]
writes = iter(("", "written"))
trigger = JournalTrigger(object(), run_fn=lambda *_args, **_kwargs: next(writes),
                         clock=lambda: clock[0])
clock[0] = 500.0
event = [{"tier": 2, "significance": 0.9}]

trigger.beat(event)
wait_until(lambda: not trigger._busy)
assert trigger._last == 100.0
assert trigger._saw_activity is True

trigger.beat(event)
wait_until(lambda: not trigger._busy)
assert trigger._last == 500.0
assert trigger._saw_activity is False
os.environ.pop("LK_JOURNAL_MIN_INTERVAL", None)

print("AUTONOMY RETRY: PASS")
