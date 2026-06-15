"""WS-J — the autonomous, first-person, rolling-revision journal engine.

The old journal was a third-person, append-only artifact written only on /journal
or at exit. WS-J replaces it: as LAWRENCE comprehends ongoing activity (the same
rolling context a turn sees), it writes journal entries **in the user's own voice**
per time-period, and keeps the file tight by lightly re-trimming the trailing
window in place instead of growing forever. The journal thereby becomes the day's
DURABLE episodic memory (the rolling tiers stay short-term/lossy).

One journal pass (`run_journal`):
  1. DRAFT  — read the trailing window of recent entries + the live rolling context
     (+ optional, throttled web) and write ONE new first-person entry; persist it
     immediately (this alone == a correct, if slightly redundant, journal — the
     degraded floor).
  2. REVISE — best-effort: lightly trim the trailing window so the file grows
     slowly and without duplication. A model-chosen, conservative tightening pass,
     NOT a rewrite. If it fails or finds nothing, the appended draft stands.

Design guarantees (mirrors the rest of the kernel):
  • Single writer / atomic — every mutation goes through admin.load_journal →
    save_journal under admin._journal_lock (locked + temp+os.replace).
  • Degraded path — any model failure falls back to the legacy single-shot append
    (or simply skips); journalling NEVER crashes the caller or loses the day.
  • Provider-agnostic — all model selection is behind the `journal` role seam (I3).
  • Day-boundary + web are pluggable seams (admin.journal_day_key; _maybe_web_*),
    so the future "dynamic running-session" boundary and per-entry retrieval slot
    in with no caller change.
"""
from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from .. import admin
from ..model import PRI_COMPACT, call_model
from . import prompts, schemas
from .invoke import _build_messages, _extract_json


# ── config knobs (round-trip through config._ENV_MAP / the GUI settings) ───────

def enabled() -> bool:
    """Autonomous journalling runs unless LK_JOURNAL is explicitly falsey."""
    return os.environ.get("LK_JOURNAL", "1").strip().lower() not in ("0", "false", "no", "off")


def _window_k() -> int:
    """How many trailing entries the draft reads and the revise pass may trim."""
    try:
        return max(1, int(os.environ.get("LK_JOURNAL_WINDOW", "3")))
    except (TypeError, ValueError):
        return 3


def _revise_enabled() -> bool:
    return os.environ.get("LK_JOURNAL_REVISE", "1").strip().lower() not in ("0", "false", "no", "off")


def _web_enabled() -> bool:
    return os.environ.get("LK_JOURNAL_WEB", "0").strip().lower() in ("1", "true", "yes", "on")


def _web_min_gap() -> float:
    """Floor (seconds) between journal web retrievals — a cost ceiling for the
    all-day autonomous loop (the per-entry retrieval is throttled like proactive)."""
    try:
        return float(os.environ.get("LK_JOURNAL_WEB_MIN_GAP", "900"))
    except (TypeError, ValueError):
        return 900.0


_web_last = [0.0]   # monotonic time of the last journal web retrieval


# ── web seam (decision: per-entry, model-decided, THROTTLED) ───────────────────

def _maybe_web_context(window: list[admin.JournalEntry], tail: str, retrieval: Any) -> str:
    """Optionally fold a little fresh web context into the draft. Off by default;
    when on, it is rate-limited (a cost ceiling for all-day autonomy). v1 keeps the
    seam minimal — a future version lets the draft request its own queries."""
    if retrieval is None or not _web_enabled():
        return ""
    now = time.monotonic()
    if now - _web_last[0] < _web_min_gap():
        return ""
    open_threads = (window[-1].body if window else "")[-400:]
    seed = (open_threads or tail[-400:]).strip()
    if not seed:
        return ""
    try:
        from ..retrieval import format_snippets
        results = retrieval.retrieve([seed[:120]])
    except Exception:
        return ""
    _web_last[0] = now
    if not results:
        return ""
    try:
        return "[WEB CONTEXT]\n" + format_snippets(results)
    except Exception:
        return ""


# ── prompt input builders ──────────────────────────────────────────────────────

def _render_window(window: list[admin.JournalEntry]) -> str:
    if not window:
        return "(no earlier entries today — this is the first)"
    out = []
    for e in window:
        out.append(f"[{e.id} · {e.time_label()}] {e.title}\n{e.body}".strip())
    return "\n\n".join(out)


def _draft_input(window: list[admin.JournalEntry], tail: str, web_ctx: str) -> str:
    parts = [
        "TODAY'S RECENT ENTRIES (for continuity — do not repeat):",
        _render_window(window),
        "",
        "LIVE ROLLING CONTEXT (what just happened):",
        tail,
    ]
    if web_ctx:
        parts += ["", web_ctx]
    return "\n".join(parts)


def _revise_input(window: list[admin.JournalEntry], new_entry: admin.JournalEntry) -> str:
    return (
        "THE NEW ENTRY (just added — do NOT change it):\n"
        f"[{new_entry.id} · {new_entry.time_label()}] {new_entry.title}\n{new_entry.body}\n\n"
        "EARLIER ENTRIES YOU MAY LIGHTLY TRIM:\n"
        + _render_window(window)
    )


# ── body composition ───────────────────────────────────────────────────────────

def _compose_body(draft: dict) -> str:
    """Compose the visible first-person entry block from a DRAFT dict. The result
    is stored as the entry's opaque body and is what the REVISE pass later edits."""
    parts: list[str] = []
    narr = str(draft.get("narrative") or draft.get("summary") or "").strip()
    if narr:
        parts.append(narr)
    hl = [str(h).strip() for h in (draft.get("highlights") or []) if str(h).strip()]
    if hl:
        parts.append("")
        parts += [f"- {h}" for h in hl[:6]]
    open_t = str(draft.get("open") or "").strip()
    if open_t and open_t.lower() not in ("none", "n/a", "-"):
        parts += ["", f"> **Next:** {open_t}"]
    return "\n".join(parts).strip()


# ── model passes ───────────────────────────────────────────────────────────────

def _draft_entry(window: list[admin.JournalEntry], tail: str, web_ctx: str) -> dict | None:
    """DRAFT the new entry. Structured first; on failure, the legacy third-person
    JOURNAL prompt is the degraded fallback (so a journal is still written)."""
    body = _draft_input(window, tail, web_ctx)
    try:
        raw = call_model(
            _build_messages(prompts.JOURNAL_DRAFT, body, [], []),
            max_tokens=1024, temperature=0.4,
            schema=schemas.JOURNAL_DRAFT, role="journal", priority=PRI_COMPACT,
        )
        parsed = _extract_json(raw.get("text", ""))
    except Exception:
        parsed = None
    if parsed and str(parsed.get("narrative", "")).strip():
        return parsed
    return _legacy_draft(tail)


def _legacy_draft(tail: str) -> dict | None:
    """Degraded path: the old third-person JOURNAL prompt, mapped into a draft dict
    (still produces a coherent entry when constrained decoding is unavailable)."""
    try:
        raw = call_model(
            _build_messages(prompts.JOURNAL, tail, [], []),
            max_tokens=2048, temperature=0.3, role="journal", priority=PRI_COMPACT,
        )
        txt = raw.get("text", "").strip()
    except Exception:
        return None
    if not txt:
        return None
    p = admin.parse_journal_output(txt)
    return {
        "narrative":  p.get("summary", ""),
        "title":      p.get("title", "Session"),
        "highlights": p.get("highlights", []),
        "topics":     p.get("topics", []),
        "open":       p.get("open", ""),
    }


def _revise_window(window: list[admin.JournalEntry], new_entry: admin.JournalEntry) -> list[dict]:
    try:
        raw = call_model(
            _build_messages(prompts.JOURNAL_REVISE, _revise_input(window, new_entry), [], []),
            max_tokens=1024, temperature=0.3,
            schema=schemas.JOURNAL_REVISE, role="journal", priority=PRI_COMPACT,
        )
        parsed = _extract_json(raw.get("text", "")) or {}
    except Exception:
        return []
    revs = parsed.get("revisions")
    return revs if isinstance(revs, list) else []


# ── public entry point ─────────────────────────────────────────────────────────

def run_journal(
    ctx: Any,
    *,
    retrieval: Any = None,
    when: datetime | None = None,
    live_fn: Callable[[str], None] | None = None,
) -> str:
    """Write one autonomous first-person journal entry (DRAFT) and lightly trim the
    trailing window (REVISE). Returns the new entry's title, or "" if nothing was
    written (no context yet, or the model was unavailable). Never raises."""
    when = when or datetime.now(timezone.utc)
    date = admin.journal_day_key(when)

    try:
        tail = ctx.tail_for_model() if ctx is not None else "(no context yet)"
    except Exception:
        tail = "(no context yet)"

    pre = admin.load_journal(date)
    if tail == "(no context yet)" and not pre.entries:
        return ""   # nothing to journal about yet

    window  = pre.entries[-_window_k():]
    web_ctx = _maybe_web_context(window, tail, retrieval)

    draft = _draft_entry(window, tail, web_ctx)
    if not draft:
        return ""   # model down → skip this beat (the time-floor retries next one)

    title  = str(draft.get("title") or "Untitled").strip()[:80] or "Untitled"
    body   = _compose_body(draft)
    if not body:
        return ""
    topics = [str(t) for t in (draft.get("topics") or []) if str(t).strip()][:8]

    # ── persist the new entry (the degraded floor is now satisfied) ──
    with admin._journal_lock:
        j       = admin.load_journal(date)            # fresh read under the lock
        from_ts = j.entries[-1].to_ts if j.entries else admin.journal_day_start(date)
        new_entry = admin.JournalEntry(
            id=admin._next_entry_id(j.entries), from_ts=from_ts or "",
            to_ts=when.isoformat(), rev=0, title=title, body=body,
        )
        j.entries.append(new_entry)
        j.tags = sorted(set(j.tags) | set(topics) | {"daily", "lawrence"})
        admin.save_journal(j, when=when)
    if live_fn:
        live_fn(f"[journal] {new_entry.id}: {title}")

    # ── light trimming-revision of the trailing window (best-effort) ──
    if window and _revise_enabled():
        revs = _revise_window(window, new_entry)
        if revs:
            with admin._journal_lock:
                j = admin.load_journal(date)
                by_id = {e.id: e for e in j.entries}
                changed = 0
                for r in revs:
                    e = by_id.get(str(r.get("id") or ""))
                    nb = str(r.get("body") or "").strip()
                    if e is None or e.id == new_entry.id or not nb or nb == e.body:
                        continue
                    e.body = nb
                    e.rev += 1
                    changed += 1
                if changed:
                    admin.save_journal(j, when=when)
                    if live_fn:
                        live_fn(f"[journal] trimmed {changed} prior entr"
                                f"{'y' if changed == 1 else 'ies'}")

    return title


# ── autonomous trigger (decision 3 — significance-gated + time floor) ──────────

def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _sig_tier() -> int:
    """C2 action-tier a drained event must reach to count as a 'meaningful shift'
    that justifies journalling early (default 2 = STUDY, same scale as the tick)."""
    try:
        return int(os.environ.get("LK_JOURNAL_SIG_TIER", "2"))
    except (TypeError, ValueError):
        return 2


def _event_significant(e: dict[str, Any]) -> bool:
    tier = e.get("tier")
    if isinstance(tier, int):
        return tier >= _sig_tier()
    return float(e.get("significance", 0.0) or 0.0) >= 0.6


class JournalTrigger:
    """Drives the WS-J journal from the cognitive tick: significance-gated, with a
    time floor. Consulted every beat via ``beat(events)`` (the tick's reflect_fn):

      • a **meaningful activity shift** (a drained event clears the C2 tier) writes an
        entry as soon as ``min_interval`` has elapsed since the last one;
      • otherwise a **max_interval floor** guarantees ≥1 entry per period of sustained
        activity (it only fires once there has been activity to journal about).

    Single-flight and non-blocking: an actual journal runs in a daemon thread, so a
    slow model call never stalls the heartbeat, and overlapping beats can't double-write.
    """

    def __init__(
        self,
        ctx: Any,
        *,
        retrieval: Any = None,
        live_fn: Callable[[str], None] | None = None,
        run_fn: Callable[..., str] = run_journal,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ctx       = ctx
        self._retrieval = retrieval
        self._live_fn   = live_fn
        self._run_fn    = run_fn
        self._clock     = clock
        self._last      = clock()
        self._saw_activity = False
        self._busy      = False
        self._lock      = threading.Lock()

    def beat(self, events: list[dict[str, Any]] | None = None) -> None:
        if not enabled():
            return
        events = events or []
        gap = self._clock() - self._last
        shift = False
        if events:
            self._saw_activity = True
            shift = any(_event_significant(e) for e in events)
        due = (shift and gap >= _float_env("LK_JOURNAL_MIN_INTERVAL", 300.0)) or \
              (self._saw_activity and gap >= _float_env("LK_JOURNAL_MAX_INTERVAL", 1800.0))
        if due:
            self.fire()

    def fire(self) -> bool:
        """Start one journal pass in the background (single-flight). Returns True iff
        a pass was actually started (False if one is already running)."""
        with self._lock:
            if self._busy:
                return False
            self._busy = True
        self._last = self._clock()
        self._saw_activity = False

        def _run() -> None:
            try:
                self._run_fn(self._ctx, retrieval=self._retrieval, live_fn=self._live_fn)
            except Exception:
                pass
            finally:
                self._busy = False

        threading.Thread(target=_run, daemon=True, name="journal").start()
        return True
