"""Zettelkasten — atomic, addressable notes (WS-M/M3).

A fourth, *distinct* kind of memory, deliberately separate from the others:

  rolling (store.py)   compressing tiers — lossy, time-ordered working memory
  journal (admin.py)   narrative reflection — prose, one entry per session/day
  daily log            flat one-liner stream — every event, never trimmed
  **notes (here)**     one file per significant event — atomic, append-only,
                       addressable by id, tagged, and cross-linked (`[[id]]`)

Each note is a Markdown file ``memory/notes/<id>-<slug>.md`` with YAML
frontmatter (`id, ts, kind, tags, links, source`) + body, plus an append-only
``index.jsonl`` that is the metadata source of truth (so reads never parse YAML).
Backlinks are derived from forward `links` (and `[[id]]` refs parsed from bodies),
so a link is navigable in both directions.

Stdlib-only and model-free — usable from the light front-door (`lk notes`) and
from the kernel alike. Notes are **append-only**: an id is never rewritten. An
optional `index_fn` lets a caller also feed note bodies to the retrieval FTS so
the model can surface them; the store itself stays decoupled from retrieval.
"""
from __future__ import annotations

import json
import re
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
_MEM_DIR  = REPO_ROOT / "memory"

_LINK_RE = re.compile(r"\[\[([0-9]{8}-[0-9]{6}(?:-[0-9]+)?)\]\]")
_WORD_RE = re.compile(r"[a-z0-9]+")


def _slug(text: str, n: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:n].rstrip("-") or "note"


def _words(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall(text.lower()) if len(w) > 2}


def _strip_frontmatter(text: str) -> str:
    """Return the body below a leading ``---`` … ``---`` YAML block (if any)."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            nl = text.find("\n", end + 1)
            return text[nl + 1:] if nl != -1 else ""
    return text


class NoteStore:
    """Atomic note storage. Thread-safe; append-only; addressable by id."""

    def __init__(
        self,
        mem_dir: Path = _MEM_DIR,
        index_fn: Callable[[str, str, str], None] | None = None,
    ) -> None:
        self._dir   = mem_dir / "notes"
        self._index = self._dir / "index.jsonl"
        self._edges = self._dir / "edges.jsonl"
        self._lock  = threading.Lock()
        self._index_fn = index_fn        # optional: (id, title, body) → retrieval FTS
        self._dir.mkdir(parents=True, exist_ok=True)

    # ── index helpers ───────────────────────────────────────────────────────────

    def _read_index(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        try:
            lines = self._index.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return out
        for l in lines:                          # tolerate a single corrupt line
            if l.strip():
                try:
                    out.append(json.loads(l))
                except json.JSONDecodeError:
                    pass
        return out

    def _new_id(self, existing: set[str]) -> str:
        base = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        nid, k = base, 2
        while nid in existing:
            nid = f"{base}-{k}"
            k += 1
        return nid

    # ── write ───────────────────────────────────────────────────────────────────

    def write_note(
        self,
        kind: str,
        text: str,
        *,
        source: str = "",
        tags: list[str] | tuple[str, ...] = (),
        links: list[str] | tuple[str, ...] = (),
    ) -> str:
        """Create one atomic note. Returns its id. Append-only — never overwrites."""
        text = (text or "").strip()
        if not text:
            return ""
        # forward links = explicit links ∪ any [[id]] referenced in the body
        link_set = list(dict.fromkeys([*links, *_LINK_RE.findall(text)]))
        tag_list = [str(t) for t in tags if t][:12]
        ts = datetime.now(timezone.utc).isoformat()

        with self._lock:
            existing = {e.get("id") for e in self._read_index()}
            nid = self._new_id(existing)
            fname = f"{nid}-{_slug(text)}.md"
            fm = [
                "---",
                f"id: {nid}",
                f"ts: {ts}",
                f"kind: {kind}",
                f"tags: [{', '.join(tag_list)}]",
                f"links: [{', '.join(link_set)}]",
                f'source: "{source}"',
                "---",
                "",
            ]
            (self._dir / fname).write_text("\n".join(fm) + text + "\n", encoding="utf-8")
            rec = {"id": nid, "ts": ts, "kind": kind, "tags": tag_list,
                   "links": link_set, "source": source, "file": fname}
            with self._index.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        if self._index_fn:                       # best-effort retrieval indexing
            try:
                self._index_fn(nid, f"note: {kind} {' '.join(tag_list)}".strip(), text)
            except Exception:
                pass
        return nid

    # ── read / navigate ─────────────────────────────────────────────────────────

    def read_note(self, note_id: str) -> dict[str, Any] | None:
        """Full note (metadata from the index + body from the file + backlinks)."""
        rec = next((e for e in self._read_index() if e.get("id") == note_id), None)
        if rec is None:
            return None
        body = ""
        try:
            body = _strip_frontmatter((self._dir / rec["file"]).read_text(encoding="utf-8")).strip()
        except (OSError, KeyError):
            pass
        return {**rec, "body": body, "backlinks": self.backlinks(note_id)}

    def backlinks(self, note_id: str) -> list[str]:
        """Ids of notes whose forward links point at note_id (reverse edges)."""
        return [e["id"] for e in self._read_index() if note_id in (e.get("links") or [])]

    def list_notes(self, limit: int = 20) -> list[dict[str, Any]]:
        """Most-recent-first metadata records (no bodies)."""
        return list(reversed(self._read_index()))[:limit]

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Keyword search over note bodies + tags + kind. Returns scored records
        (most relevant first). The user-facing `lk notes search`; works offline
        with no retrieval DB (the DB FTS is an additional, optional surface)."""
        terms = _words(query)
        if not terms:
            return []
        scored: list[tuple[int, dict[str, Any]]] = []
        for rec in self._read_index():
            hay = set(rec.get("tags") or []) | _words(str(rec.get("kind", "")))
            try:
                hay |= _words(_strip_frontmatter((self._dir / rec["file"]).read_text(encoding="utf-8")))
            except (OSError, KeyError):
                pass
            score = len(terms & hay)
            if score:
                scored.append((score, rec))
        scored.sort(key=lambda x: (x[0], x[1].get("ts", "")), reverse=True)
        return [rec for _s, rec in scored[:limit]]

    def stats(self) -> dict[str, int]:
        """Count + total bytes of the notes tree (for `lk memory` / memops)."""
        files = list(self._dir.glob("*.md"))
        nbytes = 0
        for p in [*files, self._index, self._edges]:
            try:
                nbytes += p.stat().st_size
            except OSError:
                pass
        return {"notes": len(files), "bytes": nbytes}

    # ── generic graph edges (WS-U Track 2) ──────────────────────────────────────
    # Notes link note↔note via `[[id]]`. The graph generalises to ANY addressable
    # node — chat messages ("<chatId>:<seq>"), whole chats ("<chatId>"), or notes —
    # so "link this point → another chat" is a bidirectional edge in the SAME graph
    # as the zettelkasten. Edges live in an append-only edges.jsonl; node ids are
    # opaque strings, so messages and notes coexist as first-class nodes.

    def _read_edges(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        try:
            lines = self._edges.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return out
        for l in lines:
            if l.strip():
                try:
                    out.append(json.loads(l))
                except json.JSONDecodeError:
                    pass
        return out

    def add_edge(
        self, src: str, dst: str, *, kind: str = "link", meta: dict[str, Any] | None = None
    ) -> bool:
        """Create a bidirectional edge between two nodes. Idempotent — an identical
        (src, dst, kind) edge is never duplicated. Returns True if a new edge was
        written. Self-loops and empty ids are rejected."""
        src, dst = str(src or "").strip(), str(dst or "").strip()
        if not src or not dst or src == dst:
            return False
        with self._lock:
            for e in self._read_edges():
                if e.get("src") == src and e.get("dst") == dst and e.get("kind", "link") == kind:
                    return False
            rec: dict[str, Any] = {
                "src": src, "dst": dst, "kind": kind,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            if meta:
                rec["meta"] = meta
            with self._edges.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return True

    def edges_for(self, node: str) -> list[dict[str, Any]]:
        """Every edge incident on ``node``, each annotated with the other endpoint
        and direction ('out' = node is src, 'in' = node is dst)."""
        node = str(node or "").strip()
        out: list[dict[str, Any]] = []
        for e in self._read_edges():
            if e.get("src") == node:
                out.append({**e, "peer": e.get("dst"), "dir": "out"})
            elif e.get("dst") == node:
                out.append({**e, "peer": e.get("src"), "dir": "in"})
        return out

    def neighborhood(self, node: str) -> dict[str, Any]:
        """The local graph around ``node``: its edges (both directions) plus, when
        ``node`` is itself a note id, that note's forward `[[links]]` and backlinks —
        so messages and notes surface uniformly when navigating cross-chat links."""
        node = str(node or "").strip()
        edges = self.edges_for(node)
        result: dict[str, Any] = {
            "node": node,
            "out":  [e["peer"] for e in edges if e["dir"] == "out"],
            "in":   [e["peer"] for e in edges if e["dir"] == "in"],
            "edges": edges,
        }
        rec = next((e for e in self._read_index() if e.get("id") == node), None)
        if rec is not None:
            result["links"] = list(rec.get("links") or [])
            result["backlinks"] = self.backlinks(node)
        return result
