#!/usr/bin/env python3
"""Prove model proposal, explicit confirmation, and one safe state change."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))

import lk.logger as logger
import lk.policy as policy
from lk.agency import Agency
from lk.config import apply_to_env
from lk.ctx.store import ContextStore
from lk.kernel.invoke import TurnConfig, run_turn
from lk.retrieval.db import SemanticDB
from lk.retrieval.memory import MemoryIndex
from lk.retrieval.pipeline import RetrievalPipeline
from lk.schedule import Schedule
from lk.tasks import TaskStore


class NullUI:
    def push_status(self, *_args, **_kwargs):
        pass

    def push_response(self, *_args, **_kwargs):
        pass


def main() -> int:
    apply_to_env()
    with tempfile.TemporaryDirectory(prefix="lk-agency-smoke-") as directory:
        root = Path(directory)
        old_log, old_audit = logger._LOG_DIR, policy.AUDIT_PATH
        logger._LOG_DIR = root / "logs"
        policy.AUDIT_PATH = root / "policy.jsonl"
        db = SemanticDB(root / "retrieval.db")
        memory = MemoryIndex(root / "index.db")
        try:
            agency = Agency(
                TaskStore(root / "tasks.json"),
                Schedule(root / "schedule.jsonl"),
                log_path=root / "actions.jsonl",
                artifact_dir=root / "artifacts",
            )
            _, controls = run_turn(
                "Create a proposal to write agency-smoke.md containing exactly: # Agency works",
                ctx=ContextStore(mem_dir=root / "context"),
                retrieval=RetrievalPipeline(db),
                memory=memory,
                cfg=TurnConfig(skip_analysis=True, no_retrieval=True, max_tokens=512),
                images=[],
                audios=[],
                ui=NullUI(),
                actions_fn=agency.propose,
            )
            proposals = controls.get("actionProposals") or []
            if len(proposals) != 1:
                raise RuntimeError("model did not emit exactly one action proposal")
            proposal = proposals[0]
            if (root / "artifacts").exists():
                raise RuntimeError("proposal changed state before confirmation")
            result = agency.decide(
                proposal["id"], confirm=True,
                token=proposal["confirmationToken"],
            )
            path = Path(result["result"]["path"])
            if path.read_text(encoding="utf-8") != "# Agency works":
                raise RuntimeError("confirmed artifact content mismatch")
            try:
                agency.decide(
                    proposal["id"], confirm=True,
                    token=proposal["confirmationToken"],
                )
                raise RuntimeError("confirmation token was reusable")
            except ValueError:
                pass
            print(f"AGENCY SMOKE: PASS ({proposal['operation']} -> {path.name})")
            return 0
        finally:
            memory.close()
            db.close()
            logger._LOG_DIR, policy.AUDIT_PATH = old_log, old_audit


if __name__ == "__main__":
    raise SystemExit(main())
