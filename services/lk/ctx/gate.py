"""Significance gate — decides whether a sensor event is worth writing to context.

No model involved. Pure heuristics:
  vision_gate: pixel change exceeds threshold AND text is novel vs last-written frame
  audio_gate:  transcript long enough AND not near-duplicate of recent segments

All thresholds live on the module-level `gate_config` singleton so they can be
updated at runtime via `/set vision-high 0.6` without restarting observers.
"""
from __future__ import annotations

from typing import Sequence


class GateConfig:
    """Mutable threshold settings — patched live by the CLI's /set command."""
    vision_pixel_min:   float = 0.10   # below → skip (ignores minor redraws)
    vision_novelty_min: float = 0.30   # Jaccard distance vs last-written OCR
    vision_high:        float = 0.50   # at or above → always write (layout change)
    audio_min_words:    int   = 3
    audio_dedup_max:    float = 0.60   # Jaccard sim above → near-duplicate, skip
    # extraction (WS-P/B1) info-gain: distil only when a slice is novel enough vs.
    # the last extracted one — keeps the (droppable) model call off near-duplicates.
    extract_min_words:   int   = 4
    extract_novelty_min: float = 0.25  # Jaccard distance vs last extracted slice


gate_config = GateConfig()


STOPWORDS = frozenset({
    "the", "a", "an", "is", "to", "of", "in", "and", "or", "for", "with",
    "on", "at", "it", "i", "its", "you", "we", "they", "was", "be", "are",
    "this", "that", "as", "but", "have", "had", "not", "by", "from", "been",
})


def _words(text: str) -> set[str]:
    return {w for w in text.lower().split() if len(w) > 2 and w not in STOPWORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    u = len(a | b)
    return len(a & b) / u if u else 0.0


def vision_gate(change_score: float, prev_written_ocr: str, curr_ocr: str) -> bool:
    if change_score < gate_config.vision_pixel_min:
        return False
    if change_score >= gate_config.vision_high:
        return True
    novelty = 1.0 - _jaccard(_words(prev_written_ocr), _words(curr_ocr))
    return novelty >= gate_config.vision_novelty_min


def audio_gate(transcript: str, recent_transcripts: Sequence[str]) -> bool:
    if len(transcript.split()) < gate_config.audio_min_words:
        return False
    curr = _words(transcript)
    for prev in recent_transcripts[-4:]:
        if _jaccard(curr, _words(prev)) > gate_config.audio_dedup_max:
            return False
    return True


def extract_gate(prev_slice: str, curr_slice: str) -> bool:
    """Info-gain gate for the extraction layer (B1): only distil a slice that adds
    enough novelty over the last one extracted, so the droppable model call is
    never spent on near-duplicate ambient frames."""
    curr = _words(curr_slice)
    if len(curr) < gate_config.extract_min_words:
        return False
    novelty = 1.0 - _jaccard(_words(prev_slice), curr)
    return novelty >= gate_config.extract_novelty_min
