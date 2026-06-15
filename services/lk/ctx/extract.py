"""Extraction layer (WS-P/B1) — raw perception → clean memory.

The keystone of the perception→memory→tick spine. A continuous sensor stream is
noisy: raw OCR garble and half-heard transcripts. Before such a slice lands in
working memory it passes through one **droppable, context-free** model call
(`call_model(role="extract")`, provided here as an injected `extract_fn`) that
distils it to a clean, self-contained entry and grades its **significance** —
including *what the user may be missing* — for the cognitive tick to consume.

Design rules (see docs/AUTONOMY.md §1b — the Protagonist Principle):
  • No rolling context is passed — clean focus on the slice alone.
  • The call is the lowest priority and droppable; it must never block a user
    turn or the capture loop. On skip/failure the caller keeps the RAW slice
    (the degraded path — perception keeps working without the model).
  • An info-gain gate (`ctx.gate.extract_gate`) keeps the call off near-duplicate
    ambient frames.
  • Provider logic stays in `model.py` (I3): this module only orchestrates the
    injected callable, exactly like the store's `compact_fn`.

Significance/tags are buffered in a bounded deque; the tick (WS-C/C1) drains it
via `drain()`. Until the tick exists, B1 still earns its keep by storing clean
entries instead of raw noise.
"""
from __future__ import annotations

import os
import threading
from collections import deque
from collections.abc import Callable
from typing import Any

from .gate import extract_gate
from .significance import TIER_NOTE, Grader

# Kinds that flow through the observer/spool path and should be distilled. Turn
# entries (kind="turn") and model-authored findings are never extracted.
EXTRACT_KINDS = frozenset({"vision", "audio"})


def enabled() -> bool:
    """Extraction is on unless LK_EXTRACT is explicitly falsey (config: ``extract``)."""
    return os.environ.get("LK_EXTRACT", "1").strip().lower() not in ("0", "false", "no", "off")


class Extractor:
    """Gate + (injected) model call + a significance buffer for the tick.

    extract_fn(slice_text, kind) -> {clean, significance, tags} | None
        The kernel's ``run_extract`` (the only model-touching part). Injected so
        this module stays provider-agnostic and unit-testable with a stub.
    """

    def __init__(
        self,
        extract_fn: Callable[[str, str], dict | None],
        *,
        max_recent: int = 64,
        note_store: Any = None,
        grader: Grader | None = None,
    ) -> None:
        self._fn = extract_fn
        self._prev_slice = ""
        self._lock = threading.Lock()        # observers call from >1 thread
        self.recent: deque[dict[str, Any]] = deque(maxlen=max_recent)
        self.calls = 0                        # model calls actually made (observability)
        self._notes = note_store             # ctx.notes.NoteStore | None (M3)
        self.notes_written = 0
        self.grader = grader if grader is not None else Grader()  # WS-C/C2 action tier

    def extract(self, slice_text: str, kind: str = "event") -> dict | None:
        """Distil one slice. Returns ``{clean, significance, tags, kind, ts?}`` or
        ``None`` when skipped/failed — callers fall back to the raw slice."""
        if not enabled():
            return None
        slice_text = (slice_text or "").strip()
        if not slice_text:
            return None

        # Info-gain gate (single-flighted): advance the baseline only when we pass,
        # so the very next near-duplicate is skipped without a model call.
        with self._lock:
            if not extract_gate(self._prev_slice, slice_text):
                return None
            self._prev_slice = slice_text

        try:
            out = self._fn(slice_text, kind)
        except Exception:
            out = None
        if not out or not str(out.get("clean", "")).strip():
            return None

        sig = float(out.get("significance", 0.0) or 0.0)
        # WS-C/C2: grade the score against the running mean±σ band → an action
        # tier (0 log / 1 note / 2 study+surface). `grade` classifies vs history
        # then learns. The tick reads `tier` to decide whether to surface (≥2).
        tier = self.grader.grade(sig)
        result = {
            "clean":        str(out["clean"]).strip(),
            "significance": sig,
            "tier":         tier,
            "tags":         [str(t) for t in (out.get("tags") or []) if t][:8],
            "kind":         kind,
        }
        with self._lock:
            self.calls += 1
            self.recent.append(result)

        # M3: a note-tier-or-above moment also becomes an atomic note — append-only,
        # addressable, distinct from the (compressing) rolling tiers.
        if self._notes is not None and tier >= TIER_NOTE:
            try:
                nid = self._notes.write_note(
                    kind, result["clean"],
                    source=f"{kind} observation", tags=result["tags"],
                )
                if nid:
                    result["note_id"] = nid
                    self.notes_written += 1
            except Exception:
                pass
        return result

    def drain(self) -> list[dict[str, Any]]:
        """Pop all buffered results for the cognitive tick (WS-C/C1) to score/act on."""
        with self._lock:
            items = list(self.recent)
            self.recent.clear()
        return items
