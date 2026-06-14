"""Single-writer lock for the memory/ store.

Exactly one kernel process (REPL or UI bridge) may own memory/ at a time —
both build a full ContextStore/TaskStore stack, and two processes doing
read-whole-file → rewrite-whole-file cycles (compaction, trim, archive,
tasks.json saves) silently lose each other's writes. The lock is an advisory
flock, self-releasing on process exit (including kill -9), so a crashed owner
never needs manual cleanup.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_LOCK_PATH = REPO_ROOT / "memory" / ".writer.lock"

_handle = None   # keep the locked fd alive for the life of the process


def acquire_writer_lock(role: str) -> tuple[bool, str]:
    """Try to become the single memory/ writer.

    Returns (True, "") on success, or (False, owner_info) when another live
    process holds the lock. Re-entrant within a process. On platforms without
    fcntl there is nothing to enforce with, so it always succeeds.
    """
    global _handle
    if _handle is not None:
        return True, ""
    try:
        import fcntl
    except ImportError:
        return True, ""
    _LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    f = open(_LOCK_PATH, "a+", encoding="utf-8")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.seek(0)
        info = f.read().strip() or "unknown owner"
        f.close()
        return False, info
    f.seek(0)
    f.truncate()
    f.write(json.dumps({
        "pid": os.getpid(),
        "role": role,
        "started": datetime.now(timezone.utc).isoformat(),
    }))
    f.flush()
    _handle = f
    return True, ""
