"""
Event distillation — raw sensor data → (compact, detailed) string pair.

  compact  → one line appended to context.log  (long-term sparse record)
  detailed → richer block appended to rolling.jsonl (fed to the model)

Both are distilled, neither is raw. The detailed form includes full OCR / full
transcript; the compact form is a keyword-tagged one-liner. No model involved.
"""
from __future__ import annotations

from .gate import STOPWORDS as _STOP, VISION_HIGH


def _kw(text: str, n: int = 8) -> list[str]:
    out: list[str] = []
    for w in text.split():
        w = w.strip(".,;:!?\"'()[]{}").lower()
        if len(w) > 3 and w not in _STOP:
            out.append(w)
            if len(out) == n:
                break
    return out


def vision(
    ts: str,
    change_score: float,
    ocr_text: str,
    heuristic_diff: str,
) -> tuple[str, str]:
    t = ts[11:19]
    level = "sig" if change_score >= VISION_HIGH else "minor"
    kw = ", ".join(_kw(ocr_text)) if ocr_text else "—"
    compact = f"[VISION {t}] {level} Δ={change_score:.2f} | {kw}"

    diff_line = heuristic_diff or f"{level} change Δ={change_score:.2f}"
    screen = f"\n  screen: {ocr_text[:500]}" if ocr_text else ""
    detailed = f"[VISION {t}] {diff_line}{screen}"
    return compact, detailed


def audio(ts: str, transcript: str, rms_db: float | None) -> tuple[str, str]:
    t = ts[11:19]
    db = f" ({rms_db:.0f}dB)" if rms_db is not None else ""
    compact  = f'[AUDIO {t}] "{transcript[:80]}"'
    detailed = f'[AUDIO {t}] "{transcript}"{db}'
    return compact, detailed


def turn(
    ts: str,
    user_text: str,
    answer: str,
    note_compact: str,
) -> tuple[str, str]:
    t = ts[11:19]
    note = f" → {note_compact[:80]}" if note_compact else ""
    compact  = f"[TURN  {t}] {user_text[:80]}{note}"
    detailed = f"[USER  {t}] {user_text}\n[ASSIST {t}] {answer}"
    return compact, detailed
