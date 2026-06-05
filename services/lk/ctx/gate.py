"""Significance gate — decides whether a sensor event is worth writing to context.

No model involved. Pure heuristics:
  vision_gate: pixel change exceeds threshold AND text is novel vs last-written frame
  audio_gate:  transcript long enough AND not near-duplicate of recent segments
"""
from __future__ import annotations

from typing import Sequence

VISION_PIXEL_MIN   = 0.10   # below this → skip entirely (raises floor, ignores minor redraws)
VISION_NOVELTY_MIN = 0.30   # Jaccard distance vs last-written OCR required
VISION_HIGH        = 0.50   # at or above → always write, no text check (true layout change only)
AUDIO_MIN_WORDS    = 3
AUDIO_DEDUP_MAX    = 0.60   # Jaccard similarity above this → near-duplicate, skip

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
    if change_score < VISION_PIXEL_MIN:
        return False
    if change_score >= VISION_HIGH:
        return True
    novelty = 1.0 - _jaccard(_words(prev_written_ocr), _words(curr_ocr))
    return novelty >= VISION_NOVELTY_MIN


def audio_gate(transcript: str, recent_transcripts: Sequence[str]) -> bool:
    if len(transcript.split()) < AUDIO_MIN_WORDS:
        return False
    curr = _words(transcript)
    for prev in recent_transcripts[-4:]:
        if _jaccard(curr, _words(prev)) > AUDIO_DEDUP_MAX:
            return False
    return True
