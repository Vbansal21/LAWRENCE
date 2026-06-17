"""§8 — durable scheduler + reminders (WS-T).

Reminders must fire exactly once, survive restarts without double-firing, parse
time explicitly, and drive the tick's due/fire hooks with NO model call.
"""
import sys, tempfile, shutil
sys.path.insert(0, "services")
from pathlib import Path
from datetime import datetime, timezone, timedelta

FAILS = []
def check(name, cond, extra=""):
    print(f"  [{'ok' if cond else 'XX'}] {name}" + (f"  ({extra})" if extra and not cond else ""))
    if not cond:
        FAILS.append(name)

from lk.schedule import Schedule, ScheduleError, parse_when

tmp = Path(tempfile.mkdtemp())
path = tmp / "schedule.jsonl"

def now():
    return datetime.now(timezone.utc)

# ── add / list / done ─────────────────────────────────────────────────────────
print("\n§8 add / list / done")
s = Schedule(path=path)
r = s.add("drink water", "+1h")
check("add returns a pending record with an id", r["status"] == "pending" and r["id"].startswith("rem-"))
check("list shows the reminder", any(x["id"] == r["id"] for x in s.list()))
check("counts: one pending", s.counts()["pending"] == 1)
check("future reminder is not yet due", s.due() == [])
check("done() dismisses a pending reminder", s.done(r["id"]) is True)
check("dismissed reminder leaves pending", s.counts()["pending"] == 0 and s.counts()["done"] == 1)
check("done() on an already-terminal reminder is a no-op", s.done(r["id"]) is False)

# ── invalid time → specific error ─────────────────────────────────────────────
print("\n§8 invalid time")
try:
    s.add("bad", "not-a-time")
    check("invalid time raises", False, "no exception")
except ScheduleError:
    check("invalid time raises ScheduleError", True)
try:
    s.add("", "+1h")
    check("empty text raises", False)
except ScheduleError:
    check("empty text raises ScheduleError", True)
check("parse_when is timezone-aware (ISO without offset → local tz attached)",
      parse_when("2026-06-18T09:00").tzinfo is not None)
check("parse_when honors an explicit offset", parse_when("2026-01-01T00:00+05:30").utcoffset() == timedelta(hours=5, minutes=30))

# ── due fires once ────────────────────────────────────────────────────────────
print("\n§8 due fires exactly once")
s2 = Schedule(path=tmp / "fire.jsonl")
due_r = s2.add("ping", "+0s")   # already due
first = s2.due()
check("a past/now reminder is due", len(first) == 1 and first[0]["id"] == due_r["id"])
fired = s2.mark_fired(due_r["id"])
check("mark_fired returns the fired record", fired is not None and fired["status"] == "fired")
check("after firing it is no longer due", s2.due() == [])
check("mark_fired is idempotent (second call → None, no double-fire)", s2.mark_fired(due_r["id"]) is None)

# ── past-due on startup + restart simulation ─────────────────────────────────
print("\n§8 restart does not double-fire")
restart_path = tmp / "restart.jsonl"
sa = Schedule(path=restart_path)
past = sa.add("overdue", now().isoformat())   # due immediately
# simulate a kernel restart BEFORE firing: a fresh store from the same log
sb = Schedule(path=restart_path)
due_after_restart = sb.due()
check("past-due reminder is due after a restart", len(due_after_restart) == 1)
check("the same fire-once guard holds across restart instances", sb.mark_fired(past["id"]) is not None)
# now a SECOND restart AFTER firing — must not re-fire
sc = Schedule(path=restart_path)
check("restart after firing does not re-surface the reminder", sc.due() == [])
check("fired state is durable across restart", sc.counts()["fired"] == 1)

# ── tick integration: due/fire drive the tick with NO model call ─────────────
print("\n§8 tick fires due reminders without a model call")
import lk.model as M
from lk.kernel.tick import CognitiveTick

_model_calls = {"n": 0}
_orig_call = M.call_model
def _counting_call(*a, **k):
    _model_calls["n"] += 1
    return {"text": ""}
M.call_model = _counting_call
try:
    st = Schedule(path=tmp / "tick.jsonl")
    st.add("standup", "+0s")     # due now
    fired_texts = []
    def fire(intent):
        st.mark_fired(intent["id"])
        fired_texts.append(intent["text"])
    tick = CognitiveTick(
        drain_fn=lambda: [],            # no perception events this beat
        act_fn=lambda events: None,     # would call the model — must NOT run
        due_fn=st.due,
        fire_fn=fire,
    )
    tick.beat()                          # one synchronous beat
    check("tick fired the due reminder", fired_texts == ["standup"], f"{fired_texts}")
    check("tick.fires counter advanced", tick.fires == 1)
    check("tick made ZERO model calls on the due path", _model_calls["n"] == 0, f"calls={_model_calls['n']}")
    tick.beat()                          # second beat — already fired
    check("a later beat does not re-fire", fired_texts == ["standup"], f"{fired_texts}")
finally:
    M.call_model = _orig_call

shutil.rmtree(tmp, ignore_errors=True)

if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\nALL SCHEDULE CHECKS PASSED")
