"""Confirmed allowlisted effectors for LAWRENCE."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .policy import PolicyState, audit


REPO_ROOT = Path(__file__).resolve().parents[2]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Agency:
    def __init__(self, tasks: Any, schedule: Any, *,
                 log_path: Path | None = None, artifact_dir: Path | None = None) -> None:
        self.tasks = tasks
        self.schedule = schedule
        self.log_path = log_path or REPO_ROOT / "memory" / "actions.jsonl"
        self.artifact_dir = artifact_dir or REPO_ROOT / "memory" / "artifacts"
        self._items: dict[str, dict[str, Any]] = {}
        self._tokens: dict[str, str] = {}
        self._lock = threading.Lock()

    def propose(self, proposals: list[dict[str, Any]], context_version: int) -> list[dict[str, Any]]:
        accepted = []
        for raw in proposals[:3]:
            operation = str(raw.get("operation") or "").strip()
            if operation not in {"task.add", "reminder.add", "artifact.write"}:
                continue
            args = {key: str(raw.get(key) or "").strip()
                    for key in ("text", "when", "name", "content") if raw.get(key)}
            token = secrets.token_urlsafe(18)
            action_id = f"act-{uuid.uuid4().hex[:10]}"
            item = {
                "id": action_id,
                "operation": operation,
                "args": args,
                "risk": "reversible-local",
                "contextVersion": int(context_version),
                "status": "pending",
                "createdAt": _now(),
                "tokenSha256": hashlib.sha256(token.encode()).hexdigest(),
            }
            with self._lock:
                self._items[action_id] = item
                self._tokens[action_id] = token
                self._append({"event": "proposed", **item})
            accepted.append({**self._public(item), "confirmationToken": token})
        return accepted

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            items = [self._public(item) for item in self._items.values()]
        return {"items": sorted(items, key=lambda item: item["createdAt"], reverse=True)}

    def decide(self, action_id: str, *, confirm: bool, token: str = "") -> dict[str, Any]:
        with self._lock:
            item = self._items.get(action_id)
            if item is None:
                raise ValueError("unknown action proposal")
            if item["status"] != "pending":
                raise ValueError("action proposal is no longer pending")
            if not confirm:
                item["status"] = "rejected"
                item["finishedAt"] = _now()
                self._append({"event": "rejected", **item})
                self._tokens.pop(action_id, None)
                return self._public(item)
            expected = self._tokens.get(action_id, "")
            if not expected or not secrets.compare_digest(expected, token):
                decision = PolicyState.current().allow("external_action")
                audit("external_action", decision, item["operation"])
                raise ValueError("valid one-use confirmation token required")
            decision = PolicyState.current().allow("external_action", explicit=True)
            audit("external_action", decision, json.dumps(
                {"operation": item["operation"], "args": item["args"]}, sort_keys=True))
            if not decision.allowed:
                raise ValueError(decision.reason)
            result = self._execute(item["operation"], item["args"])
            item.update(status="done", result=result, finishedAt=_now())
            self._append({"event": "executed", **item})
            self._tokens.pop(action_id, None)
            return self._public(item)

    def _execute(self, operation: str, args: dict[str, str]) -> dict[str, Any]:
        if operation == "task.add":
            task = self.tasks.add_task(args.get("text", ""), source="agent")
            if not task:
                raise ValueError("task text is required")
            return {"taskId": task["id"]}
        if operation == "reminder.add":
            reminder = self.schedule.add(
                args.get("text", ""), args.get("when", ""), source="agent")
            return {"reminderId": reminder["id"]}
        name = Path(args.get("name") or "lawrence-artifact.md").name
        if not name.lower().endswith(".md"):
            name += ".md"
        content = args.get("content", "")[:20_000]
        if not content:
            raise ValueError("artifact content is required")
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        path = self.artifact_dir / name
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)
        return {"path": str(path)}

    def _append(self, event: dict[str, Any]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _public(item: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in item.items() if key != "tokenSha256"}
