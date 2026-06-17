"""Durable scheduler — temporal agency (WS-T / NEXT_WORK_CHECKLIST §8).

This replaces the old decorative `localStorage` reminders panel with real
reminders: intents that fire **exactly once**, **survive restarts**, and surface
through the cognitive tick → SSE + desktop notification — with **no model call**
on the firing path (the tick's cheap `due_fn`/`fire_fn` hooks).

Storage is an append-only event log at ``memory/schedule.jsonl``. Each line is one
event (``add`` / ``fired`` / ``done`` / ``remove``); current state is the fold of
the log replayed on load. Append-only + fsync makes the firing record durable
*before* we act on it, so a crash or restart cannot double-fire and cannot lose a
reminder — and the log doubles as an audit trail. This is deliberately model-free:
the scheduler belongs to the system, not the LLM (the model may *propose* a
reminder, but creation is an explicit user/bridge action).

Time is timezone-aware and explicit: a naive ISO datetime is interpreted in the
host's local timezone and stored with an offset; comparisons are done in UTC.
"""
from __future__ import annotations

import json
import os
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT   = Path(__file__).resolve().parents[2]
_SCHED_FILE = REPO_ROOT / "memory" / "schedule.jsonl"

# Resolved once: the host's local timezone, used to make naive datetimes explicit.
_LOCAL_TZ = datetime.now(timezone.utc).astimezone().tzinfo


class ScheduleError(ValueError):
    """Invalid reminder input (e.g. an unparseable time)."""


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now_dt().isoformat()


def parse_when(when: str | datetime) -> datetime:
    """Parse a reminder time into a timezone-aware datetime.

    Accepts an ISO-8601 string (``2026-06-18T09:00`` or with an offset) or a
    relative offset ``+<n>[smhd]`` (e.g. ``+30m``, ``+2h``, ``+1d``). A naive
    datetime is interpreted in the host's local timezone (explicit, not silent
    UTC). Raises :class:`ScheduleError` on anything unparseable."""
    if isinstance(when, datetime):
        dt = when
    else:
        s = str(when).strip()
        if not s:
            raise ScheduleError("a reminder time is required")
        m = re.fullmatch(r"\+\s*(\d+)\s*([smhd])", s, re.IGNORECASE)
        if m:
            secs = int(m.group(1)) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[m.group(2).lower()]
            return _now_dt() + timedelta(seconds=secs)
        try:
            dt = datetime.fromisoformat(s)
        except ValueError as exc:
            raise ScheduleError(
                f"could not parse time {when!r}; use ISO-8601 (2026-06-18T09:00) "
                f"or a relative offset (+30m, +2h, +1d)"
            ) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_LOCAL_TZ)   # explicit: a bare datetime is local
    return dt


class Schedule:
    """Thread-safe, restart-safe, model-free reminder store."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _SCHED_FILE
        self._lock = threading.RLock()
        self._items: dict[str, dict[str, Any]] = {}   # id → current record (folded)
        self._load()

    # ── persistence (append-only event log) ─────────────────────────────────────
    def _load(self) -> None:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return
        except OSError:
            return
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                self._apply(json.loads(line))
            except Exception:
                continue   # tolerate a torn/garbage line; replay the rest

    def _apply(self, ev: dict[str, Any]) -> None:
        op  = ev.get("op")
        rid = ev.get("id")
        if not rid:
            return
        if op == "add":
            self._items[rid] = {
                "id":      rid,
                "text":    ev.get("text", ""),
                "due":     ev.get("due", ""),
                "status":  "pending",
                "created": ev.get("created", ev.get("at", "")),
                "source":  ev.get("source", "user"),
            }
        elif op == "fired":
            rec = self._items.get(rid)
            if rec is not None:
                rec["status"]   = "fired"
                rec["fired_at"] = ev.get("at", "")
        elif op == "done":
            rec = self._items.get(rid)
            if rec is not None:
                rec["status"] = "done"
        elif op == "remove":
            self._items.pop(rid, None)

    def _append(self, ev: dict[str, Any]) -> None:
        """Append one event durably (fsync) so the firing/creation record survives
        a crash before we act on it."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

    # ── mutations ───────────────────────────────────────────────────────────────
    def add(self, text: str, when: str | datetime, *, source: str = "user") -> dict[str, Any]:
        """Create a one-shot reminder. Raises ScheduleError on bad input."""
        text = (text or "").strip()
        if not text:
            raise ScheduleError("reminder text is required")
        due = parse_when(when)   # may raise ScheduleError
        rid = f"rem-{uuid.uuid4().hex[:10]}"
        ev = {"op": "add", "id": rid, "text": text, "due": due.isoformat(),
              "created": _now_iso(), "source": source}
        with self._lock:
            self._append(ev)
            self._apply(ev)
            return dict(self._items[rid])

    def mark_fired(self, rid: str, *, at: str | None = None) -> dict[str, Any] | None:
        """Mark a reminder fired — durably, before the caller notifies. Idempotent:
        firing an already-terminal reminder is a no-op (the guard against
        double-fire across restarts and across concurrent beats)."""
        with self._lock:
            rec = self._items.get(rid)
            if rec is None or rec.get("status") != "pending":
                return None
            ev = {"op": "fired", "id": rid, "at": at or _now_iso()}
            self._append(ev)
            self._apply(ev)
            return dict(self._items[rid])

    def done(self, rid: str) -> bool:
        """Dismiss/complete a reminder before it fires (won't fire afterwards)."""
        with self._lock:
            rec = self._items.get(rid)
            if rec is None or rec.get("status") != "pending":
                return False
            ev = {"op": "done", "id": rid, "at": _now_iso()}
            self._append(ev)
            self._apply(ev)
            return True

    def remove(self, rid: str) -> bool:
        with self._lock:
            if rid not in self._items:
                return False
            ev = {"op": "remove", "id": rid, "at": _now_iso()}
            self._append(ev)
            self._apply(ev)
            return True

    # ── reads ─────────────────────────────────────────────────────────────────
    def due(self, now: datetime | None = None) -> list[dict[str, Any]]:
        """Pending reminders whose time has arrived — the tick's cheap `due_fn`.
        Pure read (no mutation); the tick's `fire_fn` marks them fired."""
        cutoff = (now or _now_dt()).timestamp()
        out: list[dict[str, Any]] = []
        with self._lock:
            for rec in self._items.values():
                if rec.get("status") != "pending":
                    continue
                try:
                    due_ts = datetime.fromisoformat(rec["due"]).timestamp()
                except (ValueError, KeyError):
                    continue
                if due_ts <= cutoff:
                    out.append(dict(rec))
        out.sort(key=lambda r: r.get("due", ""))
        return out

    def list(self, *, include_terminal: bool = True) -> list[dict[str, Any]]:
        with self._lock:
            items = [dict(r) for r in self._items.values()
                     if include_terminal or r.get("status") == "pending"]
        items.sort(key=lambda r: r.get("due", ""))
        return items

    def counts(self) -> dict[str, int]:
        with self._lock:
            pending = sum(1 for r in self._items.values() if r.get("status") == "pending")
            fired   = sum(1 for r in self._items.values() if r.get("status") == "fired")
            done    = sum(1 for r in self._items.values() if r.get("status") == "done")
        return {"pending": pending, "fired": fired, "done": done, "total": len(self._items)}

    def snapshot(self) -> dict[str, Any]:
        """List + counts for the bridge/UI (the badge count comes from here)."""
        return {"reminders": self.list(), "counts": self.counts()}
