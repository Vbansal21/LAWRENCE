"""N-32 (LOCAL-PERF) — turn-stage cache + per-stage timing.

The full turn pipeline runs several model-touching stages (retrieval, response,
expansion) serially-cold. This module is the **caching + measurement** substrate
from N-32's menu — items (c) cache stage outputs keyed by input identity and
(d/e) the pre-preparation seam — plus the per-stage instrumentation that the
plan flags as the open prerequisite ("the per-stage dependency DAG is open").

It does NOT make the model faster (that is N-65 serving); it removes *repeated*
work. The common wins, all behavior-preserving:
  * **regenerate** re-runs a turn with the SAME query+context → identical
    retrieval is reused instead of re-gathered (the chat-ops UI regenerates a lot);
  * **expansion / proactive re-probe** of the same query reuse the bundle;
  * a stable content key means a cache *miss* runs exactly as before.

Contract: cached values are treated **read-only** by callers (the cache hands
back the same object; mutating it would poison later hits).

Bounded LRU + TTL, thread-safe, pure stdlib (I4). Counters via the shared
[debug] logger so "did the cache help?" is inspectable on /metrics.

Env:
  LK_TURNCACHE         "0"/"false" disables entirely (always miss).
  LK_TURNCACHE_TTL     entry lifetime seconds (default 300).
  LK_TURNCACHE_MAX     max live entries before LRU eviction (default 128).
"""
from __future__ import annotations

import hashlib
import os
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

from ..debuglog import bump, debug

_LOCK = threading.Lock()
_STORE: "OrderedDict[str, tuple[float, Any]]" = OrderedDict()


def _enabled() -> bool:
    return os.environ.get("LK_TURNCACHE", "1") not in ("0", "false", "")


def _ttl() -> float:
    try:
        return float(os.environ.get("LK_TURNCACHE_TTL", "300"))
    except ValueError:
        return 300.0


def _max() -> int:
    try:
        return max(1, int(os.environ.get("LK_TURNCACHE_MAX", "128")))
    except ValueError:
        return 128


def key(stage: str, *parts: Any) -> str:
    """Content-address a stage call by its inputs. Stable across processes."""
    h = hashlib.sha256()
    h.update(stage.encode("utf-8"))
    for p in parts:
        h.update(b"\x1f")
        h.update(str(p).encode("utf-8", "replace"))
    return f"{stage}:{h.hexdigest()[:32]}"


def get(k: str) -> tuple[bool, Any]:
    """Return (hit, value). Expired/absent entries are a miss."""
    if not _enabled():
        return False, None
    now = time.monotonic()
    with _LOCK:
        item = _STORE.get(k)
        if item is None:
            bump("turncache", "miss")
            return False, None
        ts, val = item
        if now - ts > _ttl():
            del _STORE[k]
            bump("turncache", "expire")
            bump("turncache", "miss")
            return False, None
        _STORE.move_to_end(k)          # LRU: mark recently used
        bump("turncache", "hit")
        return True, val


def put(k: str, value: Any) -> None:
    if not _enabled():
        return
    with _LOCK:
        _STORE[k] = (time.monotonic(), value)
        _STORE.move_to_end(k)
        while len(_STORE) > _max():
            _STORE.popitem(last=False)  # evict oldest
            bump("turncache", "evict")


def memoize(stage: str, parts: tuple, producer: Callable[[], Any]) -> Any:
    """Return a cached value for (stage, parts) or run + store the producer.

    The producer runs exactly once per (key, TTL window). Exceptions from the
    producer are NOT cached — a failed stage retries next time (degrade, I4).
    """
    k = key(stage, *parts)
    hit, val = get(k)
    if hit:
        debug("turncache", "reuse", stage=stage)
        return val
    val = producer()
    put(k, val)
    return val


@contextmanager
def stage_timer(stage: str):
    """Time a turn stage; emit a [debug] record + a max/last gauge counter."""
    t0 = time.monotonic()
    try:
        yield
    finally:
        ms = int((time.monotonic() - t0) * 1000)
        debug("turn", "stage", stage=stage, ms=ms)
        bump("turn_ms", stage, ms)   # cumulative ms per stage (truthful counter)


def clear() -> None:
    """Drop all entries (tests / explicit invalidation)."""
    with _LOCK:
        _STORE.clear()


def stats() -> dict:
    with _LOCK:
        return {"entries": len(_STORE), "max": _max(), "ttl": _ttl(),
                "enabled": _enabled()}
