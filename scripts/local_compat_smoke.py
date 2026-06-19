#!/usr/bin/env python3
"""Exercise LAWRENCE's core contracts against the bundled local model."""
from __future__ import annotations

import json
import random
import statistics
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))

from lk import model, server  # noqa: E402
from lk.ctx import ContextStore  # noqa: E402
from lk.kernel import TurnConfig, run_turn  # noqa: E402
from lk.kernel import prompts, schemas  # noqa: E402
from lk.profile import ModelProfile  # noqa: E402
from lk.retrieval import RetrievalPipeline, SemanticDB  # noqa: E402
from lk.ui import UIConnector  # noqa: E402


def call(name: str, role: str, prompt: str, schema: dict, body: str,
         timings: list[float]) -> dict:
    started = time.monotonic()
    raw = model.call_model(
        [{"role": "system", "content": prompt}, {"role": "user", "content": body}],
        schema=schema, role=role, max_tokens=384, temperature=0, timeout=180,
    )["text"]
    elapsed = time.monotonic() - started
    parsed = json.loads(raw)
    missing = [key for key in schema.get("required", []) if key not in parsed]
    if missing:
        raise RuntimeError(f"{name} missing required keys: {missing}")
    timings.append(elapsed)
    print(f"  PASS  {name:<18} {elapsed:6.2f}s")
    return parsed


def main() -> int:
    profile = ModelProfile.detect(
        model=ROOT / "models/local/gemma-4-E4B-it-GGUF/gemma-4-E4B-it-Q4_K_M.gguf",
        bin_path=ROOT / "third_party/llama.cpp/build/bin/llama-server",
    )
    started_server = not server.health_check()
    if started_server:
        server.start(profile, wait_secs=180)
    model.configure_backend(kind="local", base_url="", model=None, provider="local")
    model.clear_routing()
    timings: list[float] = []
    try:
        cases = [
            ("analysis", "analysis", prompts.ANALYSIS, schemas.ANALYSIS,
             "[CONTEXT] Editing the MVP plan.\nUSER QUESTION: What remains?"),
            ("retrieval plan", "retrieve", prompts.RETRIEVAL_PLAN, schemas.RETRIEVAL_PLAN,
             "CURRENT: local compatibility work. NEED: recall prior project decisions."),
            ("sensor extract", "extract", prompts.EXTRACT, schemas.EXTRACT,
             "VS Code shows LAWRENCE PLAN.md at N-42 local compatibility."),
            ("proactive", "proactive", prompts.PROACTIVE, schemas.PROACTIVE,
             "The context is quiet and no external information is needed."),
            ("journal", "journal", prompts.JOURNAL_DRAFT, schemas.JOURNAL_DRAFT,
             "RECENT ENTRIES: none\nLIVE CONTEXT: I completed a local model check."),
        ]
        for args in cases:
            call(*args, timings)

        chunks: list[str] = []
        started = time.monotonic()
        try:
            model.call_model(
                [{"role": "user", "content": "Count slowly from one to one hundred."}],
                role="response", max_tokens=128, timeout=60,
                stream_fn=chunks.append, should_stop=lambda: len(chunks) >= 3,
            )
            raise RuntimeError("local streaming turn ignored cancellation")
        except model.TurnCancelled:
            elapsed = time.monotonic() - started
            timings.append(elapsed)
            print(f"  PASS  cancellation       {elapsed:6.2f}s")

        replay = [
            "The MVP must stay local-first.",
            "The UI now uses durable backend state.",
            "The next frontier is local model compatibility.",
        ]
        boundary = random.Random(42).randrange(1, len(replay) + 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ctx = ContextStore(mem_dir=root / "memory")
            for text in replay[:boundary]:
                ctx.append(ts=datetime.now(timezone.utc).isoformat(), kind="turn",
                           compact=text, detailed=text)
            db = SemanticDB(root / "retrieval.db")
            try:
                started = time.monotonic()
                answer, controls = run_turn(
                    "Reply briefly and propose artifact.write for local-check.md containing 'local mode works'.",
                    ctx=ctx, retrieval=RetrievalPipeline(db),
                    cfg=TurnConfig(no_retrieval=True, skip_analysis=True, max_tokens=384,
                                   timeout=180, allow_images=False, allow_audio=False),
                    images=[], audios=[], ui=UIConnector(),
                    actions_fn=lambda actions, _version: actions,
                )
                elapsed = time.monotonic() - started
                timings.append(elapsed)
                if not answer.strip():
                    raise RuntimeError("random-boundary turn returned an empty answer")
                proposals = controls.get("actionProposals") or []
                if not any(item.get("operation") == "artifact.write" for item in proposals):
                    raise RuntimeError("random-boundary turn lost its agency proposal")
                print(f"  PASS  random turn {boundary}/3    {elapsed:6.2f}s")
            finally:
                db.close()

        ordered = sorted(timings)
        report = {
            "ok": True,
            "backend": model.describe_backend(),
            "profile": profile.summary(),
            "cases": len(timings),
            "randomBoundary": boundary,
            "latencySeconds": {
                "p50": round(statistics.median(ordered), 2),
                "p95": round(ordered[max(0, int(len(ordered) * 0.95) - 1)], 2),
                "max": round(max(ordered), 2),
            },
        }
        path = ROOT / ".runtime" / "local-compat-report.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0
    finally:
        if started_server:
            server.stop()


if __name__ == "__main__":
    raise SystemExit(main())
