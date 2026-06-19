#!/usr/bin/env python3
"""Measure the current live LAWRENCE retrieval lanes."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))

from lk.config import apply_to_env
from lk.retrieval import MemoryIndex, RetrievalEngine, SemanticDB
from lk.retrieval.web import search_and_fetch, search_stats


CASES = (
    ("own memory", "notes", "bridgeConnectEvents event connection logic",
     lambda item: item.category == "notes" and "bridgeconnectevents" in item.text.lower()),
    ("current plan", "doc", "Project Soul Anchor bipartite execution DAG",
     lambda item: item.category == "doc" and item.url.endswith("/docs/PLAN.md")),
    ("original paper", "doc", "local first watcher assistant durable memory orchestration continuity",
     lambda item: item.category == "doc" and item.url.endswith("/LAWRENCE_v0_1_ieee.tex")),
    ("cached web", "web", "Manage context for AI VS Code",
     lambda item: item.category == "web" and "code.visualstudio.com" in item.url),
)


def run_case(engine: RetrievalEngine, name: str, category: str, query: str, relevant) -> tuple[int, float]:
    os.environ["LK_RETRIEVAL_CATEGORIES"] = category
    started = time.monotonic()
    result = engine.gather(query, short_ctx="LAWRENCE retrieval smoke", timeout=60)
    elapsed = time.monotonic() - started
    rank = next((index for index, item in enumerate(result.evidence, 1) if relevant(item)), 0)
    print(f"  {name:<14} rank={rank or '-'} results={len(result.evidence)} time={elapsed:.2f}s")
    if not rank:
        raise RuntimeError(f"{name}: expected evidence was not retrieved")
    if [item.citation_num for item in result.evidence] != list(range(1, len(result.evidence) + 1)):
        raise RuntimeError(f"{name}: citation numbering is not contiguous")
    return rank, elapsed


def main() -> int:
    apply_to_env()
    os.environ["LK_RETRIEVAL_ITERS"] = "2"
    os.environ["LK_RETRIEVAL_TOP_K"] = "8"
    os.environ["LK_RETRIEVAL_MIN_RESULTS"] = "1"

    db = SemanticDB()
    memory = MemoryIndex()
    engine = RetrievalEngine(db=db, memory=memory)
    try:
        ranks = []
        times = []
        for case in CASES:
            rank, elapsed = run_case(engine, *case)
            ranks.append(rank)
            times.append(elapsed)

        cold = search_and_fetch(["site:docs.python.org sqlite3 Python documentation"], max_per_query=2)
        stats = search_stats()
        if not cold and not stats.get("last_error"):
            raise RuntimeError("cold web returned nothing without an observable failure reason")
        cold_state = f"{len(cold)} result(s)" if cold else f"degraded: {stats['last_error']}"

        mrr = sum(1 / rank for rank in ranks) / len(ranks)
        print(f"  cold web       {cold_state}")
        print(f"RETRIEVAL SMOKE: PASS (recall@8=1.00, MRR={mrr:.2f}, "
              f"source-diversity=3, max-time={max(times):.2f}s)")
        return 0
    finally:
        memory.close()
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
