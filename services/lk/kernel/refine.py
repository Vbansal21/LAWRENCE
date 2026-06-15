"""Slow loop (WS-R/R1) — the alter-ego that critiques the fast answer and, only
when it is materially better, earns its way back to the user.

The fast loop (`run_turn`) surfaces a useful answer immediately. The slow loop then
re-reads the question + that draft with more deliberation (a critique-then-rewrite
prompt on the `refine` role — routable to a *stronger* brain) and returns a
verdict. If the verdict clears the elevation gate (R2) the refined answer replaces
the surfaced one in place; otherwise the fast answer simply stands.

Per §1b (Protagonist Principle): pure model policy on the role seam; runs at
`PRI_REFINE` (below a live turn, never droppable so it isn't starved but always
yields a fresh turn ahead of it); bounded to **depth 1** (no recursion); fully
degraded-safe — any failure leaves the fast answer untouched. OFF by default
(`LK_SLOW_LOOP`) until proven stable.
"""
from __future__ import annotations

import os
import threading
from collections.abc import Callable
from typing import Any

from ..model import PRI_REFINE, call_model
from . import prompts, schemas
from .elevate import Elevator
from .invoke import _build_messages, _extract_json

# One shared gate process-wide so the rate limit + per-turn dedup span both the
# slow loop and tick findings (R2 "one elevation path"). Callers may inject their own.
_DEFAULT_ELEVATOR = Elevator()


def enabled() -> bool:
    """The slow loop is OFF unless LK_SLOW_LOOP is truthy (config: ``slow_loop``)."""
    return os.environ.get("LK_SLOW_LOOP", "0").strip().lower() in ("1", "true", "yes", "on")


def run_refine(
    user_text: str,
    fast_answer: str,
    *,
    ctx: Any = None,
    retrieval: Any = None,
    fast_confidence: float = 0.0,
    timeout: int = 300,
) -> dict | None:
    """Critique the fast answer. Returns ``{refined, better, critique, confidence,
    delta}`` or ``None`` on disabled / empty input / any failure (degraded path —
    the caller keeps the fast answer)."""
    user_text = (user_text or "").strip()
    fast_answer = (fast_answer or "").strip()
    if not user_text or not fast_answer:
        return None
    tail = ""
    try:
        tail = ctx.tail_for_model() if ctx is not None else ""
    except Exception:
        tail = ""
    body = (f"{tail}\n\nUSER QUESTION: {user_text}\n\n"
            f"FAST ANSWER (draft to critique):\n{fast_answer}")
    try:
        raw = call_model(
            _build_messages(prompts.REFINE, body, [], []),
            max_tokens=1024, temperature=0.2, timeout=timeout,
            schema=schemas.REFINE, role="refine", priority=PRI_REFINE,
        )
        out = _extract_json(raw.get("text", ""))
    except Exception:
        return None
    if not out:
        return None

    refined = str(out.get("refined", "")).strip()
    better = bool(out.get("better")) and bool(refined)   # 'better' with no text is meaningless
    conf = max(0.0, min(1.0, float(out.get("confidence", 0.0) or 0.0)))
    return {
        "refined":    refined,
        "better":     better,
        "critique":   str(out.get("critique", "")).strip(),
        "confidence": conf,
        "delta":      conf - max(0.0, min(1.0, float(fast_confidence or 0.0))),
    }


def dispatch_refine(
    user_text: str,
    fast_answer: str,
    *,
    ctx: Any = None,
    retrieval: Any = None,
    fast_confidence: float = 0.0,
    on_refine: Callable[[dict], Any] | None = None,
    elevator: Elevator | None = None,
    slow_fn: Callable[..., dict | None] | None = None,
    turn_id: str = "",
    live_fn: Callable[[str], None] | None = None,
) -> threading.Thread | None:
    """Run the slow loop in a daemon thread so the fast answer is never blocked.
    Calls ``on_refine(verdict)`` exactly once, and only if the verdict clears the
    elevation gate. Returns the thread (so callers/tests can join) or ``None`` when
    the slow loop is off. ``slow_fn`` overrides the model call for testing."""
    if not enabled():
        return None
    fn = slow_fn or run_refine
    gate = elevator or _DEFAULT_ELEVATOR

    def _work() -> None:
        try:
            verdict = fn(user_text, fast_answer, ctx=ctx, retrieval=retrieval,
                         fast_confidence=fast_confidence)
        except Exception:
            verdict = None
        if not verdict or not verdict.get("better"):
            return                                   # fast answer stands
        item = {**verdict, "turn_id": turn_id, "refined": verdict.get("refined", "")}
        if gate.elevate(item, turn_id=turn_id, prior=fast_answer,
                        emit=on_refine if on_refine is not None else None):
            if live_fn:
                live_fn(f"[refine] elevated a better answer (Δconf={verdict.get('delta', 0):.2f})")

    th = threading.Thread(target=_work, daemon=True, name="slow-refine")
    th.start()
    return th
