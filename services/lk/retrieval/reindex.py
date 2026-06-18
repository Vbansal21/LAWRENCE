"""Backfill the :class:`~lk.retrieval.memory.MemoryIndex` from on-disk memory.

The one-shot ``lk reindex`` runs this; the kernel also calls it at startup so the
hybrid recall index is populated from everything the agent has remembered. It is
the *only* place that knows the ``memory/`` file layout — :mod:`memory` stays a
clean index primitive. Incremental upserts (a new note / chat message) go through
``MemoryIndex.upsert`` directly at the write site; this module is the bulk path.

Every source is best-effort: a corrupt line or missing file is skipped, never
fatal. ``upsert`` is idempotent and skips unchanged text by hash, so re-running a
backfill is cheap and only (re-)embeds what actually changed.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .memory import MemoryIndex

REPO_ROOT = Path(__file__).resolve().parents[3]
_MEM_DIR  = REPO_ROOT / "memory"

MAX_TEXT = 2000   # cap indexed/embedded text per node (cheap embeds; full doc is on disk)


def _epoch(iso: str) -> float:
    try:
        return datetime.fromisoformat(iso).timestamp()
    except (ValueError, TypeError):
        return 0.0


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            nl = text.find("\n", end + 1)
            return text[nl + 1:] if nl != -1 else ""
    return text


def _index_notes(index: MemoryIndex, mem_dir: Path, embed: bool) -> int:
    idx = mem_dir / "notes" / "index.jsonl"
    n = 0
    try:
        lines = idx.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return 0
    for line in lines:
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        nid = rec.get("id")
        if not nid:
            continue
        try:
            body = _strip_frontmatter((mem_dir / "notes" / rec["file"]).read_text(encoding="utf-8")).strip()
        except (OSError, KeyError):
            continue
        tags = " ".join(rec.get("tags") or [])
        title = f"note: {rec.get('kind', '')} {tags}".strip()
        if index.upsert(nid, "note", body[:MAX_TEXT], ts=_epoch(rec.get("ts", "")),
                        title=title, embed=embed):
            n += 1
    return n


def _index_chats(index: MemoryIndex, mem_dir: Path, embed: bool) -> int:
    chats_dir = mem_dir / "chats"
    if not chats_dir.is_dir():
        return 0
    # chat titles from the index (best-effort)
    titles: dict[str, str] = {}
    try:
        for line in (chats_dir / "index.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                titles[r.get("id", "")] = r.get("title", "")
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    n = 0
    for msgs in chats_dir.glob("*/messages.jsonl"):
        chat_id = msgs.parent.name
        title = titles.get(chat_id, "")
        for line in msgs.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                m = json.loads(line)
            except json.JSONDecodeError:
                continue
            mid = m.get("id") or f"{chat_id}:{m.get('seq')}"
            text = (m.get("text") or "").strip()
            if not text:
                continue
            role = m.get("role", "")
            if index.upsert(mid, "chat", text[:MAX_TEXT], ts=_epoch(m.get("ts", "")),
                            title=f"chat[{role}] {title}".strip(), embed=embed):
                n += 1
    return n


def _index_rolling(index: MemoryIndex, mem_dir: Path, embed: bool) -> int:
    n = 0
    for path in [*sorted(mem_dir.glob("rolling-*.jsonl"))]:
        stem = path.stem
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = (rec.get("detailed") or rec.get("summary") or "").strip()
            if not text:
                continue
            if index.upsert(f"roll:{stem}:{i}", "rolling", text[:MAX_TEXT],
                            ts=_epoch(rec.get("ts", "")),
                            title=f"context: {rec.get('kind', '')}".strip(), embed=embed):
                n += 1
    return n


def _index_logs(index: MemoryIndex, mem_dir: Path, embed: bool) -> int:
    n = 0
    for path in sorted(mem_dir.glob("context-*.log")):
        date = path.stem.replace("context-", "")   # YYYY-MM-DD
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            # daily log lines are one-liner events ("[VISION 04:42:38] …"); the line
            # is short so we index it whole. ts left at 0 (recency-neutral) — the
            # log is the lowest-value, highest-volume source.
            if index.upsert(f"log:{date}:{i}", "log", line[:MAX_TEXT],
                            ts=0.0, title="log", embed=False):
                n += 1
    return n


def _index_journal(index: MemoryIndex, mem_dir: Path, embed: bool) -> int:
    jdir = mem_dir / "journal"
    if not jdir.is_dir():
        return 0
    n = 0
    for path in sorted(jdir.glob("*")):
        if not path.is_file():
            continue
        try:
            body = _strip_frontmatter(path.read_text(encoding="utf-8")).strip()
        except OSError:
            continue
        if not body:
            continue
        ts = _epoch(path.stem + "T00:00:00+00:00")   # journal files are date-named
        if index.upsert(f"journal:{path.stem}", "journal", body[:MAX_TEXT],
                        ts=ts, title=f"journal {path.stem}", embed=embed):
            n += 1
    return n


def backfill(
    index: MemoryIndex,
    *,
    mem_dir: Path = _MEM_DIR,
    embed: bool = True,
    sources: tuple[str, ...] = ("notes", "chats", "rolling", "log", "journal"),
) -> dict[str, Any]:
    """Index every memory source into ``index``. Returns per-source changed counts.

    ``embed`` is threaded to ``upsert`` (the local-first vector arm); pass ``False``
    for a fast lexical/graph-only backfill when no embedding backend is up. The
    high-volume daily log is always indexed lexical-only regardless."""
    fns = {
        "notes":   _index_notes,
        "chats":   _index_chats,
        "rolling": _index_rolling,
        "log":     _index_logs,
        "journal": _index_journal,
    }
    counts: dict[str, Any] = {}
    for name in sources:
        fn = fns.get(name)
        if fn is None:
            continue
        try:
            counts[name] = fn(index, mem_dir, embed)
        except Exception as exc:   # one bad source never aborts the whole backfill
            counts[name] = f"error: {exc}"
    counts["total"] = sum(v for v in counts.values() if isinstance(v, int))
    return counts


def startup_backfill(index: MemoryIndex, *, mem_dir: Path = _MEM_DIR,
                     background_embed: bool = True) -> dict[str, Any]:
    """Kernel-startup backfill: a fast lexical+graph pass so recall works
    immediately, then (optionally) a background daemon thread that fills the
    vector arm via local-first embeddings — so a slow/cold embed backend never
    delays startup. Best-effort throughout."""
    counts = backfill(index, mem_dir=mem_dir, embed=False)
    if background_embed:
        def _embed_pass() -> None:
            try:
                backfill(index, mem_dir=mem_dir, embed=True)
            except Exception:
                pass
        threading.Thread(target=_embed_pass, name="lk-mem-embed", daemon=True).start()
    return counts
