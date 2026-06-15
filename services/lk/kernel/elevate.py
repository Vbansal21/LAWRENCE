"""Elevation gate (WS-R/R2) — the one channel by which slow / background output
earns its way into the foreground.

Both the per-turn slow loop (R1, a refined answer) and the always-on tick
(C1/run_proactive, an unprompted finding) produce candidates that *might* be worth
interrupting the user with. This is the single gate they both pass through, so the
"don't pester" policy lives in exactly one place (Protagonist Principle:
contemplation, not nagging).

A candidate is elevated only when it clears every bar:
  • **better** — for a refinement, the slow loop said so; findings default to true;
  • **Δconfidence ≥ delta** — when the candidate carries a confidence delta (a
    refinement does; a finding may not), the gain must be meaningful;
  • **novel** — not a near-duplicate of what is already shown for this turn;
  • **within the rate limit** — at most `max_per_min` elevations per rolling minute.

Idempotent per turn-id: the same refinement never double-surfaces. Pure policy —
no model, no provider logic (I3); the caller supplies the surfacing `emit`.
All knobs are config-driven (lk.json → env): `LK_ELEVATE_DELTA`,
`LK_ELEVATE_MAX_PER_MIN`.
"""
from __future__ import annotations

import os
import re
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Any


def _delta() -> float:
    try:
        return float(os.environ.get("LK_ELEVATE_DELTA", "0.15"))
    except (TypeError, ValueError):
        return 0.15


def _max_per_min() -> int:
    try:
        return int(os.environ.get("LK_ELEVATE_MAX_PER_MIN", "3"))
    except (TypeError, ValueError):
        return 3


def _fingerprint(text: str) -> str:
    """Cheap normalised signature for near-duplicate detection."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())[:160]


def _candidate_text(item: dict[str, Any]) -> str:
    """The human-facing text of either shape — a refinement or a finding."""
    return str(item.get("refined") or item.get("insight") or item.get("headline") or "").strip()


class Elevator:
    """Shared gate + bookkeeping. Thread-safe (R1 runs in a background thread)."""

    def __init__(self, *, delta: float | None = None, max_per_min: int | None = None,
                 now: Callable[[], float] = time.monotonic) -> None:
        self._delta = delta
        self._max = max_per_min
        self._now = now
        self._lock = threading.Lock()
        self._emits: deque[float] = deque()          # recent elevation timestamps
        self._seen: dict[str, set[str]] = {}         # turn-id → shown fingerprints
        self.elevated = 0
        self.blocked = 0

    def delta(self) -> float:
        return _delta() if self._delta is None else self._delta

    def max_per_min(self) -> int:
        return _max_per_min() if self._max is None else self._max

    # ── gate ─────────────────────────────────────────────────────────────────────
    def _passes(self, item: dict[str, Any], turn_id: str, prior: str) -> bool:
        if not item or not bool(item.get("better", True)):
            return False
        d = item.get("delta")
        if d is not None and float(d) < self.delta():
            return False
        text = _candidate_text(item)
        if not text:
            return False
        fp = _fingerprint(text)
        shown = self._seen.get(turn_id, set())
        if fp in shown or fp == _fingerprint(prior):   # duplicate of prior/shown
            return False
        # rate limit: prune the rolling-minute window, then check headroom
        cutoff = self._now() - 60.0
        while self._emits and self._emits[0] < cutoff:
            self._emits.popleft()
        return len(self._emits) < self.max_per_min()

    def elevate(self, item: dict[str, Any], *, turn_id: str = "", prior: str = "",
                emit: Callable[[dict[str, Any]], Any] | None = None) -> bool:
        """Gate one candidate; on success record it, call ``emit`` once, return True."""
        with self._lock:
            if not self._passes(item, turn_id, prior):
                self.blocked += 1
                return False
            self._emits.append(self._now())
            self._seen.setdefault(turn_id, set()).add(_fingerprint(_candidate_text(item)))
            self.elevated += 1
        if emit is not None:
            try:
                emit(item)
            except Exception:
                pass
        return True
