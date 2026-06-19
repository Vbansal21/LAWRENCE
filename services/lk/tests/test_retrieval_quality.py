"""Small labeled retrieval-quality gate over the production engine."""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "services")

from lk.retrieval.db import SemanticDB
from lk.retrieval.engine import RetrievalEngine
from lk.retrieval.memory import MemoryIndex
import lk.retrieval.web as web


def no_model(*_args, **_kwargs):
    raise RuntimeError("use enforced heuristic queries")


tmp = Path(tempfile.mkdtemp(prefix="lk-retrieval-quality-"))
saved_fetch = web.search_and_fetch
saved_env = {k: os.environ.get(k) for k in (
    "LK_RETRIEVAL_CATEGORIES", "LK_RETRIEVAL_ITERS", "LK_RETRIEVAL_ASSESS",
    "LK_RETRIEVAL_TOP_K", "LK_RETRIEVAL_MIN_RESULTS",
)}
try:
    web.search_and_fetch = lambda *_args, **_kwargs: []
    os.environ["LK_RETRIEVAL_ITERS"] = "1"
    os.environ["LK_RETRIEVAL_ASSESS"] = "0"
    os.environ["LK_RETRIEVAL_TOP_K"] = "8"
    os.environ["LK_RETRIEVAL_MIN_RESULTS"] = "1"

    memory = MemoryIndex(tmp / "memory.db")
    memory.upsert("note-target", "note", "zephyr cobalt handshake confirms the watcher state", embed=False)
    memory.upsert("note-noise", "note", "bread fermentation temperature notes", embed=False)

    db = SemanticDB(tmp / "retrieval.db")
    db.upsert("file:///fixtures/orion.md", "Orion", ["orion lattice rollback procedure and recovery steps"])
    db.upsert("file:///fixtures/noise.md", "Noise", ["quarterly office supply inventory"])
    db.upsert("https://official.test/maple", "Maple", ["maple telemetry protocol reference implementation"])
    db.upsert("https://noise.test/page", "Noise", ["weekend garden weather report"])
    db.upsert("note://shadow", "Shadow", ["maple telemetry protocol must not appear as web evidence"])

    engine = RetrievalEngine(db=db, memory=memory, call_fn=no_model)
    fixture = json.loads(Path(
        "services/lk/tests/fixtures/retrieval_quality.json"
    ).read_text(encoding="utf-8"))

    recalls = []
    reciprocal_ranks = []
    for case in fixture["cases"]:
        os.environ["LK_RETRIEVAL_CATEGORIES"] = case["categories"]
        result = engine.gather(case["query"], short_ctx="quality fixture", timeout=10)
        urls = [item.url for item in result.evidence]
        expected = set(case["expected"])
        recalls.append(len(expected.intersection(urls[:5])) / len(expected))
        ranks = [urls.index(url) + 1 for url in expected if url in urls]
        reciprocal_ranks.append(1 / min(ranks) if ranks else 0.0)
        print(f"  {case['name']}: {urls[:5]}")
        assert "note://shadow" not in urls, f"{case['name']}: category contamination"
        assert [item.citation_num for item in result.evidence] == list(
            range(1, len(result.evidence) + 1)
        ), f"{case['name']}: broken citation numbering"
        normalized = [" ".join(item.text.lower().split()) for item in result.evidence]
        assert len(normalized) == len(set(normalized)), f"{case['name']}: duplicate evidence"

    recall_at_5 = sum(recalls) / len(recalls)
    mrr = sum(reciprocal_ranks) / len(reciprocal_ranks)
    assert recall_at_5 == 1.0, f"recall@5={recall_at_5:.3f}"
    assert mrr >= 0.75, f"MRR={mrr:.3f}"
    print(f"RETRIEVAL QUALITY: PASS (recall@5={recall_at_5:.2f}, MRR={mrr:.2f})")
finally:
    web.search_and_fetch = saved_fetch
    for key, value in saved_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    shutil.rmtree(tmp, ignore_errors=True)
