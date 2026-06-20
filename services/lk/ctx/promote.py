"""Durable-memory formation — P_dist promotion + DistillAndLink + S_link (N-71, §P).

The soul (`docs/papers/LAWRENCE_v0_1_ieee.tex`, Eq.3 / Eq.4 + Alg.2) says a finished
turn or finding should be *scored* for durable promotion and, when it clears the
bar, written as a linked Zettelkasten note whose edges come from a
similarity / recency / thread link score — not ad-hoc tag overlap. The live turn
only wrote the rolling ContextStore + the retrieval index and **never** promoted to
a durable note; links were manual `[[id]]` only. This module closes both gaps and
fills the soul's note taxonomy ({context_log, task_note, knowledge_note}).

Design constraints (KISS / local-first / I4 / §K.0.1 integrity):
  • MODEL-FREE & best-effort — it composes signals the turn already produced (the
    model's confidence, its self-curated tasks/remember, context tags, the recent
    notes). NO extra LLM call ⇒ it never slows or blocks a turn, and never raises.
  • The S_link *semantic* term uses a LEXICAL cosine (token frequency). Embedding
    cosine is a clean future upgrade; we deliberately do not claim a semantic
    similarity we are not computing.
  • Conservative by default so the vault does not become an event dump (the soul's
    explicit warning): `LK_DISTILL_OFF=1` disables, `LK_DISTILL_TAU` /
    `LK_DISTILL_LINK_TAU` tune the promotion / link thresholds.
"""
from __future__ import annotations

import math
import os
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

_WORD = re.compile(r"[a-z0-9]+")
_EMPHASIS = (
    "remember", "don't forget", "do not forget", "important", "note this",
    "save this", "keep in mind", "make a note", "take note", "for future",
)

# P_dist weights (soul Eq.3): novelty, salience, user-emphasis, thread, action.
_AN, _AS, _AU, _AT, _AA = 0.30, 0.30, 0.20, 0.10, 0.10
# S_link weights (soul Eq.4): lexcos(≈semantic), tag-jaccard, recency, thread.
_L1, _L2, _L3, _L4 = 0.40, 0.25, 0.15, 0.20

_RECENT_K = 40                # candidate window for novelty + linking
_LINK_MAX = 5                 # max auto-links per promoted note
_TIME_HALFLIFE_DAYS = 14.0


def _f(name: str, default: float) -> float:
    try:
        return min(1.0, max(0.0, float(os.getenv(name, str(default)))))
    except ValueError:
        return default


def _disabled() -> bool:
    return os.getenv("LK_DISTILL_OFF", "").strip().lower() in {"1", "true", "yes", "on"}


# ── small model-free similarity primitives ────────────────────────────────────

def _tokens(text: str) -> Counter:
    return Counter(w for w in _WORD.findall((text or "").lower()) if len(w) > 2)


def _lexcos(a: Counter, b: Counter) -> float:
    """Cosine over token-frequency vectors — a model-free stand-in for semantic
    similarity until embeddings are wired into the link step."""
    common = set(a) & set(b)
    if not common:
        return 0.0
    dot = sum(a[w] * b[w] for w in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def _age_days(ts_iso: str, now: datetime) -> float:
    try:
        dt = datetime.fromisoformat(str(ts_iso))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (now - dt).total_seconds() / 86400.0)
    except (ValueError, TypeError):
        return 1e9


def _recency(ts_iso: str, now: datetime, halflife: float = _TIME_HALFLIFE_DAYS) -> float:
    age = _age_days(ts_iso, now)
    return 0.0 if age >= 1e8 else 0.5 ** (age / halflife)


# ── the two formal scores ─────────────────────────────────────────────────────

def pdist(*, novelty: float, salience: float, emphasis: float,
          thread: float, action: float) -> float:
    """Soul Eq.3 — priority for durable promotion, normalised to [0,1]."""
    s = (_AN * novelty + _AS * salience + _AU * emphasis
         + _AT * thread + _AA * action)
    return max(0.0, min(1.0, s))


def slink(new_tok: Counter, new_tags: set, cand_body: str, cand_tags: set,
          cand_ts: str, now: datetime) -> float:
    """Soul Eq.4 — link score between a new note and a candidate, in [0,1]."""
    same_thread = 1.0 if (new_tags & cand_tags and _age_days(cand_ts, now) < 1.0) else 0.0
    return (_L1 * _lexcos(new_tok, _tokens(cand_body))
            + _L2 * _jaccard(new_tags, cand_tags)
            + _L3 * _recency(cand_ts, now)
            + _L4 * same_thread)


# ── candidate gathering (bounded I/O) ─────────────────────────────────────────

def _candidates(notes: Any, tags: set) -> list[tuple[str, str, set, str]]:
    """Cheap pre-filter for linking + novelty: the few most-recent notes plus any
    that share a tag. Bodies are read only for this bounded set (not the whole
    vault). Returns [(id, body, tagset, ts), …]."""
    try:
        recs = notes.list_notes(_RECENT_K)
    except Exception:
        return []
    picked: dict[str, dict] = {}
    for r in recs[:10]:                       # always consider the most recent few
        if r.get("id"):
            picked[r["id"]] = r
    if tags:
        for r in recs:                        # plus anything topically related
            if r.get("id") and tags & {str(t) for t in (r.get("tags") or [])}:
                picked[r["id"]] = r
    out: list[tuple[str, str, set, str]] = []
    for nid, r in picked.items():
        try:
            full = notes.read_note(nid) or {}
        except Exception:
            full = {}
        out.append((nid, str(full.get("body", "")),
                    {str(t) for t in (r.get("tags") or [])}, str(r.get("ts", ""))))
    return out


# ── the public entry point ────────────────────────────────────────────────────

def promote_turn(
    notes: Any, *,
    ts: str,
    user_text: str,
    answer: str,
    note_full: str = "",
    note_compact: str = "",
    tags: list[str] | None = None,
    confidence: float = 0.0,
    has_tasks: bool = False,
    has_actions: bool = False,
    has_remember: bool = False,
) -> str:
    """Score a finished turn and, if it clears the bar, write a linked durable note.

    Returns the new note id, or "" when nothing was promoted (the common case for
    small-talk). Never raises — durable memory must not break a turn.
    """
    if notes is None or _disabled():
        return ""
    try:
        tag_set = {str(t) for t in (tags or []) if t}
        body = (note_full or "").strip() or f"{user_text}\n\n{answer}".strip()
        if len(body) < 12:
            return ""

        now = datetime.now(timezone.utc)
        cand = _candidates(notes, tag_set)
        tok = _tokens(f"{user_text} {body}")

        # P_dist terms (soul Eq.3), each in [0,1] -------------------------------
        if cand:
            novelty = 1.0 - max(_lexcos(tok, _tokens(b)) for _, b, _, _ in cand)
        else:
            novelty = 0.5                                  # neutral when vault empty
        salience = max(0.0, min(1.0, confidence)) if confidence else 0.1
        ul = (user_text or "").lower()
        emphasis = 1.0 if (has_remember or any(k in ul for k in _EMPHASIS)) else 0.0
        recent_tags: set = set()
        for _, _, ct, _ts in cand:
            recent_tags |= ct
        thread = _jaccard(tag_set, recent_tags)
        action = 1.0 if (has_tasks or has_actions) else 0.0

        score = pdist(novelty=novelty, salience=salience, emphasis=emphasis,
                      thread=thread, action=action)
        # Promote on score, OR an explicit pin, OR a confirmed action (soul rule).
        if not (score >= _f("LK_DISTILL_TAU", 0.50)
                or has_remember or has_tasks or has_actions):
            return ""

        kind = ("task_note" if (has_tasks or has_actions)
                else "knowledge_note" if (has_remember or (novelty >= 0.6 and salience >= 0.5))
                else "context_log")

        # DistillAndLink (soul Alg.2): keep candidates whose S_link clears the bar.
        link_tau = _f("LK_DISTILL_LINK_TAU", 0.30)
        scored = [(slink(tok, tag_set, b, ct, cts, now), nid)
                  for nid, b, ct, cts in cand]
        links = [nid for s, nid in sorted(scored, reverse=True)
                 if s >= link_tau][:_LINK_MAX]

        text = body if note_full else f"{body}\n\n— distilled from chat turn ({str(ts)[:19]})"
        return notes.write_note(kind, text, source=f"turn:{ts}",
                                tags=sorted(tag_set), links=links)
    except Exception:
        return ""
