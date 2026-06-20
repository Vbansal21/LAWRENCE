"""N-32 (LOCAL-PERF) — turn-stage cache: keying, TTL, LRU, degrade, memoize.

Typed contract for kernel/turncache.py:

  INPUT    (stage, parts, producer) calls + env tuning.
  OUTPUT   producer result, run at most once per (key, TTL window); identical
           inputs reuse the stored object; distinct inputs do not collide.
  WHEN HIT same stage + same parts within TTL and under the LRU cap.
  WHEN MISS first call · expired entry · distinct parts · evicted (LRU) ·
           cache disabled (LK_TURNCACHE=0) · producer raised (never cached).

Pure stdlib, offline. No server, no model.
"""
import os
import sys
import time

sys.path.insert(0, "services")

os.environ["LK_TURNCACHE"] = "1"
os.environ["LK_TURNCACHE_TTL"] = "100"
os.environ["LK_TURNCACHE_MAX"] = "3"

from lk.kernel import turncache as TC  # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    print(f"{'PASS' if cond else 'FAIL'}: {name}" + (f"  [{extra}]" if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def counter():
    box = {"n": 0}

    def producer():
        box["n"] += 1
        return f"value-{box['n']}"
    return box, producer


# ── A — basic hit/miss + run-once ────────────────────────────────────────────
TC.clear()
box, prod = counter()
v1 = TC.memoize("retrieve", ("q", "ctx", False), prod)
v2 = TC.memoize("retrieve", ("q", "ctx", False), prod)
check("A1 first call runs producer", v1 == "value-1")
check("A2 second identical call is a hit (no rerun)", v2 == "value-1" and box["n"] == 1)
check("A3 hit returns the SAME object", v1 is v2)

# ── B — distinct parts don't collide ─────────────────────────────────────────
TC.clear()
box, prod = counter()
a = TC.memoize("retrieve", ("q1",), prod)
b = TC.memoize("retrieve", ("q2",), prod)
check("B1 different parts -> different producer runs", a == "value-1" and b == "value-2")
# distinct stage also separates
c = TC.memoize("gather", ("q1",), prod)
check("B2 different stage -> separate key", c == "value-3")

# ── C — key stability ────────────────────────────────────────────────────────
check("C1 key is deterministic", TC.key("s", 1, "x") == TC.key("s", 1, "x"))
check("C2 key separates stages", TC.key("a", 1) != TC.key("b", 1))
check("C3 key separates parts", TC.key("s", 1) != TC.key("s", 2))

# ── D — TTL expiry ───────────────────────────────────────────────────────────
os.environ["LK_TURNCACHE_TTL"] = "0"   # everything expires immediately
TC.clear()
box, prod = counter()
TC.memoize("retrieve", ("q",), prod)
TC.memoize("retrieve", ("q",), prod)
check("D1 expired entry forces a rerun", box["n"] == 2)
os.environ["LK_TURNCACHE_TTL"] = "100"

# ── E — LRU eviction at the cap (max=3) ──────────────────────────────────────
TC.clear()
box, prod = counter()
for q in ("q1", "q2", "q3"):
    TC.memoize("retrieve", (q,), prod)
TC.memoize("retrieve", ("q4",), prod)        # evicts q1 (oldest)
hit_q1, _ = TC.get(TC.key("retrieve", "q1"))
hit_q4, _ = TC.get(TC.key("retrieve", "q4"))
check("E1 oldest entry evicted past the cap", not hit_q1)
check("E2 newest entry still present", hit_q4)
check("E3 store never exceeds the cap", TC.stats()["entries"] <= 3)

# ── F — disabled cache always misses ─────────────────────────────────────────
os.environ["LK_TURNCACHE"] = "0"
TC.clear()
box, prod = counter()
TC.memoize("retrieve", ("q",), prod)
TC.memoize("retrieve", ("q",), prod)
check("F disabled -> producer runs every time", box["n"] == 2)
os.environ["LK_TURNCACHE"] = "1"

# ── G — producer exceptions are NOT cached (degrade, I4) ─────────────────────
TC.clear()
state = {"calls": 0}


def flaky():
    state["calls"] += 1
    if state["calls"] == 1:
        raise RuntimeError("boom")
    return "ok"


try:
    TC.memoize("retrieve", ("q",), flaky)
except RuntimeError:
    pass
v = TC.memoize("retrieve", ("q",), flaky)   # retried, succeeds, now cached
check("G1 failed producer is retried (not cached)", v == "ok" and state["calls"] == 2)

# ── H — stage_timer never swallows nor blocks ────────────────────────────────
with TC.stage_timer("response"):
    pass
ran = {"x": False}
try:
    with TC.stage_timer("response"):
        ran["x"] = True
        raise ValueError("inner")
except ValueError:
    pass
check("H1 stage_timer re-raises inner errors", ran["x"])

# ── I — run_turn reuses retrieval on an identical re-run (the regenerate win) ─
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from lk.ctx import ContextStore
from lk.kernel import run_turn, TurnConfig
from lk.ui import UIConnector
import lk.kernel.invoke as INV


class _Gather:
    def __init__(self):
        self.evidence = []
        self.context_understanding = "ctx"
        self.capture_hires = False
        self.queries = {"notes": ["q"]}


class _CountingEngine:
    def __init__(self):
        self.calls = 0

    def gather(self, *a, **k):
        self.calls += 1
        return _Gather()


TC.clear()
os.environ["LK_TURNCACHE"] = "1"
os.environ["LK_TURNCACHE_TTL"] = "100"
tmp = Path(tempfile.mkdtemp())
TS = "2026-06-20T00:00:00+00:00"   # fixed ts so two stores seed identically


def seeded_store(name):
    # run_turn keys retrieval on the frozen context TEXT; two stores with
    # byte-identical seed content produce an identical ctx_tail -> the cache is
    # content-addressed, so the second turn reuses the first's gather.
    c = ContextStore(mem_dir=tmp / name)
    c.append(ts=TS, kind="turn", compact="seed", detailed="seed ctx")
    return c


try:
    eng = _CountingEngine()
    ui = UIConnector()
    cfg = TurnConfig(timeout=30)

    def fake_call(messages, *, stream_fn=None, should_stop=None, **kw):
        return {"text": json.dumps({"answer_text": "A", "confidence": 0.9})}

    real = INV.call_model
    INV.call_model = fake_call
    try:
        run_turn("same question?", ctx=seeded_store("a"), retrieval=None, engine=eng,
                 cfg=cfg, images=[], audios=[], ui=ui, stream_fn=lambda p: None)
        first = eng.calls
        # identical query AND identical frozen-context text within TTL -> cache hit
        run_turn("same question?", ctx=seeded_store("b"), retrieval=None, engine=eng,
                 cfg=cfg, images=[], audios=[], ui=ui, stream_fn=lambda p: None)
        second = eng.calls
        check("I1 first turn gathers", first == 1, f"calls={first}")
        check("I2 identical-context re-run reuses the bundle (no second gather)",
              second == 1, f"calls={second}")
        # a different query must NOT hit the cache
        run_turn("a different question?", ctx=seeded_store("c"), retrieval=None,
                 engine=eng, cfg=cfg, images=[], audios=[], ui=ui, stream_fn=lambda p: None)
        check("I3 distinct query re-gathers", eng.calls == 2, f"calls={eng.calls}")
    finally:
        INV.call_model = real
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print()
if FAILS:
    print(f"FAILED ({len(FAILS)}): " + ", ".join(FAILS))
    sys.exit(1)
print("test_turncache OK")
