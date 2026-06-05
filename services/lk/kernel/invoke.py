"""LLM kernel — the only place the model is called.

run_turn():
  1. Read rolling context tail
  2. Analysis pass → decide what to retrieve
  3. Retrieval (if needed)
  4. Response pass → answer + memory note
  5. Write turn to ContextStore and turn log

run_proactive():
  Triggered by sensor observers on significant context change.
  Analysis pass only (no user question) → retrieval if useful → DB warm-up.
  Does not write to context, does not answer the user.
"""
from __future__ import annotations

import itertools
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..ctx      import ContextStore
from ..ctx      import distill as D
from ..logger   import write_turn
from ..model    import call_model, audio_block, image_block, text_block
from ..retrieval import RetrievalPipeline, format_snippets, format_for_model, format_citations
from ..ui       import UIConnector
from .          import prompts

REPO_ROOT    = Path(__file__).resolve().parents[3]
_JOURNAL_DIR = REPO_ROOT / "memory" / "journal"

_turn_ctr = itertools.count(1)


# ── JSON helpers ──────────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict[str, Any] | None:
    """Return the last valid JSON object found in text (skips thinking-block noise)."""
    decoder = json.JSONDecoder()
    found: dict[str, Any] | None = None
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            val, _ = decoder.raw_decode(text[i:])
            if isinstance(val, dict):
                found = val
        except json.JSONDecodeError:
            continue
    return found


def _fallback_response(text: str) -> dict[str, Any]:
    # If the text looks like truncated JSON, salvage answer_text with a regex
    answer = text[:800]
    if text.lstrip().startswith("{"):
        import re
        m = re.search(r'"answer_text"\s*:\s*"((?:[^"\\]|\\.)*)', text)
        if m:
            answer = m.group(1).replace('\\"', '"').replace("\\n", "\n")
    return {
        "answer_text":     answer,
        "modalities_used": ["text"],
        "note_compact":    "",
        "note_full":       "",
        "context_tags":    [],
        "confidence":      0.1,
    }


# ── message builder ───────────────────────────────────────────────────────────

def _build_messages(
    system: str,
    body: str,
    images: list[Path],
    audios: list[Path],
) -> list[dict[str, Any]]:
    if not images and not audios:
        user_msg: dict[str, Any] = {"role": "user", "content": body}
    else:
        user_msg = {"role": "user", "content": (
            [image_block(p) for p in images] +
            [audio_block(p) for p in audios] +
            [text_block(body)]
        )}
    return [{"role": "system", "content": system}, user_msg]


# ── turn config ───────────────────────────────────────────────────────────────

@dataclass
class TurnConfig:
    max_tokens:    int   = 2048
    temperature:   float = 0.2
    timeout:       int   = 300
    skip_analysis: bool  = False
    no_retrieval:  bool  = False


# ── main turn ─────────────────────────────────────────────────────────────────

def run_turn(
    user_text: str,
    *,
    ctx:        ContextStore,
    retrieval:  RetrievalPipeline,
    cfg:        TurnConfig,
    images:     list[Path],
    audios:     list[Path],
    ui:         UIConnector,
    capture_fn: Callable[[], Path | None] | None = None,
    live_fn:    Callable[[str], None]     | None = None,
) -> tuple[str, dict]:
    turn_id  = f"t-{next(_turn_ctr):04d}"
    ts_start = time.monotonic()
    ts_now   = datetime.now(timezone.utc).isoformat()
    ctx_tail = ctx.tail_for_model()
    images   = list(images)   # local copy — we may append capture_fn result

    # ── pass 1: analysis ──────────────────────────────────────────────────────
    analysis: dict[str, Any] | None = None
    retrieval_queries: list[str] = []
    cited_results = []

    if not cfg.skip_analysis:
        ui.push_status("analysing")
        body = f"{ctx_tail}\n\nUSER QUESTION: {user_text}"
        try:
            raw = call_model(
                _build_messages(prompts.ANALYSIS, body, images, audios),
                max_tokens=768, temperature=0.1, timeout=cfg.timeout,
            )
            parsed = _extract_json(raw.get("text", ""))
            if parsed and "needs_retrieval" in parsed:
                analysis = parsed
        except Exception:
            pass

    # Model requested a hi-res capture for the response pass
    if analysis and analysis.get("capture_hires") and capture_fn:
        hi = capture_fn()
        if hi and hi.exists() and hi not in images:
            images.append(hi)
            if live_fn:
                live_fn("[vision] hi-res captured on model request")

    if analysis and analysis.get("needs_retrieval") and analysis.get("queries"):
        retrieval_queries = [str(q) for q in analysis["queries"] if q][:4]

    # ── retrieval — snippets first ────────────────────────────────────────────
    if not cfg.no_retrieval and retrieval_queries:
        ui.push_status("retrieving", f"{len(retrieval_queries)} queries")
        cited_results = retrieval.retrieve(retrieval_queries)
        if live_fn and cited_results:
            qs = ", ".join(f'"{q}"' for q in retrieval_queries[:2])
            live_fn(f"[retrieval] {len(cited_results)} sources for {qs}")

    # ── pass 2: response (snippets) ───────────────────────────────────────────
    ui.push_status("responding")
    snippet_block = format_snippets(cited_results) if cited_results else ""
    parts = [ctx_tail]
    if snippet_block:
        parts.append(snippet_block)
    if analysis and analysis.get("situation"):
        parts.append(f"[SITUATION] {analysis['situation']}")
    parts.append(f"USER QUESTION: {user_text}")

    try:
        raw_resp = call_model(
            _build_messages(prompts.RESPONSE, "\n\n".join(parts), images, audios),
            max_tokens=cfg.max_tokens, temperature=cfg.temperature, timeout=cfg.timeout,
        )
        resp_text = raw_resp.get("text", "")
        response  = _extract_json(resp_text) or _fallback_response(resp_text)
    except Exception as e:
        response = _fallback_response(str(e))

    # ── expand sources if model requested full text ───────────────────────────
    expand_nums = [n for n in response.get("expand_sources", [])
                   if isinstance(n, int)]
    if expand_nums and cited_results:
        by_num = {r.citation_num: r for r in cited_results}
        to_expand = [by_num[n] for n in expand_nums if n in by_num]
        if to_expand:
            if live_fn:
                live_fn(f"[retrieval] expanding {len(to_expand)} sources to full text")
            ui.push_status("expanding", f"{len(to_expand)} sources")
            full_block = "[EXPANDED SOURCES — full text]\n" + format_for_model(to_expand)
            parts2 = [ctx_tail, snippet_block, full_block]
            if analysis and analysis.get("situation"):
                parts2.append(f"[SITUATION] {analysis['situation']}")
            parts2.append(f"USER QUESTION: {user_text}")
            try:
                raw2 = call_model(
                    _build_messages(prompts.RESPONSE, "\n\n".join(parts2), images, audios),
                    max_tokens=cfg.max_tokens, temperature=cfg.temperature,
                    timeout=cfg.timeout,
                )
                t2 = raw2.get("text", "")
                response = _extract_json(t2) or response
            except Exception:
                pass   # keep first-pass response if expansion fails

    controls     = response.get("controls") or {}
    latency_ms   = int((time.monotonic() - ts_start) * 1000)
    answer       = str(response.get("answer_text", ""))
    note_compact = str(response.get("note_compact", ""))

    if note_compact and live_fn:
        live_fn(note_compact)   # rolling narrative: model's synthesized note

    if cited_results:
        answer += format_citations(cited_results)

    # ── write turn to context + log ───────────────────────────────────────────
    compact, detailed = D.turn(ts_now, user_text, answer, note_compact)
    ctx.append(ts=ts_now, kind="turn", compact=compact, detailed=detailed)

    write_turn({
        "ts":          ts_now,
        "turn_id":     turn_id,
        "user_text":   user_text,
        "analysis":    analysis,
        "queries":     retrieval_queries,
        "answer":      answer[:600],
        "note_compact": note_compact,
        "note_full":   str(response.get("note_full", "")),
        "tags":        list(response.get("context_tags", [])),
        "confidence":  response.get("confidence", 0.0),
        "latency_ms":  latency_ms,
        "modalities":  response.get("modalities_used", ["text"]),
    })

    ui.push_response(
        answer=answer,
        citations=[{"num": r.citation_num, "url": r.url, "title": r.title}
                   for r in cited_results],
        note_compact=note_compact,
        confidence=float(response.get("confidence", 0.0)),
        latency_ms=latency_ms,
    )

    return answer, controls


# ── proactive retrieval (no user question) ────────────────────────────────────

def run_proactive(
    ctx:       ContextStore,
    retrieval: RetrievalPipeline,
    live_fn:   Callable[[str], None] | None = None,
) -> None:
    """
    Called from background thread after a significant sensor event.
    Runs analysis against the current context to decide what to pre-fetch.
    Stores retrieved content in the semantic DB only — no answer, no context write.
    """
    tail = ctx.tail_for_model()
    if tail == "(no context yet)":
        return
    try:
        raw = call_model(
            _build_messages(prompts.PROACTIVE, tail, [], []),
            max_tokens=256, temperature=0.1,
        )
        parsed = _extract_json(raw.get("text", ""))
    except Exception:
        return
    if not parsed or not parsed.get("needs_retrieval"):
        return
    queries = [str(q) for q in parsed.get("queries", []) if q][:3]
    if queries:
        results = retrieval.retrieve(queries)
        if live_fn and results:
            qs = ", ".join(f'"{q}"' for q in queries[:2])
            live_fn(f"[proactive] {len(results)} sources warmed ({qs})")


# ── memory compaction (called by ContextStore background thread) ───────────────

def run_compaction(events_text: str, level: str) -> str:
    """
    Compress a block of context events into a denser summary.
    level="l1" → compress raw events into an hourly session summary (L2 entry).
    level="l2" → compress session summaries into a long-range summary (L3 entry).
    Returns empty string on failure so the store leaves its file unchanged.
    """
    prompt  = prompts.COMPACT_L1 if level == "l1" else prompts.COMPACT_L2
    max_tok = 300 if level == "l1" else 180
    try:
        raw = call_model(
            _build_messages(prompt, events_text, [], []),
            max_tokens=max_tok, temperature=0.1,
        )
        return raw.get("text", "").strip()
    except Exception:
        return ""


# ── journal (on demand / session end) ────────────────────────────────────────

def write_journal_entry(ctx: ContextStore) -> str:
    """
    Write a synthesized session journal entry to memory/journal/YYYY-MM-DD.md.
    Called explicitly (/journal command) or at clean exit.
    Returns the prose written, or "" if there was nothing to journal.
    """
    tail = ctx.tail_for_model()
    if tail == "(no context yet)":
        return ""
    try:
        raw = call_model(
            _build_messages(prompts.JOURNAL, tail, [], []),
            max_tokens=400, temperature=0.3,
        )
        entry = raw.get("text", "").strip()
    except Exception:
        return ""
    if not entry:
        return ""
    _JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    today  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ts_str = datetime.now(timezone.utc).strftime("%H:%M UTC")
    path   = _JOURNAL_DIR / f"{today}.md"
    with path.open("a", encoding="utf-8") as f:
        f.write(f"\n## {ts_str}\n\n{entry}\n")
    return entry
