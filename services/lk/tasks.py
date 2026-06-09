"""Self-managed task list + remember points.

LAWRENCE maintains a lightweight TODO/task list and a "points to remember" list
that the *model* curates on its own — it proposes additions and completions from
the flow of conversation and passive context, without the user having to ask.

Storage is a single JSON document at ``memory/tasks.json`` (atomic rewrite), so
both the CLI and the desktop bridge see the same state. The store is thread-safe
so the observer/proactive threads and the turn thread can all touch it.

Schema::

    {
      "tasks":    [{"id","text","status","created","updated","source"}],
      "remember": [{"id","text","created","source"}],
      "updated":  "<iso8601>"
    }

``status`` is ``"open"`` or ``"done"``. ``source`` is ``"model"`` (self-curated)
or ``"user"`` (explicit). The model emits proposals in its RESPONSE JSON; the
kernel routes them here via :meth:`TaskStore.apply_model`.
"""
from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
_TASKS_FILE = REPO_ROOT / "memory" / "tasks.json"

_MAX_TASKS = 250
_MAX_REMEMBER = 250


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(text: str) -> str:
    """Normalised key for dedup — lowercase, punctuation-light, collapsed space."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", text.lower())).strip()


class TaskStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _TASKS_FILE
        self._lock = threading.RLock()
        self._tasks: list[dict[str, Any]] = []
        self._remember: list[dict[str, Any]] = []
        self._load()

    # ── persistence ───────────────────────────────────────────────────────────
    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._tasks = list(data.get("tasks", []))
            self._remember = list(data.get("remember", []))
        except Exception:
            self._tasks = []
            self._remember = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "tasks": self._tasks[-_MAX_TASKS:],
            "remember": self._remember[-_MAX_REMEMBER:],
            "updated": _now(),
        }
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    # ── reads ───────────────────────────────────────────────────────────────────
    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            open_n = sum(1 for t in self._tasks if t.get("status") == "open")
            done_n = sum(1 for t in self._tasks if t.get("status") == "done")
            return {
                "tasks": [dict(t) for t in self._tasks],
                "remember": [dict(r) for r in self._remember],
                "counts": {
                    "open": open_n,
                    "done": done_n,
                    "remember": len(self._remember),
                },
            }

    # ── task mutations ──────────────────────────────────────────────────────────
    def add_task(self, text: str, source: str = "user") -> dict[str, Any] | None:
        text = (text or "").strip()
        if not text:
            return None
        key = _norm(text)
        with self._lock:
            for t in self._tasks:
                if t.get("status") == "open" and _norm(t.get("text", "")) == key:
                    return t  # already tracked — do not duplicate
            task = {
                "id": f"tk-{uuid.uuid4().hex[:10]}",
                "text": text,
                "status": "open",
                "created": _now(),
                "updated": _now(),
                "source": source,
            }
            self._tasks.append(task)
            self._save()
            return task

    def _find_open_by_text(self, text: str) -> dict[str, Any] | None:
        key = _norm(text)
        for t in self._tasks:
            if t.get("status") == "open" and _norm(t.get("text", "")) == key:
                return t
        return None

    def complete_task(self, task_id: str = "", *, text: str = "", source: str = "user") -> dict[str, Any] | None:
        with self._lock:
            target = None
            if task_id:
                target = next((t for t in self._tasks if t.get("id") == task_id), None)
            elif text:
                target = self._find_open_by_text(text)
            if target is None and text:
                # Model reported finishing something it never logged — record it done.
                target = {
                    "id": f"tk-{uuid.uuid4().hex[:10]}",
                    "text": text.strip(),
                    "status": "open",
                    "created": _now(),
                    "source": source,
                }
                self._tasks.append(target)
            if target is None:
                return None
            target["status"] = "done"
            target["updated"] = _now()
            self._save()
            return target

    def reopen_task(self, task_id: str) -> bool:
        with self._lock:
            for t in self._tasks:
                if t.get("id") == task_id:
                    t["status"] = "open"
                    t["updated"] = _now()
                    self._save()
                    return True
        return False

    def remove_task(self, task_id: str) -> bool:
        with self._lock:
            n = len(self._tasks)
            self._tasks = [t for t in self._tasks if t.get("id") != task_id]
            if len(self._tasks) != n:
                self._save()
                return True
        return False

    # ── remember mutations ──────────────────────────────────────────────────────
    def add_remember(self, text: str, source: str = "model") -> dict[str, Any] | None:
        text = (text or "").strip()
        if not text:
            return None
        key = _norm(text)
        with self._lock:
            for r in self._remember:
                if _norm(r.get("text", "")) == key:
                    return r
            item = {
                "id": f"rm-{uuid.uuid4().hex[:10]}",
                "text": text,
                "created": _now(),
                "source": source,
            }
            self._remember.append(item)
            self._save()
            return item

    def remove_remember(self, item_id: str) -> bool:
        with self._lock:
            n = len(self._remember)
            self._remember = [r for r in self._remember if r.get("id") != item_id]
            if len(self._remember) != n:
                self._save()
                return True
        return False

    def clear(self, scope: str = "all") -> None:
        with self._lock:
            if scope in ("all", "tasks"):
                self._tasks = []
            if scope in ("all", "remember"):
                self._remember = []
            if scope == "done":
                self._tasks = [t for t in self._tasks if t.get("status") != "done"]
            self._save()

    # ── model-driven batch (self-curation) ──────────────────────────────────────
    def apply_model(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        """Apply a model's self-determined task/remember proposals.

        Accepted shapes (all optional, omitted = no change):
          payload["tasks"]:    [ "text" | {"op":"add|done|complete|remove","text"|"id"} ]
          payload["remember"]: [ "text" | {"text": "..."} ]

        Returns a small summary of what changed (for live/SSE notification).
        """
        added: list[str] = []
        done: list[str] = []
        remembered: list[str] = []
        if not isinstance(payload, dict):
            return {"added": added, "done": done, "remembered": remembered}

        for entry in payload.get("tasks") or []:
            op, text, tid = "add", "", ""
            if isinstance(entry, str):
                text = entry
            elif isinstance(entry, dict):
                op = str(entry.get("op", "add")).lower()
                text = str(entry.get("text", ""))
                tid = str(entry.get("id", ""))
            if op in ("done", "complete", "completed", "close"):
                t = self.complete_task(tid, text=text, source="model")
                if t:
                    done.append(t["text"])
            elif op in ("remove", "delete", "drop"):
                if tid:
                    self.remove_task(tid)
            else:  # add
                t = self.add_task(text, source="model")
                if t and t["text"] not in added:
                    added.append(t["text"])

        for entry in payload.get("remember") or []:
            text = entry if isinstance(entry, str) else str((entry or {}).get("text", ""))
            r = self.add_remember(text, source="model")
            if r and r["text"] not in remembered:
                remembered.append(r["text"])

        return {"added": added, "done": done, "remembered": remembered}
