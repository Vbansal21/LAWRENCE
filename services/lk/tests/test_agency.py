"""Allowlisted proposals require one-use confirmation before state changes."""
import tempfile
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, "services")

import lk.policy as policy
from lk.agency import Agency
from lk.schedule import Schedule
from lk.tasks import TaskStore


root = Path(tempfile.mkdtemp(prefix="lk-agency-"))
old_audit = policy.AUDIT_PATH
policy.AUDIT_PATH = root / "policy.jsonl"
try:
    tasks = TaskStore(root / "tasks.json")
    schedule = Schedule(root / "schedule.jsonl")
    agency = Agency(tasks, schedule, log_path=root / "actions.jsonl",
                    artifact_dir=root / "artifacts")

    proposed = agency.propose(
        [{"operation": "task.add", "text": "Review the retrieval report"}], 7)
    assert len(proposed) == 1
    action = proposed[0]
    assert tasks.snapshot()["counts"]["open"] == 0

    try:
        agency.decide(action["id"], confirm=True, token="wrong")
        raise AssertionError("wrong token executed")
    except ValueError:
        pass
    assert tasks.snapshot()["counts"]["open"] == 0

    done = agency.decide(
        action["id"], confirm=True, token=action["confirmationToken"])
    assert done["status"] == "done"
    assert tasks.snapshot()["counts"]["open"] == 1
    try:
        agency.decide(action["id"], confirm=True, token=action["confirmationToken"])
        raise AssertionError("one-use token executed twice")
    except ValueError:
        pass

    artifact = agency.propose([{
        "operation": "artifact.write",
        "name": "../../report",
        "content": "# Retrieval report\n\nVerified.",
    }], 8)[0]
    result = agency.decide(
        artifact["id"], confirm=True, token=artifact["confirmationToken"])
    artifact_path = Path(result["result"]["path"])
    assert artifact_path.parent == root / "artifacts"
    assert artifact_path.name == "report.md"

    due = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    reminder = agency.propose([{
        "operation": "reminder.add", "text": "Check the MVP", "when": due,
    }], 9)[0]
    agency.decide(reminder["id"], confirm=False)
    assert schedule.counts()["pending"] == 0

    assert len((root / "actions.jsonl").read_text().splitlines()) == 6
    assert '"operation":"external_action"' in policy.AUDIT_PATH.read_text()
    print("AGENCY: PASS")
finally:
    policy.AUDIT_PATH = old_audit
