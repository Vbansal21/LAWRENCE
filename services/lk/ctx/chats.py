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
from datetime import datetime, timedelta, timezone
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


def _hit_snippet(text: str, query: str, *, regex: bool = False, pad: int = 40) -> str:
    """A short context window around the first match (for search-result previews)."""
    body = re.sub(r"\s+", " ", text or "")
    idx, mlen = -1, len(query)
    if regex:
        try:
            m = re.search(query, body, re.IGNORECASE)
            if m:
                idx, mlen = m.start(), max(1, m.end() - m.start())
        except re.error:
            idx = -1
    else:
        idx = body.lower().find(query.lower())
    if idx < 0:
        return body[:90].rstrip()
    start = max(0, idx - pad)
    end = min(len(body), idx + mlen + pad)
    return ("…" if start else "") + body[start:end].strip() + ("…" if end < len(body) else "")


def _node_summary(text: str, n: int = 72) -> str:
    """Short, single-line node label for the graph minimap: first meaningful line
    (skip MDX heading marks / list bullets), whitespace-collapsed, length-capped."""
    for raw in (text or "").splitlines():
        line = re.sub(r"\s+", " ", raw.strip())
        line = re.sub(r"^#{1,6}\s*", "", line)          # drop heading hashes
        line = re.sub(r"^[-*>]\s+", "", line)           # drop list/quote markers
        if line:
            return line[:n].rstrip() + ("…" if len(line) > n else "")
    return "(empty)"


class ChatStore:
    """Registry + durable transcripts for switchable chats. Append-only messages;
    mutable per-chat metadata (title/updated/count) via atomic registry rewrites."""

    def __init__(self, mem_dir: Path = _MEM_DIR) -> None:
        self._root   = mem_dir / "chats"
        self._index  = self._root / "index.json"
        self._active = self._root / "active"
        self._bookmarks = self._root / "bookmarks.json"   # N-81 B8: message-level pins
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
    def _sort(rows: list[dict[str, Any]], *, sort: str = "recency") -> list[dict[str, Any]]:
        # N-81 B8: pinned/favorite chats always float to the top. N-81 B9c: the secondary
        # key is selectable — recency (updated, default) | created | title | messages.
        # title sorts A→Z (ascending); the rest newest/largest-first (descending).
        if sort == "title":
            return sorted(rows, key=lambda r: (not bool(r.get("pinned")),
                                               str(r.get("title") or r.get("id") or "").lower()))
        if sort == "created":
            key = lambda r: (bool(r.get("pinned")), str(r.get("created", "")))
        elif sort == "messages":
            key = lambda r: (bool(r.get("pinned")), int(r.get("messages", 0) or 0))
        else:                                                   # "recency" (default)
            key = lambda r: (bool(r.get("pinned")), str(r.get("updated", "")))
        return sorted(rows, key=key, reverse=True)

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

    def list_chats(self, *, include_archived: bool = False,
                   include_trashed: bool = False, folder: str | None = None,
                   tag: str | None = None, sort: str = "recency") -> list[dict[str, Any]]:
        # N-81 B1: trashed chats are a distinct soft-deleted state — excluded from the
        # normal + archived listings; surfaced only via the trash view (list_trash).
        # N-81 B9c: optional ``folder``/``tag`` filters + a selectable ``sort`` key.
        rows = self._read_index()
        if not include_trashed:
            rows = [r for r in rows if not r.get("trashed")]
        if not include_archived:
            rows = [r for r in rows if not r.get("archived")]
        if folder is not None:
            # "" / "none" ⇒ the unfiled chats (no folder set).
            want = folder.strip()
            if want.lower() in ("", "none", "unfiled"):
                rows = [r for r in rows if not (r.get("folder") or "").strip()]
            else:
                rows = [r for r in rows if (r.get("folder") or "") == want]
        if tag:
            t = tag.strip().lower()
            rows = [r for r in rows
                    if any(t == str(x).strip().lower() for x in (r.get("tags") or []))]
        return self._sort(rows, sort=sort)

    def list_trash(self) -> list[dict[str, Any]]:
        """N-81 B1: only the soft-deleted (trashed) chats, newest first."""
        return self._sort([r for r in self._read_index() if r.get("trashed")])

    def search(self, query: str, *, regex: bool = False, chat_id: str | None = None,
               include_archived: bool = True, include_trashed: bool = False,
               limit: int = 200) -> list[dict[str, Any]]:
        """N-81 B2: find messages across chats (the whole append-only log, so matches
        in non-active variants are found too). ``chat_id`` restricts the scope to one
        chat (the use-time scope restriction). ``regex`` switches from case-insensitive
        substring to a regex; a bad regex yields no hits (never raises). Newest chats
        first; capped at ``limit`` hits."""
        q = (query or "").strip()
        if not q:
            return []
        if regex:
            try:
                pat = re.compile(q, re.IGNORECASE)
            except re.error:
                return []
            match = lambda t: bool(pat.search(t))
        else:
            ql = q.lower()
            match = lambda t: ql in t.lower()
        if chat_id:
            meta = self.chat_meta(chat_id)
            metas = [meta] if meta else []
        else:
            metas = self.list_chats(include_archived=include_archived,
                                    include_trashed=include_trashed)
        hits: list[dict[str, Any]] = []
        for meta in metas:
            cid = meta["id"]
            for m in self.messages(cid):
                text = m.get("text") or ""
                if not match(text):
                    continue
                hits.append({
                    "chatId": cid, "chatTitle": meta.get("title") or cid,
                    "messageId": m.get("id"), "seq": m.get("seq"),
                    "role": m.get("role"), "kind": m.get("kind", "turn"),
                    "ts": m.get("ts", ""),
                    "snippet": _hit_snippet(text, q, regex=regex),
                })
                if len(hits) >= limit:
                    return hits
        return hits

    def semantic_search(self, query: str, *, chat_id: str | None = None,
                        include_archived: bool = True, include_trashed: bool = False,
                        limit: int = 50) -> list[dict[str, Any]]:
        """N-81 B7: relevance-ranked search across chats. Reuses the retrieval FTS5/BM25
        pattern (porter-stemmed, word-order/morphology tolerant) over the append-only log
        — distinct from B2's exact substring/regex match. Builds an EPHEMERAL ``:memory:``
        FTS5 index per query from the scoped messages, so there is no second persistent
        writer (I1 untouched) and no index-staleness; chat corpora are small enough that a
        per-query build is cheap. Graceful degrade (I4): if SQLite has no FTS5, falls back
        to the lexical ``search`` (still useful, just unranked). Hits carry a ``score``
        and are returned best-first.

        Embedding-based recall (paper ``S_ret`` vector arm via retrieval.MemoryIndex) is a
        deliberate later seam — the embed role is gated/local-first, so MVP semantic search
        stays on the always-available lexical FTS substrate."""
        q = (query or "").strip()
        if not q:
            return []
        if chat_id:
            meta = self.chat_meta(chat_id)
            metas = [meta] if meta else []
        else:
            metas = self.list_chats(include_archived=include_archived,
                                    include_trashed=include_trashed)
        # Gather candidate messages (full log, so non-active variants match too).
        rows: list[dict[str, Any]] = []
        for meta in metas:
            cid = meta["id"]
            title = meta.get("title") or cid
            for m in self.messages(cid):
                text = m.get("text") or ""
                if text:
                    rows.append({"meta": m, "cid": cid, "title": title, "text": text})
        if not rows:
            return []
        try:
            import sqlite3
            con = sqlite3.connect(":memory:")
            con.execute("CREATE VIRTUAL TABLE m USING fts5(text, tokenize='porter unicode61')")
            con.executemany("INSERT INTO m(rowid, text) VALUES (?,?)",
                            [(i, r["text"]) for i, r in enumerate(rows)])
            fts_q = self._fts_query(q)
            if not fts_q:
                con.close()
                return []
            ranked = con.execute(
                "SELECT rowid, -bm25(m) FROM m WHERE m MATCH ? ORDER BY bm25(m) LIMIT ?",
                (fts_q, limit),
            ).fetchall()
            con.close()
        except sqlite3.OperationalError:
            # No FTS5 in this SQLite build — degrade to lexical (B2), tagged as a fallback.
            hits = self.search(q, chat_id=chat_id, include_archived=include_archived,
                               include_trashed=include_trashed, limit=limit)
            for h in hits:
                h["score"] = 0.0
                h["ranked"] = False
            return hits
        out: list[dict[str, Any]] = []
        for rowid, score in ranked:
            r = rows[rowid]
            m = r["meta"]
            out.append({
                "chatId": r["cid"], "chatTitle": r["title"],
                "messageId": m.get("id"), "seq": m.get("seq"),
                "role": m.get("role"), "kind": m.get("kind", "turn"),
                "ts": m.get("ts", ""),
                "snippet": _hit_snippet(r["text"], q),
                "score": round(float(score), 4), "ranked": True,
            })
        return out

    @staticmethod
    def _fts_query(text: str) -> str:
        """Natural-language query → a bounded FTS token OR-union (BM25 ranks the matches).
        Mirrors retrieval.db._fts_query so chat search behaves like the KB search."""
        words = list(dict.fromkeys(re.findall(r"[A-Za-z0-9_]+", text)))[:12]
        return " OR ".join(f'"{w}"' for w in words)

    def chat_meta(self, chat_id: str) -> dict[str, Any] | None:
        return next((r for r in self._read_index() if r.get("id") == chat_id), None)

    def create_chat(self, title: str = "", *, ttl_minutes: float | None = None) -> dict[str, Any]:
        """Create a chat. ``ttl_minutes`` (> 0) makes it a **temporary chat** (N-81 B4):
        ephemeral, with an ``expires_at`` timer; ``sweep_expired`` moves it to the trash
        once the timer elapses. Default ⇒ a permanent chat (back-compatible)."""
        nowdt = datetime.now(timezone.utc)
        now = nowdt.isoformat()
        with self._lock:
            rows = self._read_index()
            nid  = self._new_id({r.get("id") for r in rows})
            meta = {
                "id": nid, "title": _slug(title) if title else "",
                "created": now, "updated": now, "messages": 0, "archived": False,
            }
            if ttl_minutes is not None and float(ttl_minutes) > 0:
                mins = float(ttl_minutes)
                meta["ephemeral"]   = True
                meta["ttl_minutes"] = mins
                meta["expires_at"]  = (nowdt + timedelta(minutes=mins)).isoformat()
            self.chat_dir(nid).mkdir(parents=True, exist_ok=True)
            rows.append(meta)
            self._write_index(rows)
        return meta

    def set_ttl(self, chat_id: str, minutes: float | None) -> dict[str, Any] | None:
        """N-81 B4: set / extend / clear a chat's temporary-timer. ``minutes`` > 0 makes
        it ephemeral with a fresh ``expires_at`` (passing a new value RE-arms the timer
        from now — the "adjustable" timer); ``None`` or ``<= 0`` makes it permanent
        again (clears the ephemeral fields). Returns the updated meta, or None if the
        chat is unknown."""
        nowdt = datetime.now(timezone.utc)
        with self._lock:
            rows = self._read_index()
            row  = next((r for r in rows if r.get("id") == chat_id), None)
            if row is None:
                return None
            if minutes is None or float(minutes) <= 0:
                row.pop("ephemeral", None)
                row.pop("ttl_minutes", None)
                row.pop("expires_at", None)
            else:
                mins = float(minutes)
                row["ephemeral"]   = True
                row["ttl_minutes"] = mins
                row["expires_at"]  = (nowdt + timedelta(minutes=mins)).isoformat()
            row["updated"] = nowdt.isoformat()
            self._write_index(rows)
            return dict(row)

    def sweep_expired(self) -> list[str]:
        """N-81 B4: move every expired temporary chat to the trash (reversible — the
        existing trash lifecycle then governs final purge). Lazy: call it from read
        entry points (no background thread; stdlib core + graceful degrade). Returns the
        ids that just expired. Writes the registry only when something actually expired."""
        now = datetime.now(timezone.utc).timestamp()
        expired: list[str] = []
        with self._lock:
            rows = self._read_index()
            for r in rows:
                if not r.get("ephemeral") or r.get("trashed"):
                    continue
                exp = r.get("expires_at")
                if not exp:
                    continue
                try:
                    t = datetime.fromisoformat(str(exp)).timestamp()
                except ValueError:
                    continue
                if t <= now:
                    stamp = datetime.now(timezone.utc).isoformat()
                    r["trashed"]    = True
                    r["trashed_at"] = stamp
                    r["updated"]    = stamp
                    expired.append(str(r.get("id")))
            if expired:
                self._write_index(rows)
                if self.active_chat() in expired:     # never keep an expired chat active
                    try:
                        self._active.unlink()
                    except OSError:
                        pass
        return expired

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

    def pin_chat(self, chat_id: str, pinned: bool = True) -> dict[str, Any] | None:
        """N-81 B8: pin/favorite a chat (floats it to the top of every listing via
        ``_sort``). ``pinned=False`` un-pins. Returns the updated meta, or None if the
        chat is unknown. Does NOT bump ``updated`` — pinning is an org action, not an
        edit (so it never reshuffles the recency order among other pins)."""
        with self._lock:
            rows = self._read_index()
            row  = next((r for r in rows if r.get("id") == chat_id), None)
            if row is None:
                return None
            if pinned:
                row["pinned"] = True
            else:
                row.pop("pinned", None)
            self._write_index(rows)
            return dict(row)

    # ── organization: tags + folders/collections + bulk ops — N-81 B9c ─────────────

    @staticmethod
    def _norm_tags(tags: Any) -> list[str]:
        """Normalise a tag list: trim, drop blanks, de-dupe case-insensitively while
        preserving the first-seen casing + order."""
        out: list[str] = []
        seen: set[str] = set()
        for raw in (tags or []):
            t = str(raw).strip()
            if not t:
                continue
            k = t.lower()
            if k not in seen:
                seen.add(k)
                out.append(t)
        return out

    def set_tags(self, chat_id: str, tags: Any) -> dict[str, Any] | None:
        """N-81 B9c: replace a chat's tag set (org action — does NOT bump ``updated``).
        Returns the updated meta, or None if the chat is unknown."""
        norm = self._norm_tags(tags)
        with self._lock:
            rows = self._read_index()
            row  = next((r for r in rows if r.get("id") == chat_id), None)
            if row is None:
                return None
            if norm:
                row["tags"] = norm
            else:
                row.pop("tags", None)
            self._write_index(rows)
            return dict(row)

    def add_tag(self, chat_id: str, tag: str) -> dict[str, Any] | None:
        """N-81 B9c: add one tag (idempotent, case-insensitive)."""
        cur = (self.chat_meta(chat_id) or {}).get("tags") or []
        return self.set_tags(chat_id, [*cur, tag])

    def remove_tag(self, chat_id: str, tag: str) -> dict[str, Any] | None:
        """N-81 B9c: drop one tag (case-insensitive)."""
        t = str(tag).strip().lower()
        cur = (self.chat_meta(chat_id) or {}).get("tags") or []
        return self.set_tags(chat_id, [x for x in cur if str(x).strip().lower() != t])

    def all_tags(self, *, include_archived: bool = True) -> list[dict[str, Any]]:
        """N-81 B9c: every distinct tag in use + how many (live) chats carry it, most
        used first (the facet sidebar). Trashed chats are excluded."""
        counts: dict[str, dict[str, Any]] = {}
        for r in self.list_chats(include_archived=include_archived):
            for raw in (r.get("tags") or []):
                t = str(raw).strip()
                if not t:
                    continue
                k = t.lower()
                slot = counts.setdefault(k, {"tag": t, "count": 0})
                slot["count"] += 1
        return sorted(counts.values(), key=lambda d: (-d["count"], d["tag"].lower()))

    def set_folder(self, chat_id: str, folder: str | None) -> dict[str, Any] | None:
        """N-81 B9c: file a chat into a folder/collection (a flat label). ``None`` / blank
        unfiles it. Org action — does NOT bump ``updated``. Returns the meta, or None."""
        name = (folder or "").strip()
        with self._lock:
            rows = self._read_index()
            row  = next((r for r in rows if r.get("id") == chat_id), None)
            if row is None:
                return None
            if name:
                row["folder"] = name
            else:
                row.pop("folder", None)
            self._write_index(rows)
            return dict(row)

    def all_folders(self, *, include_archived: bool = True) -> list[dict[str, Any]]:
        """N-81 B9c: every folder in use + its (live) chat count, A→Z. Trashed excluded."""
        counts: dict[str, int] = {}
        for r in self.list_chats(include_archived=include_archived):
            name = (r.get("folder") or "").strip()
            if name:
                counts[name] = counts.get(name, 0) + 1
        return [{"folder": k, "count": counts[k]} for k in sorted(counts, key=str.lower)]

    def bulk(self, chat_ids: list[str], op: str, *, value: Any = None) -> dict[str, Any]:
        """N-81 B9c: apply one organisation op across many chats. ``op`` ∈
        trash | restore | archive | unarchive | pin | unpin | tag | untag | folder.
        ``value`` carries the tag (tag/untag) or folder name (folder; blank ⇒ unfile).
        Returns ``{op, ok:[ids], failed:[ids]}`` — each chat handled via the existing
        single-chat path (so locking/atomicity is unchanged)."""
        ok: list[str] = []
        failed: list[str] = []
        for cid in chat_ids:
            cid = str(cid)
            try:
                if op == "trash":
                    res = self.trash_chat(cid)
                elif op == "restore":
                    res = self.restore_chat(cid)
                elif op == "archive":
                    res = self.delete_chat(cid)               # soft archive
                elif op == "unarchive":
                    res = self.restore_chat(cid)
                elif op in ("pin", "unpin"):
                    res = self.pin_chat(cid, op == "pin") is not None
                elif op == "tag":
                    res = self.add_tag(cid, str(value or "")) is not None
                elif op == "untag":
                    res = self.remove_tag(cid, str(value or "")) is not None
                elif op == "folder":
                    res = self.set_folder(cid, value) is not None
                else:
                    raise ValueError(f"unknown bulk op: {op}")
            except ValueError:
                raise
            except Exception:
                res = False
            (ok if res else failed).append(cid)
        return {"op": op, "ok": ok, "failed": failed}

    # ── bookmarks (message-level pins / pinned snippets) — N-81 B8 ─────────────────

    def _read_bookmarks(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self._bookmarks.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _write_bookmarks(self, rows: list[dict[str, Any]]) -> None:
        tmp = self._bookmarks.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, self._bookmarks)

    def add_bookmark(self, chat_id: str, message_id: str, *, note: str = "") -> dict[str, Any] | None:
        """N-81 B8: bookmark a specific message (a jump target + optional ``note`` =
        a pinned snippet). Idempotent on (chatId, messageId): re-bookmarking updates the
        note. Returns the bookmark, or None if the message does not exist (so the UI never
        bookmarks a dangling id)."""
        msg = self.get_by_id(chat_id, message_id)
        if msg is None:
            return None
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            rows = self._read_bookmarks()
            existing = next((b for b in rows
                             if b.get("chatId") == chat_id and b.get("messageId") == message_id), None)
            if existing is not None:
                existing["note"] = note
                existing["updated"] = now
                bm = dict(existing)
            else:
                bm = {"chatId": chat_id, "messageId": message_id,
                      "seq": msg.get("seq"), "role": msg.get("role"),
                      "preview": _node_summary(msg.get("text") or ""),
                      "note": note, "created": now, "updated": now}
                rows.append(bm)
            self._write_bookmarks(rows)
        return bm

    def remove_bookmark(self, chat_id: str, message_id: str) -> bool:
        """N-81 B8: drop a message bookmark. Returns True if one was removed."""
        with self._lock:
            rows = self._read_bookmarks()
            kept = [b for b in rows
                    if not (b.get("chatId") == chat_id and b.get("messageId") == message_id)]
            if len(kept) == len(rows):
                return False
            self._write_bookmarks(kept)
        return True

    def list_bookmarks(self, *, chat_id: str | None = None) -> list[dict[str, Any]]:
        """N-81 B8: all bookmarks (newest first), optionally scoped to one chat."""
        rows = self._read_bookmarks()
        if chat_id:
            rows = [b for b in rows if b.get("chatId") == chat_id]
        return sorted(rows, key=lambda b: str(b.get("created", "")), reverse=True)

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
                # N-81 B8: drop this chat's bookmarks so none dangle (inline — _lock held).
                bms = self._read_bookmarks()
                kept = [b for b in bms if b.get("chatId") != chat_id]
                if len(kept) != len(bms):
                    self._write_bookmarks(kept)
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
        """Make an archived OR trashed chat available again (clears both states)."""
        with self._lock:
            rows = self._read_index()
            row = next((r for r in rows if r.get("id") == chat_id), None)
            if row is None:
                return False
            row["archived"] = False
            row["trashed"] = False
            row.pop("trashed_at", None)
            row["updated"] = datetime.now(timezone.utc).isoformat()
            self._write_index(rows)
        return True

    def trash_chat(self, chat_id: str) -> bool:
        """N-81 B1: soft-delete → the trash bin (distinct from archive). Reversible via
        restore_chat; permanently removed by purge_chat / purge_trashed."""
        with self._lock:
            rows = self._read_index()
            row  = next((r for r in rows if r.get("id") == chat_id), None)
            if row is None:
                return False
            now = datetime.now(timezone.utc).isoformat()
            row["trashed"] = True
            row["trashed_at"] = now
            row["updated"] = now
            self._write_index(rows)
            if self.active_chat() == chat_id:        # don't keep a trashed chat active
                try:
                    self._active.unlink()
                except OSError:
                    pass
        return True

    def purge_chat(self, chat_id: str) -> bool:
        """N-81 B1: permanent hard-delete (empties one chat from the trash). Removes the
        index row AND the on-disk transcript dir. Irreversible."""
        return self.delete_chat(chat_id, hard=True)

    def purge_trashed(self, *, older_than_days: float | None = None) -> int:
        """N-81 B1: empty the trash (optionally only entries trashed > N days ago, for an
        auto-purge timer). Returns the count purged."""
        cutoff = None
        if older_than_days is not None:
            cutoff = datetime.now(timezone.utc).timestamp() - older_than_days * 86400.0
        ids: list[str] = []
        for r in self._read_index():
            if not r.get("trashed"):
                continue
            if cutoff is not None:
                try:
                    ts = datetime.fromisoformat(str(r.get("trashed_at") or "")).timestamp()
                except ValueError:
                    ts = 0.0
                if ts > cutoff:
                    continue
            ids.append(str(r.get("id")))
        for cid in ids:
            self.delete_chat(cid, hard=True)
        return len(ids)

    # ── transcript ──────────────────────────────────────────────────────────────

    def append_message(
        self, chat_id: str, role: str, text: str, *,
        meta: dict[str, Any] | None = None,
        parent: Any = _AUTO, kind: str = "turn",
        edit_of: str | None = None, diff: str | None = None,
        set_head: bool = True,
    ) -> str:
        """Append one durable message to the event log. Returns its stable id
        ``<chatId>:<seq>``. Append-only — never mutates a prior record.

        ``parent`` defaults to ``_AUTO`` ⇒ chain to the current active leaf (so legacy
        two-call turns keep producing a clean linear backbone). An explicit ``None``
        marks a root; an explicit id places this message as a child/sibling of it
        (the regenerate/edit/branch paths use this to fork the DAG). The new node is
        made the active variant for its parent (``head``) unless ``set_head`` is False
        (N-81 B5: an anchored insert off a mid-path node must NOT hijack the existing
        path — it stays a browsable sibling branch)."""
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
            if set_head:
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
            # N-80 #1 (graph minimap): a short default node label + a longer scrollable
            # hover detail. ``snippet`` is retained for back-compat.
            "summary": _node_summary(r.get("text") or ""),
            "detail": (r.get("text") or "").strip()[:600],
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

    def insert_after(self, chat_id: str, anchor_id: str, role: str, text: str,
                     *, kind: str = "summary", meta: dict[str, Any] | None = None) -> str | None:
        """N-81 B5 #13: insert a block anchored at ``anchor_id``. If the anchor is a
        leaf on its path, the block extends the conversation inline; if the anchor
        already has a child, the block is recorded as a sibling branch off the anchor
        (browsable via the variant switcher) so the existing active path is never
        disrupted. Append-only / DAG-faithful. Returns the new id, or None if the
        anchor is unknown."""
        if self.get_by_id(chat_id, anchor_id) is None:
            return None
        recs = self.messages(chat_id)
        seq_to_id = {int(r.get("seq", 0)): r.get("id") for r in recs}
        has_child = any(self._resolve_parent(r, seq_to_id) == anchor_id for r in recs)
        return self.append_message(chat_id, role, text, parent=anchor_id,
                                   kind=kind, meta=meta, set_head=not has_child)

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

    # ── backup / restore (full, lossless) — N-81 catalog #4 ───────────────────────

    def backup_all(self, *, include_trashed: bool = True) -> dict[str, Any]:
        """A complete, durable, lossless snapshot of every chat: the full append-only
        event log + the head cursor + the registry metadata per chat (NOT the lossy
        active-path MDX of ``export_chat``). Round-trips through ``restore_bundle``.
        Stdlib-only / model-free."""
        chats: list[dict[str, Any]] = []
        for meta in self._sort(self._read_index()):
            if meta.get("trashed") and not include_trashed:
                continue
            cid = str(meta.get("id"))
            chats.append({
                "meta": dict(meta),
                "messages": self.messages(cid),
                "head": self._read_head(cid),
            })
        return {
            "version": 1, "kind": "lawrence-chat-backup",
            "exported": datetime.now(timezone.utc).isoformat(),
            "active": self.active_chat(), "count": len(chats), "chats": chats,
        }

    @staticmethod
    def _remap_ids(records: list[dict[str, Any]], head: dict[str, str],
                   old_id: str, new_id: str) -> tuple[list[dict[str, Any]], dict[str, str]]:
        """Rewrite every ``<old_id>:N`` reference (a record's id / parent / edit_of and
        the head's keys+values) to ``<new_id>:N`` so a re-id'd chat stays internally
        consistent. The root head key (``""``) and unrelated ids are left untouched."""
        opfx, npfx = f"{old_id}:", f"{new_id}:"
        def fix(v: Any) -> Any:
            return npfx + v[len(opfx):] if isinstance(v, str) and v.startswith(opfx) else v
        recs: list[dict[str, Any]] = []
        for r in records:
            r = dict(r)
            r["id"] = fix(r.get("id"))
            if r.get("parent"):
                r["parent"] = fix(r.get("parent"))
            if r.get("edit_of"):
                r["edit_of"] = fix(r.get("edit_of"))
            recs.append(r)
        new_head = {fix(k): fix(v) for k, v in (head or {}).items()}
        return recs, new_head

    def _install_chat(self, meta: dict[str, Any], records: list[dict[str, Any]],
                      head: dict[str, str]) -> None:
        """Write a chat's transcript + head + registry row verbatim (atomic temp+replace),
        replacing any existing row with the same id. Used by the conflict-free import and
        the rename import paths (the merge path goes through ``append_message``)."""
        cid = str(meta["id"])
        with self._lock:
            self.chat_dir(cid).mkdir(parents=True, exist_ok=True)
            mp  = self._messages_path(cid)
            tmp = mp.with_suffix(".jsonl.tmp")
            tmp.write_text(
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
                encoding="utf-8")
            os.replace(tmp, mp)
            if head:
                self._write_head(cid, head)
            row = dict(meta)
            row["messages"] = len(records)
            rows = [r for r in self._read_index() if r.get("id") != cid]
            rows.append(row)
            self._write_index(rows)

    def _merge_into(self, chat_id: str, incoming: list[dict[str, Any]]) -> dict[str, Any]:
        """Union an incoming message log into an existing chat (merge-conflict resolution).
        A record identical by id+text is already present (deduped). Otherwise it is
        appended as a NEW node (parents remapped to where they landed) and made a
        browsable sibling variant (``set_head=False`` — the existing active path is never
        disrupted). A record whose id already exists but whose text differs is a CONFLICT:
        both versions are kept (the incoming one appended as a variant). Append-only."""
        # Snapshot the ORIGINAL messages once: conflict/dedup detection runs only against
        # these (a freshly-appended node reuses the <chatId>:<seq> id space, so checking a
        # live map would let an incoming id spuriously collide with a just-merged node).
        original = {r.get("id"): r for r in self.messages(chat_id)}
        id_map: dict[str, str] = {}
        added = conflicts = 0
        for rec in sorted(incoming, key=lambda r: int(r.get("seq", 0))):
            iid, itext = rec.get("id"), (rec.get("text") or "")
            cur = original.get(iid)
            if cur is not None and (cur.get("text") or "") == itext:
                id_map[iid] = iid                  # identical — already present
                continue
            is_conflict = cur is not None          # same id, different text
            iparent = rec.get("parent")
            parent = id_map.get(iparent, iparent if iparent in original else None)
            ieo = rec.get("edit_of")
            edit_of = id_map.get(ieo) or (ieo if ieo in original else None)
            new_id = self.append_message(
                chat_id, str(rec.get("role") or "user"), itext,
                parent=parent, kind=str(rec.get("kind") or "turn"),
                edit_of=edit_of, diff=rec.get("diff"), meta=rec.get("meta"),
                set_head=False)
            id_map[iid] = new_id
            added += 1
            conflicts += int(is_conflict)
        return {"id": chat_id, "added": added, "conflicts": conflicts}

    def restore_bundle(self, bundle: dict[str, Any], *,
                       on_conflict: str = "skip") -> dict[str, Any]:
        """Import a backup produced by ``backup_all`` (import + restore). ``on_conflict``
        decides what happens when an incoming chat id already exists:

          * ``"skip"``   — keep the existing chat untouched (safe default);
          * ``"rename"`` — import the incoming copy under a fresh, conflict-free id;
          * ``"merge"``  — union the incoming log into the existing chat (see ``_merge_into``).

        A chat whose id is new is always imported verbatim (lossless). Returns a
        structured report ``{imported, skipped, renamed, merged}``. Append-only /
        DAG-faithful; never mutates a prior line."""
        if not isinstance(bundle, dict):
            raise ValueError("restore_bundle: bundle must be a dict")
        chats = bundle.get("chats")
        if not isinstance(chats, list):
            raise ValueError("restore_bundle: bundle has no 'chats' list")
        if on_conflict not in ("skip", "rename", "merge"):
            raise ValueError(f"restore_bundle: bad on_conflict {on_conflict!r}")
        report: dict[str, Any] = {"imported": [], "skipped": [], "renamed": [], "merged": []}
        for entry in chats:
            if not isinstance(entry, dict):
                continue
            meta    = dict(entry.get("meta") or {})
            cid     = str(meta.get("id") or "").strip()
            records = list(entry.get("messages") or [])
            head    = dict(entry.get("head") or {})
            if not cid:
                continue
            if self.chat_meta(cid) is None:                  # new id — import verbatim
                self._install_chat(meta, records, head)
                report["imported"].append(cid)
            elif on_conflict == "skip":
                report["skipped"].append(cid)
            elif on_conflict == "rename":
                new_id = self._new_id({r.get("id") for r in self._read_index()})
                recs2, head2 = self._remap_ids(records, head, cid, new_id)
                meta2 = dict(meta); meta2["id"] = new_id
                base  = meta2.get("title") or cid
                meta2["title"] = _slug(f"{base} (imported)")
                self._install_chat(meta2, recs2, head2)
                report["renamed"].append({"from": cid, "to": new_id})
            else:                                            # merge
                report["merged"].append(self._merge_into(cid, records))
        return report

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
        self.sweep_expired()                  # N-81 B4: retire timed-out temporary chats
        cid = self.active_chat()
        meta = self.chat_meta(cid) if cid else None
        if cid and meta and not meta.get("archived") and not meta.get("trashed"):
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
