"""lk memory ops — inspect / back up / clear LAWRENCE's memory, safely.

LAWRENCE's "memory" is the ``memory/`` directory. It holds four *distinct* kinds
of state (kept separate on purpose) plus a rebuildable cache:

  cache     retrieval.db*          FTS5 search index — derived, safe to drop
  rolling   rolling-l*.jsonl       L1/L2/L3 associative memory (+ archives)
  log       logs/*                 discrete turn/event log (daily files)
  journal   journal/*.mdx          the model's reflective narrative
  notes     notes/*                atomic zettelkasten notes — user-valuable, opt-in clear
  vault     vault/*                deep-study exports — user-valuable, never auto-wiped

``notes`` and ``vault`` are *opt-in* categories: counted and backed up, but never
touched by ``clear all`` — only when named explicitly (and ``vault`` not even then).

This module is file-level and stdlib-only: it never imports the kernel, so it
works before anything is loaded and from a fresh process against the same DB.
Destructive ops refuse while a kernel owns the writer lock (so we never corrupt a
live SQLite file) unless ``force=True``, and always snapshot a backup first.

Shared by `lk memory` (CLI) and the launcher's Memory panel (GUI) — identical
behaviour from either entry point.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MEM_DIR   = REPO_ROOT / "memory"
LOCK_PATH = MEM_DIR / ".writer.lock"
BACKUP_DIR = REPO_ROOT / ".runtime" / "memory-backups"

# category → glob patterns (relative to memory/). These are the ONLY categories
# 'all' clears. vault + notes are intentionally absent (opt-in only — see _OPT_IN).
_CATEGORIES = {
    "cache":   ["retrieval.db", "retrieval.db-shm", "retrieval.db-wal"],
    "rolling": ["rolling-*.jsonl", "rolling.jsonl"],
    "log":     ["logs/*", "tasks.json"],
    "journal": ["journal/*.mdx", "journal/*.md"],
}
# Counted + backed up like the rest, but NEVER swept by 'all'. ``notes`` can be
# cleared when named explicitly; ``vault`` is never auto-cleared at all.
_OPT_IN = {
    "notes": ["notes/*"],
}
_PRESERVE = {".writer.lock", ".gitkeep"}


def lock_owner() -> dict | None:
    """Who holds the memory writer lock right now (None if free). Stdlib only."""
    try:
        import fcntl
    except ImportError:
        return None
    try:
        f = open(LOCK_PATH, "a+", encoding="utf-8")
    except OSError:
        return None
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return None
    except OSError:
        f.seek(0)
        try:
            return json.loads(f.read().strip() or "{}")
        except json.JSONDecodeError:
            return {"role": "unknown"}
    finally:
        f.close()


def _iter(patterns: list[str]):
    for pat in patterns:
        yield from MEM_DIR.glob(pat)


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{int(n)}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}GB"


def _size(p: Path) -> int:
    try:
        return p.stat().st_size if p.is_file() else sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    except OSError:
        return 0


def stats() -> dict:
    """Per-category file count + total bytes, plus who (if anyone) is writing."""
    out: dict = {"locked_by": lock_owner(), "categories": {}}
    for cat, patterns in {**_CATEGORIES, **_OPT_IN}.items():
        files = [p for p in _iter(patterns) if p.exists()]
        out["categories"][cat] = {
            "files": len(files),
            "bytes": sum(_size(p) for p in files),
        }
    vault = MEM_DIR / "vault"
    out["categories"]["vault"] = {
        "files": sum(1 for _ in vault.rglob("*")) if vault.exists() else 0,
        "bytes": _size(vault) if vault.exists() else 0,
    }
    out["total_bytes"] = sum(c["bytes"] for c in out["categories"].values())
    return out


def backup() -> Path:
    """Zip the whole memory/ tree (minus the lock) into .runtime/memory-backups."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = BACKUP_DIR / f"memory-{stamp}"
    # shutil.make_archive zips MEM_DIR; the live lock file is harmless inside a zip.
    path = shutil.make_archive(str(base), "zip", root_dir=str(MEM_DIR))
    return Path(path)


def _delete(patterns: list[str]) -> int:
    removed = 0
    for p in _iter(patterns):
        if p.name in _PRESERVE or not p.exists():
            continue
        try:
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def clear(categories: list[str], *, force: bool = False, do_backup: bool = True) -> dict:
    """Clear one or more categories ('cache','rolling','log','journal','notes','all').

    Refuses while a kernel holds the writer lock unless force=True. 'all' covers
    every base category but NOT the opt-in ones ('notes','vault') — atomic notes
    and deep-study exports are only cleared when named explicitly ('vault' never).
    Returns {removed, backup, skipped}.
    """
    owner = lock_owner()
    if owner and not force:
        return {"skipped": f"kernel is running ({owner.get('role','?')} pid {owner.get('pid','?')}); "
                           "stop it first or use force", "removed": 0, "backup": None}
    valid = {**_CATEGORIES, **_OPT_IN}
    if "all" in categories:
        cats = list(_CATEGORIES)                 # opt-in categories are never in 'all'
    else:
        cats = [c for c in categories if c in valid]
    if not cats:
        return {"skipped": f"nothing to do (unknown: {categories})", "removed": 0, "backup": None}
    bkp = str(backup()) if do_backup else None
    removed = sum(_delete(valid[c]) for c in cats)
    return {"removed": removed, "backup": bkp, "cleared": cats, "skipped": None}
