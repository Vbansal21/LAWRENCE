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
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..ctx      import ContextStore
from ..ctx      import distill as D
from ..logger   import write_turn
from ..model    import (
    PRI_COMPACT, PRI_PROACTIVE,
    audio_block, call_model, image_block, note_fallback_parse, text_block,
)
from ..retrieval import RetrievalPipeline, format_snippets, format_for_model, format_citations
from ..ui       import UIConnector
from .          import prompts, schemas

REPO_ROOT = Path(__file__).resolve().parents[3]
# Journal files live under memory/journal/ — assembled by lk.admin (MDX writer).

_turn_ctr = itertools.count(1)


# ── JSON helpers ──────────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict[str, Any] | None:
    """Return the last *top-level* JSON object in text (skips thinking-block noise).

    Scans left-to-right and, on each successful decode, jumps past the parsed
    object rather than continuing into it — so a nested object (e.g. the RESPONSE
    schema's `controls: {...}`) does NOT get mistaken for the result. Taking the
    last top-level object still discards leading thinking/preamble noise.
    """
    decoder = json.JSONDecoder()
    found: dict[str, Any] | None = None
    i, n = 0, len(text)
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        try:
            val, end = decoder.raw_decode(text[i:])
            if isinstance(val, dict):
                found = val
            i += max(end, 1)          # skip past this object — don't descend into it
        except json.JSONDecodeError:
            i += 1
    return found


def _fallback_response(text: str) -> dict[str, Any]:
    # If the text looks like truncated JSON, salvage answer_text with a regex
    answer = text[:800]
    if text.lstrip().startswith("{"):
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


class AnswerTextStreamer:
    """Streams the *value* of "answer_text" out of an incrementally-decoded
    JSON envelope (the RESPONSE schema puts answer_text first, and grammar
    enforcement preserves property order — see kernel/schemas.py).

    feed() receives raw model deltas (JSON fragments); emit receives clean,
    unescaped answer text. Escape sequences and the key itself may straddle
    chunk boundaries — the internal buffer handles both. If the output never
    turns out to be JSON (schema fallback), nothing is emitted and the caller's
    final non-streamed rendering is unaffected.
    """

    _KEY = '"answer_text"'
    _ESC = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "/": "/",
            "b": "\b", "f": "\f"}

    def __init__(self, emit: Callable[[str], None]) -> None:
        self._emit  = emit
        self._buf   = ""
        self._state = 0   # 0 seek key · 1 seek opening quote · 2 in string · 3 done
        self.emitted = False

    def feed(self, chunk: str) -> None:
        if self._state == 3 or not chunk:
            return
        self._buf += chunk
        if self._state == 0:
            i = self._buf.find(self._KEY)
            if i < 0:
                self._buf = self._buf[-(len(self._KEY) - 1):] if self._buf else ""
                return
            self._buf = self._buf[i + len(self._KEY):]
            self._state = 1
        if self._state == 1:
            j = 0
            while j < len(self._buf) and self._buf[j] in " \t\r\n:":
                j += 1
            if j >= len(self._buf):
                self._buf = ""
                return
            if self._buf[j] != '"':
                self._state = 3          # malformed — stop streaming, stay safe
                return
            self._buf = self._buf[j + 1:]
            self._state = 2
        if self._state == 2:
            out: list[str] = []
            i, n = 0, len(self._buf)
            while i < n:
                c = self._buf[i]
                if c == "\\":
                    if i + 1 >= n:
                        break                         # escape straddles chunks — wait
                    e = self._buf[i + 1]
                    if e == "u":
                        if i + 6 > n:
                            break
                        try:
                            out.append(chr(int(self._buf[i + 2:i + 6], 16)))
                        except ValueError:
                            pass
                        i += 6
                        continue
                    out.append(self._ESC.get(e, e))
                    i += 2
                    continue
                if c == '"':                          # unescaped close — value done
                    if out:
                        self._emit("".join(out))
                        self.emitted = True
                    self._state = 3
                    self._buf = ""
                    return
                out.append(c)
                i += 1
            if out:
                self._emit("".join(out))
                self.emitted = True
            self._buf = self._buf[i:]


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
    max_tokens:        int         = 2048
    temperature:       float       = 0.2
    timeout:           int         = 300
    skip_analysis:     bool        = False
    no_retrieval:      bool        = False
    allow_images:      bool        = True   # False for text-only / non-vision models
    allow_audio:       bool        = True   # False for models without audio input
    # Advanced sampling — None = use backend default (omitted from payload)
    top_p:              float | None = None
    min_p:              float | None = None
    top_k:              int   | None = None
    typical_p:          float | None = None
    tfs_z:              float | None = None
    repeat_penalty:     float | None = None
    repeat_last_n:      int   | None = None
    presence_penalty:   float | None = None
    frequency_penalty:  float | None = None
    mirostat:           int   | None = None
    mirostat_tau:       float | None = None
    mirostat_eta:       float | None = None
    dry_multiplier:     float | None = None
    dry_base:           float | None = None
    dry_allowed_length: int   | None = None
    seed:               int   | None = None
    stop_sequences:     list[str] | None = None


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
    tasks_fn:   Callable[[dict], None]    | None = None,
    stream_fn:  Callable[[str], None]     | None = None,
) -> tuple[str, dict]:
    turn_id  = f"t-{next(_turn_ctr):04d}"
    ts_start = time.monotonic()
    ts_now   = datetime.now(timezone.utc).isoformat()
    ctx_tail = ctx.tail_for_model()

    # Drop media the model can't accept (text-only / vision-only models). Sending
    # an image_url/audio_url block to a model without that modality errors.
    images = list(images) if cfg.allow_images else []
    audios = list(audios) if cfg.allow_audio  else []
    if not cfg.allow_images:
        capture_fn = None   # don't bother capturing hi-res for a non-vision model

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
                schema=schemas.ANALYSIS, role="analysis",
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

    _sampling = dict(
        top_p=cfg.top_p, min_p=cfg.min_p, top_k=cfg.top_k,
        typical_p=cfg.typical_p, tfs_z=cfg.tfs_z,
        repeat_penalty=cfg.repeat_penalty, repeat_last_n=cfg.repeat_last_n,
        presence_penalty=cfg.presence_penalty, frequency_penalty=cfg.frequency_penalty,
        mirostat=cfg.mirostat, mirostat_tau=cfg.mirostat_tau, mirostat_eta=cfg.mirostat_eta,
        dry_multiplier=cfg.dry_multiplier, dry_base=cfg.dry_base,
        dry_allowed_length=cfg.dry_allowed_length,
        seed=cfg.seed, stop=cfg.stop_sequences or None,
    )
    # Live answer streaming: deltas are raw JSON fragments; the streamer
    # extracts only the answer_text value (schemas.RESPONSE puts it first).
    answer_stream = AnswerTextStreamer(stream_fn) if stream_fn else None
    try:
        raw_resp = call_model(
            _build_messages(prompts.RESPONSE, "\n\n".join(parts), images, audios),
            max_tokens=cfg.max_tokens, temperature=cfg.temperature, timeout=cfg.timeout,
            schema=schemas.RESPONSE, role="response",
            stream_fn=answer_stream.feed if answer_stream else None,
            **_sampling,
        )
        resp_text = raw_resp.get("text", "")
        response  = _extract_json(resp_text)
        if response is None:
            note_fallback_parse()
            response = _fallback_response(resp_text)
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
                # No streaming on the expansion pass — its answer replaces the
                # first one; streaming both would duplicate text in the UI.
                raw2 = call_model(
                    _build_messages(prompts.RESPONSE, "\n\n".join(parts2), images, audios),
                    max_tokens=cfg.max_tokens, temperature=cfg.temperature,
                    timeout=cfg.timeout, schema=schemas.RESPONSE, role="response", **_sampling,
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

    # Self-curated tasks / remember points — the model decides these on its own.
    if tasks_fn:
        proposals = {
            "tasks":    response.get("tasks") or [],
            "remember": response.get("remember") or [],
        }
        if proposals["tasks"] or proposals["remember"]:
            try:
                tasks_fn(proposals)
            except Exception:
                pass

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
    live_fn:   Callable[[str], None]  | None = None,
    present_fn: Callable[[dict], None] | None = None,
) -> None:
    """
    Called from a background thread after a significant sensor event — this is the
    autonomous loop: realize context → retrieve → (optionally) surface.

      1. PROACTIVE pass: does the current context warrant pre-fetching? which queries?
      2. retrieve(queries) → warms the semantic DB (silent).
      3. if present_fn is given, PROACTIVE_BRIEF pass: is anything worth surfacing
         unprompted? If so, emit a structured finding via present_fn and record it
         to context (kind="finding") so it is remembered and not repeated.

    With present_fn=None it behaves as before: warm the cache, surface nothing.
    """
    tail = ctx.tail_for_model()
    if tail == "(no context yet)":
        return
    try:
        # PRI_PROACTIVE is droppable: if the local inference slot is busy the
        # call returns empty text ("skipped") and we simply bail out below.
        raw = call_model(
            _build_messages(prompts.PROACTIVE, tail, [], []),
            max_tokens=512, temperature=0.1,   # headroom for the thinking block
            schema=schemas.PROACTIVE, priority=PRI_PROACTIVE, role="proactive",
        )
        parsed = _extract_json(raw.get("text", ""))
    except Exception:
        return
    if not parsed or not parsed.get("needs_retrieval"):
        return
    queries = [str(q) for q in parsed.get("queries", []) if q][:3]
    if not queries:
        return

    results = retrieval.retrieve(queries)
    if live_fn and results:
        qs = ", ".join(f'"{q}"' for q in queries[:2])
        live_fn(f"[proactive] {len(results)} sources warmed ({qs})")

    # ── surface a finding unprompted (the "present nicely" step) ─────────────────
    if present_fn is None or not results:
        return
    snippet_block = format_snippets(results)
    body = f"{tail}\n\n{snippet_block}"
    try:
        raw2 = call_model(
            _build_messages(prompts.PROACTIVE_BRIEF, body, [], []),
            max_tokens=1024, temperature=0.2,
            schema=schemas.PROACTIVE_BRIEF, priority=PRI_PROACTIVE, role="proactive",
        )
        brief = _extract_json(raw2.get("text", ""))
    except Exception:
        return
    if not brief or not brief.get("surface"):
        return
    headline = str(brief.get("headline", "")).strip()[:120]
    insight  = str(brief.get("insight", "")).strip()
    if not insight:
        return

    finding = {
        "headline":  headline,
        "insight":   insight,
        "citations": [{"num": r.citation_num, "title": r.title, "url": r.url}
                      for r in results],
    }
    present_fn(finding)

    # Record so the agent remembers it surfaced this (and the user can see it later).
    ts = datetime.now(timezone.utc).isoformat()
    ctx.append(
        ts=ts, kind="finding",
        compact=f"[FOUND] {headline}",
        detailed=f"[PROACTIVE FINDING] {headline}\n{insight}",
    )


# ── memory compaction (called by ContextStore background thread) ───────────────

def run_compaction(events_text: str, level: str) -> str:
    """
    Compress a block of context events into a denser summary.
    level="l1" → compress raw events into an hourly session summary (L2 entry).
    level="l2" → compress session summaries into a long-range summary (L3 entry).
    Returns empty string on failure so the store leaves its file unchanged.
    """
    prompt  = prompts.COMPACT_L1 if level == "l1" else prompts.COMPACT_L2
    # Headroom for the thinking block before the summary (same reason as the
    # journal): with too small a ceiling the budget is spent thinking and the
    # summary comes back empty, so no L2/L3 entry is ever stored. The model
    # stops at EOS once the (short) summary is done.
    max_tok = 768 if level == "l1" else 512
    try:
        raw = call_model(
            _build_messages(prompt, events_text, [], []),
            max_tokens=max_tok, temperature=0.1,
            priority=PRI_COMPACT, role="compact",
        )
        return raw.get("text", "").strip()
    except Exception:
        return ""


# ── journal (on demand / session end) ────────────────────────────────────────

def write_journal_entry(ctx: ContextStore) -> str:
    """
    Write a synthesized session journal entry to memory/journal/YYYY-MM-DD.mdx.
    Called explicitly (/journal command) or at clean exit.

    The model writes a title line + prose; admin.append_journal_entry assembles
    it into a browseable MDX journal (frontmatter + timestamped, titled sections).
    Returns the prose written, or "" if there was nothing to journal.
    """
    tail = ctx.tail_for_model()
    if tail == "(no context yet)":
        return ""
    try:
        # Headroom matters: thinking models (e.g. Gemma 4) spend tokens in a
        # thought block before the answer channel, and the amount of thinking
        # scales with context size. 400 ran out mid-thought on a large session
        # (→ _strip_thinking returned ""). The model stops at EOS, so a high
        # ceiling isn't wasteful — it just guarantees room to reach the answer.
        raw = call_model(
            _build_messages(prompts.JOURNAL, tail, [], []),
            max_tokens=2048, temperature=0.3, role="journal",
        )
        entry = raw.get("text", "").strip()
    except Exception:
        return ""
    if not entry:
        return ""

    from ..admin import append_journal_entry, day_tags, parse_journal_output
    parsed = parse_journal_output(entry)
    append_journal_entry(parsed, tags=day_tags())
    # Return a short human-readable confirmation (summary, falling back to title)
    return parsed.get("summary") or parsed.get("title") or ""
