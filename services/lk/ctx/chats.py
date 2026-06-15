"""Chat/session store — first-class, addressable conversations (WS-U Track 1).

A chat is a persistent, named conversation with its own durable transcript and
its own short-term working memory, while the agent's long-term mind (journal,
notes, the deep L3 tier) stays shared across every chat. This formalises today's
ad-hoc per-day rolling/log streams into switchable, manageable entities so the UI
can offer new / switch / rename / delete / backup / restore — and so individual
messages become addressable nodes the cross-chat graph (Track 2) can link.

Layout under ``memory/chats/``::

  index.json              the registry: [{id, title, created, updated,
                          messages, archived}], most-recent-updated first.
  active                  one line: the id of the active chat (survives restart).
  <id>/
    messages.jsonl        durable transcript — {seq, id, role, text, ts, meta};
                          message id == "<chatId>:<seq>" (stable, addressable).
    rolling-l1.jsonl      per-chat conversation working memory (the hybrid model:
    rolling-l2.jsonl      short-term is per-chat, long-term L3 is shared — Track 1b).

Stdlib-only, model-free, thread-safe. The single-writer invariant (I1) still
holds: exactly one kernel process owns ``memory/``. Atomic writes (temp +
os.replace) keep a lock-free reader from ever seeing a half-written registry.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
_MEM_DIR  = REPO_ROOT / "memory"

_DEFAULT_TITLE = "Scratch"


def _slug(text: str, n: int = 48) -> str:
    s = re.sub(r"\s+", " ", (text or "").strip())
    return s[:n].rstrip() or "Untitled"


class ChatStore:
    """Registry + durable transcripts for switchable chats. Append-only messages;
    mutable per-chat metadata (title/updated/count) via atomic registry rewrites."""

    def __init__(self, mem_dir: Path = _MEM_DIR) -> None:
        self._root   = mem_dir / "chats"
        self._index  = self._root / "index.json"
        self._active = self._root / "active"
        self._lock   = threading.Lock()
        self._root.mkdir(parents=True, exist_ok=True)

    # ── registry I/O ────────────────────────────────────────────────────────────

    def _read_index(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self._index.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _write_index(self, rows: list[dict[str, Any]]) -> None:
        tmp = self._index.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, self._index)

    @staticmethod
    def _sort(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(rows, key=lambda r: str(r.get("updated", "")), reverse=True)

    def chat_dir(self, chat_id: str) -> Path:
        return self._root / chat_id

    def _messages_path(self, chat_id: str) -> Path:
        return self.chat_dir(chat_id) / "messages.jsonl"

    def _new_id(self, existing: set[str]) -> str:
        base = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        nid, k = base, 2
        while nid in existing:
            nid = f"{base}-{k}"
            k += 1
        return nid

    # ── CRUD ────────────────────────────────────────────────────────────────────

    def list_chats(self, *, include_archived: bool = False) -> list[dict[str, Any]]:
        rows = self._read_index()
        if not include_archived:
            rows = [r for r in rows if not r.get("archived")]
        return self._sort(rows)

    def chat_meta(self, chat_id: str) -> dict[str, Any] | None:
        return next((r for r in self._read_index() if r.get("id") == chat_id), None)

    def create_chat(self, title: str = "") -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            rows = self._read_index()
            nid  = self._new_id({r.get("id") for r in rows})
            meta = {
                "id": nid, "title": _slug(title) if title else "",
                "created": now, "updated": now, "messages": 0, "archived": False,
            }
            self.chat_dir(nid).mkdir(parents=True, exist_ok=True)
            rows.append(meta)
            self._write_index(rows)
        return meta

    def rename_chat(self, chat_id: str, title: str) -> bool:
        with self._lock:
            rows = self._read_index()
            row  = next((r for r in rows if r.get("id") == chat_id), None)
            if row is None:
                return False
            row["title"]   = _slug(title)
            row["updated"] = datetime.now(timezone.utc).isoformat()
            self._write_index(rows)
        return True

    def delete_chat(self, chat_id: str, *, hard: bool = False) -> bool:
        """Archive (default) or hard-delete a chat. Hard delete removes its dir."""
        with self._lock:
            rows = self._read_index()
            row  = next((r for r in rows if r.get("id") == chat_id), None)
            if row is None:
                return False
            if hard:
                rows = [r for r in rows if r.get("id") != chat_id]
                shutil.rmtree(self.chat_dir(chat_id), ignore_errors=True)
            else:
                row["archived"] = True
                row["updated"]  = datetime.now(timezone.utc).isoformat()
            self._write_index(rows)
            # If the active chat was just removed, clear the pointer.
            if self.active_chat() == chat_id:
                try:
                    self._active.unlink()
                except OSError:
                    pass
        return True

    # ── transcript ──────────────────────────────────────────────────────────────

    def append_message(
        self, chat_id: str, role: str, text: str, *, meta: dict[str, Any] | None = None
    ) -> str:
        """Append one durable message. Returns its stable id ``<chatId>:<seq>``.
        Auto-titles the chat from the first user message. Append-only."""
        text = text or ""
        ts   = datetime.now(timezone.utc).isoformat()
        with self._lock:
            rows = self._read_index()
            row  = next((r for r in rows if r.get("id") == chat_id), None)
            if row is None:                       # tolerate a vanished chat (degraded)
                row = {"id": chat_id, "title": "", "created": ts,
                       "updated": ts, "messages": 0, "archived": False}
                rows.append(row)
            self.chat_dir(chat_id).mkdir(parents=True, exist_ok=True)
            path = self._messages_path(chat_id)
            seq  = sum(1 for _ in self._iter_lines(path)) + 1
            mid  = f"{chat_id}:{seq}"
            record = {"seq": seq, "id": mid, "role": role, "text": text, "ts": ts}
            if meta:
                record["meta"] = meta
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            row["messages"] = seq
            row["updated"]  = ts
            if not row.get("title") and role == "user" and text.strip():
                row["title"] = _slug(text)
            self._write_index(rows)
        return mid

    @staticmethod
    def _iter_lines(path: Path) -> list[str]:
        try:
            return [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        except FileNotFoundError:
            return []

    def messages(self, chat_id: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for l in self._iter_lines(self._messages_path(chat_id)):
            try:
                out.append(json.loads(l))
            except json.JSONDecodeError:
                pass
        return out

    def get_message(self, chat_id: str, seq: int | str) -> dict[str, Any] | None:
        try:
            seq = int(seq)
        except (TypeError, ValueError):
            return None
        return next((m for m in self.messages(chat_id) if m.get("seq") == seq), None)

    def get_chat(self, chat_id: str) -> dict[str, Any] | None:
        meta = self.chat_meta(chat_id)
        if meta is None:
            return None
        return {**meta, "messages_list": self.messages(chat_id)}

    def export_chat(self, chat_id: str) -> str:
        """Render the full transcript as browseable MDX (for backup/export)."""
        meta = self.chat_meta(chat_id)
        if meta is None:
            return ""
        title = meta.get("title") or f"Chat {chat_id}"
        out: list[str] = [
            "---", f"id: {chat_id}", f'title: "{title}"',
            f"created: {meta.get('created','')}", f"exported: {datetime.now(timezone.utc).isoformat()}",
            f"messages: {meta.get('messages', 0)}", "---", "", f"# {title}",
        ]
        for m in self.messages(chat_id):
            ts = str(m.get("ts") or "")
            stamp = ts[11:16] if len(ts) >= 16 else ""
            who = "You" if m.get("role") == "user" else "LAWRENCE"
            out.append("")
            out.append(f"## {who} {stamp}".rstrip())
            out.append("")
            out.append(str(m.get("text") or ""))
        return "\n".join(out) + "\n"

    # ── active pointer ──────────────────────────────────────────────────────────

    def active_chat(self) -> str | None:
        try:
            cid = self._active.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return cid or None

    def set_active(self, chat_id: str) -> bool:
        if self.chat_meta(chat_id) is None:
            return False
        tmp = self._active.with_suffix(".tmp")
        tmp.write_text(chat_id + "\n", encoding="utf-8")
        os.replace(tmp, self._active)
        return True

    def ensure_default(self) -> str:
        """Return a valid active chat id, creating a default 'scratch' chat if the
        workspace is empty. The degraded path: with no chat ever selected, the
        system still behaves as today's single conversation stream."""
        cid = self.active_chat()
        if cid and self.chat_meta(cid) and not self.chat_meta(cid).get("archived"):
            return cid
        live = self.list_chats()
        if live:
            self.set_active(live[0]["id"])
            return live[0]["id"]
        meta = self.create_chat(_DEFAULT_TITLE)
        self.set_active(meta["id"])
        return meta["id"]

    # ── stats (memops) ──────────────────────────────────────────────────────────

    def stats(self) -> dict[str, int]:
        rows = self._read_index()
        nbytes = 0
        for p in self._root.rglob("*"):
            if p.is_file():
                try:
                    nbytes += p.stat().st_size
                except OSError:
                    pass
        return {
            "chats": len(rows),
            "messages": sum(int(r.get("messages", 0) or 0) for r in rows),
            "bytes": nbytes,
        }
