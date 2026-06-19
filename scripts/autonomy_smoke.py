#!/usr/bin/env python3
"""Run one live perception-to-finding cycle without a user turn."""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))

from lk.config import apply_to_env
from lk import admin
from lk.ctx.store import ContextStore
from lk.kernel.invoke import run_proactive
from lk.kernel.journal import run_journal
from lk.kernel.tick import CognitiveTick
from lk.retrieval.engine import GatherResult
from lk.retrieval.memory import MemoryIndex
from lk.retrieval.pipeline import CitedResult


class ControlledEvidence:
    def gather(self, *_args, **_kwargs):
        evidence = CitedResult(
            1,
            "https://docs.perplexity.ai/docs/search/quickstart",
            "Perplexity Search API",
            "A reliable search provider returns ranked structured results and explicit "
            "source metadata. Configure a supported provider instead of silently "
            "accepting empty fresh-web retrieval.",
            "web",
        )
        return GatherResult(
            context_understanding="fresh web provider outage",
            evidence=[evidence],
            queries={"web": ["reliable search provider"]},
            iterations=1,
        )


def main() -> int:
    apply_to_env()
    with tempfile.TemporaryDirectory(prefix="lk-autonomy-smoke-") as directory:
        root = Path(directory)
        old_dirs = (admin._MEM_DIR, admin._JOURNAL_DIR, admin._LOGS_DIR)
        admin._MEM_DIR = root
        admin._JOURNAL_DIR = root / "journal"
        admin._LOGS_DIR = root / "logs"
        context = ContextStore(mem_dir=root)
        memory = MemoryIndex(root / "index.db")
        try:
            context.append(
                datetime.now(timezone.utc).isoformat(),
                "vision",
                "[VISION] retrieval provider degraded",
                "LAWRENCE fresh web retrieval is degraded because DDG is bot-blocked "
                "and no reliable provider is configured.",
            )

            findings = []
            outcomes = []

            def act(_events):
                outcomes.append(run_proactive(
                    context,
                    retrieval=None,
                    engine=ControlledEvidence(),
                    memory=memory,
                    present_fn=findings.append,
                ))

            pending = [[{"clean": "fresh web provider degraded", "significance": 0.95, "tier": 2}]]
            tick = CognitiveTick(lambda: pending.pop(0) if pending else [], act)
            tick.beat()
            journal_title = run_journal(context, memory=memory)

            stats = memory.stats()
            if tick.actions != 1 or outcomes != [True] or len(findings) != 1:
                raise RuntimeError("cognitive tick did not complete one autonomous finding")
            if stats["by_kind"].get("finding") != 1:
                raise RuntimeError("autonomous finding was not indexed")
            if "[PROACTIVE FINDING]" not in context.tail_for_model():
                raise RuntimeError("autonomous finding was not persisted")
            if not journal_title or stats["by_kind"].get("journal") != 1:
                raise RuntimeError("autonomous journal was not written and indexed")
            print(f"AUTONOMY SMOKE: PASS ({findings[0]['headline']}; journal={journal_title})")
        finally:
            memory.close()
            admin._MEM_DIR, admin._JOURNAL_DIR, admin._LOGS_DIR = old_dirs
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
