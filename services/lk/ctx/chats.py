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
    messages.jsonl        durable, append-only EVENT LOG — {seq, id, role, text, ts,
                          parent, kind, [edit_of], [diff], [meta]}; message id ==
                          "<chatId>:<seq>" (stable, addressable). Regenerations and
                          edits are appended as SIBLINGS sharing a parent (a DAG over
                          the log) — the log is never mutated (preserves I1 + durability).
    head.json             the selected PATH through the DAG: {parent_id -> child_id}
                          ("" key == the root slot). Walking head from the root yields
                          the "current conversation"; switching a variant rewrites one
                          entry. Absent/legacy ⇒ linear walk by seq (back-compatible).
    rolling-l1.jsonl      per-chat conversation working memory (the hybrid model:
    rolling-l2.jsonl      short-term is per-chat, long-term L3 is shared — Track 1b).

Stdlib-only, model-free, thread-safe. The single-writer invariant (I1) still
holds: exactly one kernel process owns ``memory/``. Atomic writes (temp +
os.replace) keep a lock-free reader from ever seeing a half-written registry.
"""
from __future__ import annotations

import difflib
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

# Sentinel for append_message(parent=...): default ⇒ auto-chain to the active leaf;
# an explicit ``None`` means "this is a root", an explicit id means "this parent".
_AUTO = object()


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

    # ── DAG: head/path cursor (the selected walk through variants) ─────────────────

    def _head_path(self, chat_id: str) -> Path:
        return self.chat_dir(chat_id) / "head.json"

    def _read_head(self, chat_id: str) -> dict[str, str]:
        try:
            data = json.loads(self._head_path(chat_id).read_text(encoding="utf-8"))
            return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_head(self, chat_id: str, head: dict[str, str]) -> None:
        self.chat_dir(chat_id).mkdir(parents=True, exist_ok=True)
        p   = self._head_path(chat_id)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(head, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, p)

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

    def restore_chat(self, chat_id: str) -> bool:
        """Make one archived chat available again."""
        with self._lock:
            rows = self._read_index()
            row = next((r for r in rows if r.get("id") == chat_id), None)
            if row is None:
                return False
            row["archived"] = False
            row["updated"] = datetime.now(timezone.utc).isoformat()
            self._write_index(rows)
        return True

    # ── transcript ──────────────────────────────────────────────────────────────

    def append_message(
        self, chat_id: str, role: str, text: str, *,
        meta: dict[str, Any] | None = None,
        parent: Any = _AUTO, kind: str = "turn",
        edit_of: str | None = None, diff: str | None = None,
    ) -> str:
        """Append one durable message to the event log. Returns its stable id
        ``<chatId>:<seq>``. Append-only — never mutates a prior record.

        ``parent`` defaults to ``_AUTO`` ⇒ chain to the current active leaf (so legacy
        two-call turns keep producing a clean linear backbone). An explicit ``None``
        marks a root; an explicit id places this message as a child/sibling of it
        (the regenerate/edit/branch paths use this to fork the DAG). The new node is
        made the active variant for its parent (``head``)."""
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
            if parent is _AUTO:                    # auto-chain to the current active leaf
                leaf   = self._path_records(chat_id)
                parent = leaf[-1]["id"] if leaf else None
            record: dict[str, Any] = {
                "seq": seq, "id": mid, "role": role, "text": text, "ts": ts,
                "parent": parent, "kind": kind,
            }
            if edit_of:
                record["edit_of"] = edit_of
            if diff:
                record["diff"] = diff
            if meta:
                record["meta"] = meta
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            # make the new node the active variant on its parent's slot
            head = self._read_head(chat_id)
            head["" if parent is None else str(parent)] = mid
            self._write_head(chat_id, head)
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

    def get_by_id(self, chat_id: str, message_id: str) -> dict[str, Any] | None:
        return next((m for m in self.messages(chat_id) if m.get("id") == message_id), None)

    def get_chat(self, chat_id: str) -> dict[str, Any] | None:
        meta = self.chat_meta(chat_id)
        if meta is None:
            return None
        # The UI renders the selected PATH (not the full log); the minimap reads ``tree``.
        return {**meta, "messages_list": self.path_messages(chat_id),
                "tree": self.tree(chat_id)}

    # ── DAG traversal (path walk + tree) ──────────────────────────────────────────

    @staticmethod
    def _resolve_parent(rec: dict[str, Any], seq_to_id: dict[int, str]) -> str | None:
        """Parent of a record: explicit ``parent`` if present, else the legacy linear
        backbone (the seq-1 record) so pre-DAG transcripts still walk correctly."""
        if "parent" in rec:
            return rec.get("parent")
        return seq_to_id.get(int(rec.get("seq", 0)) - 1)

    def _path_records(self, chat_id: str) -> list[dict[str, Any]]:
        """Walk ``head`` from the root → the active conversation path. Lock-free read;
        safe to call while holding ``self._lock`` (used by append for auto-parent)."""
        recs = self.messages(chat_id)
        if not recs:
            return []
        seq_to_id = {int(r.get("seq", 0)): r.get("id") for r in recs}
        children: dict[str | None, list[dict[str, Any]]] = {}
        for r in recs:
            children.setdefault(self._resolve_parent(r, seq_to_id), []).append(r)
        for kids in children.values():
            kids.sort(key=lambda r: int(r.get("seq", 0)))
        head = self._read_head(chat_id)

        def pick(parent_id: str | None) -> dict[str, Any] | None:
            kids = children.get(parent_id, [])
            if not kids:
                return None
            chosen = head.get("" if parent_id is None else str(parent_id))
            for k in kids:
                if k.get("id") == chosen:
                    return k
            return kids[-1]                       # default: the latest variant

        path: list[dict[str, Any]] = []
        seen: set[str] = set()
        cur = pick(None)
        while cur and cur.get("id") not in seen:
            seen.add(cur["id"])
            path.append(cur)
            cur = pick(cur.get("id"))
        return path

    def path_messages(self, chat_id: str) -> list[dict[str, Any]]:
        """The active conversation path (what the UI renders)."""
        return self._path_records(chat_id)

    def parent_of(self, chat_id: str, message_id: str) -> str | None:
        recs = self.messages(chat_id)
        seq_to_id = {int(r.get("seq", 0)): r.get("id") for r in recs}
        rec = next((r for r in recs if r.get("id") == message_id), None)
        return self._resolve_parent(rec, seq_to_id) if rec else None

    def tree(self, chat_id: str) -> dict[str, Any]:
        """Compact node/edge view for the minimap: every variant, the active path,
        and the head selections."""
        recs = self.messages(chat_id)
        seq_to_id = {int(r.get("seq", 0)): r.get("id") for r in recs}
        nodes = [{
            "id": r.get("id"), "seq": r.get("seq"), "role": r.get("role"),
            "kind": r.get("kind", "turn"), "parent": self._resolve_parent(r, seq_to_id),
            "ts": r.get("ts", ""), "edit_of": r.get("edit_of"),
            "snippet": (r.get("text") or "")[:80],
        } for r in recs]
        return {
            "id": chat_id, "nodes": nodes,
            "head": self._read_head(chat_id),
            "path": [r.get("id") for r in self._path_records(chat_id)],
        }

    # ── DAG ops (regenerate / edit / variant-switch / branch) ─────────────────────

    def add_variant(self, chat_id: str, message_id: str, role: str, text: str,
                    *, kind: str = "regen", meta: dict[str, Any] | None = None) -> str | None:
        """Append a sibling of ``message_id`` (same parent) — the storage half of a
        regeneration. The new node becomes the active variant. Text comes from the
        caller (the model turn happens in the bridge). Returns the new id, or None."""
        if self.get_by_id(chat_id, message_id) is None:
            return None
        parent = self.parent_of(chat_id, message_id)
        return self.append_message(chat_id, role, text, parent=parent, kind=kind, meta=meta)

    def edit_message(self, chat_id: str, message_id: str, new_text: str) -> dict[str, Any] | None:
        """Capture an edited version as a sibling (kind ``edit``) carrying a unified
        diff vs the prior text. Pure storage — never mutates the original line."""
        orig = self.get_by_id(chat_id, message_id)
        if orig is None:
            return None
        old_text = orig.get("text") or ""
        new_text = new_text or ""
        diff = "".join(difflib.unified_diff(
            old_text.splitlines(keepends=True), new_text.splitlines(keepends=True),
            fromfile=f"{message_id} (before)", tofile=f"{message_id} (after)",
        ))
        parent = self.parent_of(chat_id, message_id)
        new_id = self.append_message(
            chat_id, str(orig.get("role") or "assistant"), new_text,
            parent=parent, kind="edit", edit_of=message_id, diff=diff)
        return {"id": new_id, "diff": diff, "edit_of": message_id}

    def set_head(self, chat_id: str, parent_id: str | None, child_id: str) -> bool:
        """Select which variant sits on the active path under ``parent_id`` (variant
        switch — no model call)."""
        with self._lock:
            ids = {m.get("id") for m in self.messages(chat_id)}
            if child_id not in ids:
                return False
            head = self._read_head(chat_id)
            head["" if parent_id is None else str(parent_id)] = child_id
            self._write_head(chat_id, head)
        return True

    def fork_chat(self, chat_id: str, at_message_id: str, title: str = "") -> dict[str, Any] | None:
        """Branch-off (kind-2): create a new chat seeded with the active-path prefix up
        to and including ``at_message_id`` (copied as ``branch-seed`` messages)."""
        path = self._path_records(chat_id)
        prefix: list[dict[str, Any]] = []
        for r in path:
            prefix.append(r)
            if r.get("id") == at_message_id:
                break
        else:
            return None                            # not on the active path
        src = self.chat_meta(chat_id) or {}
        new = self.create_chat(title or f"{src.get('title') or chat_id} (branch)")
        nid, prev = new["id"], None
        for r in prefix:
            prev = self.append_message(
                nid, str(r.get("role") or "user"), r.get("text") or "",
                parent=prev, kind="branch-seed")
        return new

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
        for m in self.path_messages(chat_id):
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
