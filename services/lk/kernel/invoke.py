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

import difflib
import itertools
import json
import os
import re
import threading
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
    PRI_COMPACT, PRI_PROACTIVE, TurnCancelled,
    audio_block, call_model, image_block, note_fallback_parse, text_block,
)
from ..retrieval import (
    RetrievalPipeline, RetrievalEngine, MemoryIndex, format_snippets, format_for_model,
    format_citations, format_recall,
)
from ..ui       import UIConnector
from .          import prompts, schemas, turncache

REPO_ROOT = Path(__file__).resolve().parents[3]
# Journal files live under memory/journal/ — assembled by lk.admin (MDX writer).

_turn_ctr = itertools.count(1)


@dataclass(frozen=True)
class ContextSnapshot:
    """One stable rolling-context view shared by every pass in a run."""
    version: int
    text: str


def freeze_context(ctx: ContextStore) -> ContextSnapshot:
    """Read context without mixing two concurrently changing versions."""
    for _ in range(3):
        before = ctx.version()
        text = ctx.tail_for_model()
        after = ctx.version()
        if before == after:
            return ContextSnapshot(after, text)
    return ContextSnapshot(after, text)


# ── §9 proactive dedup / stale-guard tunables ─────────────────────────────────
# How many context-version advances (new appends/archives from concurrent user or
# sensor activity) are tolerated between the start of a proactive run and the
# moment it would surface, before the finding is judged stale and dropped.
def _proactive_stale_delta() -> int:
    try:
        return max(0, int(os.getenv("LK_PROACTIVE_STALE_DELTA", "3")))
    except ValueError:
        return 3


# Similarity ratio (0..1) at/above which a candidate finding is treated as a
# duplicate of a recent one and dropped. difflib.SequenceMatcher on normalised
# headline+insight — reuse the stdlib rather than a fuzzy-match dependency.
def _finding_dedup_ratio() -> float:
    try:
        return min(1.0, max(0.0, float(os.getenv("LK_FINDING_DEDUP_RATIO", "0.85"))))
    except ValueError:
        return 0.85


def _norm_finding(headline: str, insight: str) -> str:
    """Collapse a finding to a comparison key: lowercased, whitespace-normalised
    headline+insight. Compares meaning, not exact bytes (§9 interaction rule)."""
    text = f"{headline}\n{insight}".lower()
    return re.sub(r"\s+", " ", text).strip()


def _is_duplicate_finding(headline: str, insight: str, recent: list[dict]) -> bool:
    """True if this finding repeats a recent one — by exact normalised headline or
    by SequenceMatcher ratio over the combined headline+insight."""
    if not recent:
        return False
    cand = _norm_finding(headline, insight)
    cand_head = re.sub(r"\s+", " ", headline.lower()).strip()
    ratio = _finding_dedup_ratio()
    for prev in recent:
        p_head = re.sub(r"\s+", " ", str(prev.get("headline", "")).lower()).strip()
        if cand_head and cand_head == p_head:
            return True
        prev_norm = _norm_finding(str(prev.get("headline", "")), str(prev.get("insight", "")))
        if difflib.SequenceMatcher(None, cand, prev_norm).ratio() >= ratio:
            return True
    return False


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
    # N-22: optional turn-WIDE wall-clock ceiling across all stages (retrieval +
    # response + expansion). None = off (per-call `timeout` still bounds each op);
    # set it and the composed watchdog aborts the whole turn via TurnCancelled.
    turn_deadline_s:   float | None = None
    skip_analysis:     bool        = False
    no_retrieval:      bool        = False
    deep_search:       bool        = False   # UI deepSearch flag → wider/deeper retrieval
    allow_images:      bool        = True   # False for text-only / non-vision models
    allow_audio:       bool        = True   # False for models without audio input
    allow_remote_media: bool       = False  # explicit user attachment only
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
    memory:     MemoryIndex | None = None,
    engine:     RetrievalEngine | None = None,
    cfg:        TurnConfig,
    images:     list[Path],
    audios:     list[Path],
    ui:         UIConnector,
    capture_fn: Callable[[], Path | None] | None = None,
    live_fn:    Callable[[str], None]     | None = None,
    tasks_fn:   Callable[[dict], None]    | None = None,
    actions_fn: Callable[[list[dict[str, Any]], int], list[dict[str, Any]]] | None = None,
    stream_fn:  Callable[[str], None]     | None = None,
    should_stop: Callable[[], bool]       | None = None,
    on_refine:  Callable[[dict], None]    | None = None,
    elevator:   Any                              = None,
) -> tuple[str, dict]:
    turn_id  = f"t-{next(_turn_ctr):04d}"
    ts_start = time.monotonic()
    ts_now   = datetime.now(timezone.utc).isoformat()

    # N-22: compose a turn-wide watchdog into should_stop. Every stage already
    # honors should_stop (D-09); ORing a single turn deadline in here extends that
    # coverage to the WHOLE pipeline without touching each call site. Off by
    # default (turn_deadline_s=None) so existing behavior is unchanged.
    if cfg.turn_deadline_s and cfg.turn_deadline_s > 0:
        _caller_stop = should_stop
        _turn_deadline = ts_start + cfg.turn_deadline_s

        def should_stop() -> bool:   # noqa: F811 - intentional watchdog wrap
            if _caller_stop and _caller_stop():
                return True
            return time.monotonic() > _turn_deadline

    snapshot = freeze_context(ctx)
    ctx_tail = snapshot.text

    # Drop media the model can't accept (text-only / vision-only models). Sending
    # an image_url/audio_url block to a model without that modality errors.
    images = list(images) if cfg.allow_images else []
    audios = list(audios) if cfg.allow_audio  else []
    if not cfg.allow_images:
        capture_fn = None   # don't bother capturing hi-res for a non-vision model

    analysis: dict[str, Any] | None = None
    retrieval_queries: list[str] = []
    cited_results = []
    recall_block = ""

    if engine is not None and not cfg.no_retrieval and user_text.strip():
        # ── unified retrieval (N-05): DISCERN own-context → per-category PARALLEL
        # chains (notes+doc+web) → final collective cited bundle. This subsumes the
        # separate analysis + recall + single-shot retrieve path: own memory is now a
        # cited category in ONE consistent bundle, not a side block. Best-effort.
        ui.push_status("retrieving")
        try:
            # N-32: memoize the gather by (query, context identity, deep). A
            # regenerate / proactive re-probe of the same query+context reuses the
            # bundle instead of re-running the whole engine. Miss == today's path.
            with turncache.stage_timer("retrieve"):
                g = turncache.memoize(
                    "gather", (user_text, ctx_tail, cfg.deep_search),
                    lambda: engine.gather(
                        user_text, short_ctx=ctx_tail, deep=cfg.deep_search,
                        timeout=cfg.timeout, should_stop=should_stop, live_fn=live_fn,
                    ),
                )
            cited_results = g.evidence
            analysis = {"situation": g.context_understanding, "capture_hires": g.capture_hires}
            retrieval_queries = [q for qs in g.queries.values() for q in qs]
        except TurnCancelled:
            raise
        except Exception:
            cited_results = []
    else:
        # ── legacy / no-engine path: own-memory recall block + single analysis +
        # single-shot retrieve (kept for back-compat, tests, and engine-disabled). ──
        if memory is not None and user_text.strip():
            try:
                recalled = memory.recall(user_text, k=6)
                recall_block = format_recall(recalled)
                if live_fn and recalled:
                    kinds = ", ".join(sorted({r.source_kind for r in recalled}))
                    live_fn(f"[recall] {len(recalled)} memory items ({kinds})")
            except Exception:
                recall_block = ""

        if not cfg.skip_analysis:
            ui.push_status("analysing")
            body = f"{ctx_tail}\n\nUSER QUESTION: {user_text}"
            try:
                raw = call_model(
                    _build_messages(prompts.ANALYSIS, body, images, audios),
                    max_tokens=768, temperature=0.1, timeout=cfg.timeout,
                    schema=schemas.ANALYSIS, role="analysis", should_stop=should_stop,
                    allow_remote_media=cfg.allow_remote_media,
                )
                parsed = _extract_json(raw.get("text", ""))
                if parsed and "needs_retrieval" in parsed:
                    analysis = parsed
            except TurnCancelled:
                raise
            except Exception:
                pass

        if analysis and analysis.get("needs_retrieval") and analysis.get("queries"):
            retrieval_queries = [str(q) for q in analysis["queries"] if q][:4]

        if not cfg.no_retrieval and retrieval_queries:
            ui.push_status("retrieving", f"{len(retrieval_queries)} queries")
            with turncache.stage_timer("retrieve"):
                cited_results = turncache.memoize(
                    "retrieve", (tuple(retrieval_queries),),
                    lambda: retrieval.retrieve(retrieval_queries),
                )
            if live_fn and cited_results:
                qs = ", ".join(f'"{q}"' for q in retrieval_queries[:2])
                live_fn(f"[retrieval] {len(cited_results)} sources for {qs}")

    # Model (or engine) requested a hi-res capture for the response pass
    if analysis and analysis.get("capture_hires") and capture_fn:
        hi = capture_fn()
        if hi and hi.exists() and hi not in images:
            images.append(hi)
            if live_fn:
                live_fn("[vision] hi-res captured on model request")

    # ── pass 2: response (snippets) ───────────────────────────────────────────
    ui.push_status("responding")
    snippet_block = format_snippets(cited_results) if cited_results else ""
    parts = [ctx_tail]
    if recall_block:
        parts.append(recall_block)
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
    if should_stop and should_stop():           # cancelled before the first token
        raise TurnCancelled()
    try:
        with turncache.stage_timer("response"):
            raw_resp = call_model(
                _build_messages(prompts.RESPONSE, "\n\n".join(parts), images, audios),
                max_tokens=cfg.max_tokens, temperature=cfg.temperature, timeout=cfg.timeout,
                schema=schemas.RESPONSE, role="response",
                stream_fn=answer_stream.feed if answer_stream else None,
                should_stop=should_stop,
                allow_remote_media=cfg.allow_remote_media,
                **_sampling,
            )
        resp_text = raw_resp.get("text", "")
        response  = _extract_json(resp_text)
        if response is None:
            note_fallback_parse()
            response = _fallback_response(resp_text)
    except TurnCancelled:
        raise   # never fabricate an answer or write memory for a cancelled turn
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
                    timeout=cfg.timeout, schema=schemas.RESPONSE, role="response",
                    should_stop=should_stop,
                    allow_remote_media=cfg.allow_remote_media, **_sampling,
                )
                t2 = raw2.get("text", "")
                response = _extract_json(t2) or response
            except TurnCancelled:
                raise
            except Exception:
                pass   # keep first-pass response if expansion fails

    controls     = response.get("controls") or {}
    if actions_fn and response.get("actions"):
        try:
            controls = dict(controls)
            controls["actionProposals"] = actions_fn(
                list(response.get("actions") or []), snapshot.version)
        except Exception:
            pass
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

    # Live incremental indexing (closes the N-02→N-06→N-07 loop): the just-finished
    # turn becomes recallable immediately — lexical/graph now; the embedding is filled
    # by the background backfill / `lk reindex`. Best-effort, never blocks the turn.
    if memory is not None:
        try:
            memory.upsert(turn_id, "turn", f"{user_text}\n\n{answer}"[:2000],
                          ts=time.time(), title="chat turn", embed=False)
        except Exception:
            pass

    write_turn({
        "ts":          ts_now,
        "turn_id":     turn_id,
        "context_version": snapshot.version,
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

    # ── §P/N-71: durable-memory formation (P_dist promotion + S_link auto-link) ─
    # Promote a genuinely worth-keeping turn into a linked Zettelkasten note — the
    # soul's distillation/linking half (Eq.3/Eq.4, Alg.2). Model-free, conservative,
    # best-effort: most small-talk turns promote nothing. Runs AFTER the answer is
    # surfaced and never blocks or breaks the turn.
    if memory is not None and getattr(memory, "notes", None) is not None:
        try:
            from ..ctx.promote import promote_turn
            promote_turn(
                memory.notes, ts=ts_now, user_text=user_text,
                answer=str(response.get("answer_text", "")),
                note_full=str(response.get("note_full", "")),
                note_compact=note_compact,
                tags=list(response.get("context_tags", [])),
                confidence=float(response.get("confidence", 0.0) or 0.0),
                has_tasks=bool(response.get("tasks")),
                has_actions=bool(response.get("actions")),
                has_remember=bool(response.get("remember")),
            )
        except Exception:
            pass

    # ── WS-R/R1: slow loop ────────────────────────────────────────────────────
    # The fast answer is now surfaced. Behind slow_loop:on, dispatch a bounded
    # critique-refine in a daemon thread that may elevate a materially better
    # answer into THIS turn (R2 gate). Non-blocking; a no-op when slow_loop:off.
    if on_refine is not None:
        try:
            from .refine import dispatch_refine
            dispatch_refine(
                user_text, answer, ctx=ctx, retrieval=retrieval,
                fast_confidence=float(response.get("confidence", 0.0) or 0.0),
                on_refine=on_refine, elevator=elevator, turn_id=turn_id, live_fn=live_fn,
            )
        except Exception:
            pass

    return answer, controls


# ── proactive retrieval (no user question) ────────────────────────────────────

# §P/N-07 proactive observability: the loop is wired from four drivers (vision /
# audio / cognitive-tick / spool) onto this ONE throttled convergence. It is
# droppable + interval-gated by design, so silence is EXPECTED — these counters
# make "is it actually firing?" answerable at runtime instead of guessed.
# Thread-safe: proactive runs in daemon threads.
_PROACTIVE_LOCK = threading.Lock()
_PROACTIVE_STATS: dict[str, int] = {
    "calls": 0, "warmed": 0, "surfaced": 0, "stale": 0, "dup": 0,
    "skipped": 0, "error": 0,
}


def _pstat(key: str) -> None:
    with _PROACTIVE_LOCK:
        _PROACTIVE_STATS[key] = _PROACTIVE_STATS.get(key, 0) + 1


def proactive_stats() -> dict[str, int]:
    """Snapshot of proactive-loop outcomes since process start (N-07 observability).
    calls=invocations · warmed=had evidence · surfaced=shown to user · stale/dup=
    dropped by the §9 guards · skipped=no context / no retrieval / busy slot · error."""
    with _PROACTIVE_LOCK:
        return dict(_PROACTIVE_STATS)


def run_proactive(
    ctx:       ContextStore,
    retrieval: RetrievalPipeline,
    live_fn:   Callable[[str], None]  | None = None,
    present_fn: Callable[[dict], None] | None = None,
    *,
    engine:    RetrievalEngine | None = None,
    memory:    MemoryIndex | None = None,
) -> bool:
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
    # §9 stale guard: snapshot the context version BEFORE we spend time realizing
    # + retrieving + briefing. If the user (or sensors) move the context on too far
    # while we work, the conclusion we are about to surface is about an old state —
    # we drop it at the end instead of surfacing it late.
    _pstat("calls")
    snapshot = freeze_context(ctx)
    start_ver = snapshot.version
    tail = snapshot.text
    if tail == "(no context yet)":
        _pstat("skipped")
        return False

    if engine is not None:
        # Unified engine (N-05/N-07): DISCERN the live stream → per-category parallel
        # retrieval (own memory + doc + web) → a cited bundle. Proactive findings now
        # ride the SAME notes+doc+web evidence a user turn would — not web alone. The
        # engine's plan/assess calls are PRI_PROACTIVE (droppable when the slot is busy).
        try:
            g = engine.gather("", short_ctx=tail, proactive=True,
                              priority=PRI_PROACTIVE, live_fn=live_fn)
        except Exception:
            _pstat("error")
            return False
        results = g.evidence
    else:
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
            _pstat("error")
            return False
        if not parsed or not parsed.get("needs_retrieval"):
            _pstat("skipped")
            return False
        queries = [str(q) for q in parsed.get("queries", []) if q][:3]
        if not queries:
            _pstat("skipped")
            return False
        results = retrieval.retrieve(queries)

    if results:
        _pstat("warmed")
    if live_fn and results:
        live_fn(f"[proactive] {len(results)} sources warmed")

    # ── surface a finding unprompted (the "present nicely" step) ─────────────────
    if present_fn is None or not results:
        if not results:
            _pstat("skipped")
        return bool(results)
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
        return True
    if not brief or not brief.get("surface"):
        _pstat("skipped")
        return True
    headline = str(brief.get("headline", "")).strip()[:120]
    insight  = str(brief.get("insight", "")).strip()
    if not insight:
        return True

    # §9 stale guard: the DB is already warmed (kept), but if the context advanced
    # past the tolerance while we were working, this conclusion is about an old
    # state — drop it silently rather than surface a late, possibly-irrelevant card.
    if ctx.version() - start_ver > _proactive_stale_delta():
        _pstat("stale")
        return True

    # §9 dedup: don't repeat a finding we recently surfaced. Compares headline +
    # insight by meaning (normalised + SequenceMatcher), not exact text.
    if _is_duplicate_finding(headline, insight, ctx.recent_findings()):
        _pstat("dup")
        return True

    finding = {
        "headline":  headline,
        "insight":   insight,
        "citations": [{"num": r.citation_num, "title": r.title, "url": r.url}
                      for r in results],
    }
    present_fn(finding)
    _pstat("surfaced")

    # Record so the agent remembers it surfaced this (and the user can see it later).
    ts = datetime.now(timezone.utc).isoformat()
    ctx.append(
        ts=ts, kind="finding",
        compact=f"[FOUND] {headline}",
        detailed=f"[PROACTIVE FINDING] {headline}\n{insight}",
    )
    # Live-index the finding so it is recallable in the same session (and so the next
    # proactive pass's own-memory arm sees what was already surfaced) — best-effort.
    if memory is not None:
        try:
            memory.upsert(f"finding-{ts}", "finding", f"{headline}\n{insight}",
                          title=headline[:80], embed=False)
        except Exception:
            pass
    return True


# ── perception: extraction (called from the observer/spool path) ───────────────

def run_extract(slice_text: str, kind: str = "event") -> dict | None:
    """Distil ONE raw sensor slice into a clean entry — WS-P/B1, the keystone.

    Deliberately context-free (no rolling memory) so the model focuses purely on
    the slice (clean focus), and **droppable** (PRI_PROACTIVE): if the local slot
    is busy it returns empty and we yield — extraction must NEVER block a user
    turn or the capture loop. Returns ``{clean, significance, tags}`` or ``None``
    on skip/failure, so the caller falls back to logging the raw slice (the
    degraded path — perception keeps working without the model).
    """
    slice_text = (slice_text or "").strip()
    if not slice_text:
        return None
    try:
        raw = call_model(
            _build_messages(prompts.EXTRACT, slice_text[:4000], [], []),
            max_tokens=320, temperature=0.1,
            schema=schemas.EXTRACT, priority=PRI_PROACTIVE, role="extract",
        )
    except Exception:
        return None
    parsed = _extract_json(raw.get("text", ""))
    if not parsed or not str(parsed.get("clean", "")).strip():
        return None
    try:
        sig = float(parsed.get("significance", 0.0) or 0.0)
    except (TypeError, ValueError):
        sig = 0.0
    return {
        "clean":        str(parsed.get("clean", "")).strip(),
        "significance": max(0.0, min(1.0, sig)),
        "tags":         [str(t) for t in (parsed.get("tags") or []) if t][:8],
    }


# ── memory compaction (called by ContextStore background thread) ───────────────

def run_compaction(events_text: str, layer: Any) -> str:
    """
    Compress a block of context events into a denser summary (one tier → next).

    The store passes the source ``Layer`` (M2): we route on ``layer.compact_role``
    (so a deep tier can use a different/cheaper/longer-context model purely via
    config), size the summary to ``layer.compact_target_tokens``, and pick the
    raw vs. summary prompt from ``layer.is_raw``. A bare string name is also
    accepted for backward-compat / direct callers ("l1" ⇒ raw prompt).

    Returns empty string on failure so the store leaves its file bounded but
    un-summarised (the degraded path — memory never depends on one model).
    """
    if isinstance(layer, str):
        role, is_raw, target = "compact", (layer == "l1"), 0
    else:
        role   = getattr(layer, "compact_role", "compact") or "compact"
        is_raw = bool(getattr(layer, "is_raw", False))
        target = int(getattr(layer, "compact_target_tokens", 0) or 0)
    prompt = prompts.COMPACT_L1 if is_raw else prompts.COMPACT_L2
    # Headroom for the thinking block before the summary (same reason as the
    # journal): with too small a ceiling the budget is spent thinking and the
    # summary comes back empty, so no entry is ever stored. The model stops at
    # EOS once the (short) summary is done, so a high ceiling is not wasteful.
    max_tok = target if target > 0 else (768 if is_raw else 512)
    try:
        raw = call_model(
            _build_messages(prompt, events_text, [], []),
            max_tokens=max_tok, temperature=0.1,
            priority=PRI_COMPACT, role=role,
        )
        return raw.get("text", "").strip()
    except Exception:
        return ""


# ── journal (on demand / session end) ────────────────────────────────────────

def write_journal_entry(ctx: ContextStore, *, retrieval: Any = None,
                        memory: Any = None,
                        live_fn: Callable[[str], None] | None = None) -> str:
    """
    Write a journal entry to memory/journal/YYYY-MM-DD.mdx. Called explicitly
    (/journal command), at clean exit, and autonomously from the cognitive tick.

    Delegates to the WS-J engine (kernel/journal.run_journal): an autonomous,
    first-person, rolling-revision journal — it drafts a new first-person entry
    from the trailing window + live context and lightly trims the window in place.
    Returns the new entry's title, or "" if there was nothing to journal.
    """
    from .journal import run_journal
    return run_journal(ctx, retrieval=retrieval, memory=memory, live_fn=live_fn)
