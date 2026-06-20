"""Backup + retention robustness (memops).

Typed contract:
  INPUT    repeated backup() calls + LK_BACKUP_KEEP.
  OUTPUT   each backup() produces a zip; the backup dir never retains more than
           LK_BACKUP_KEEP zips (newest kept); KEEP=0 disables pruning.
  WHEN OK  prune runs after every backup; clear(do_backup) makes one first.
  WHEN FAIL .runtime/ would grow unbounded until the disk fills (a crash cause).

Pure stdlib, offline. Redirects memops' module-level paths to a temp tree so the
real memory/ + .runtime/ are never touched.
"""
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, "services")

from lk import memops as M  # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    print(f"{'PASS' if cond else 'FAIL'}: {name}" + (f"  [{extra}]" if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


tmp = Path(tempfile.mkdtemp())
mem = tmp / "memory"
mem.mkdir()
(mem / "context.log").write_text("seed\n", encoding="utf-8")
# redirect module paths
M.MEM_DIR = mem
M.BACKUP_DIR = tmp / ".runtime" / "memory-backups"


def n_backups():
    return len(list(M.BACKUP_DIR.glob("memory-*.zip"))) if M.BACKUP_DIR.exists() else 0


# ── A — backup produces a zip ────────────────────────────────────────────────
os.environ["LK_BACKUP_KEEP"] = "3"
# monkeypatch the stamp so successive backups get distinct names without sleeping
_orig_strftime = time.strftime
_counter = {"n": 0}


def _fake_strftime(fmt, *a):
    _counter["n"] += 1
    return f"test-{_counter['n']:05d}"


time.strftime = _fake_strftime
try:
    p = M.backup()
    check("A backup() returns an existing zip", p.exists() and p.suffix == ".zip", str(p))

    # ── B — retention caps the count at KEEP ─────────────────────────────────
    for _ in range(6):
        M.backup()
    check("B retained count == LK_BACKUP_KEEP (3)", n_backups() == 3, f"have {n_backups()}")

    # ── C — newest are the ones kept (lexicographic stamp == chronological) ──
    names = sorted(p.name for p in M.BACKUP_DIR.glob("memory-*.zip"))
    # 7 backups made (A + 6); keep=3 → the 3 highest-numbered survive
    check("C kept the NEWEST 3 backups", names == ["memory-test-00005.zip",
          "memory-test-00006.zip", "memory-test-00007.zip"], str(names))

    # ── D — explicit prune to a smaller keep ─────────────────────────────────
    removed = M.prune_backups(keep=1)
    check("D prune_backups(keep=1) leaves exactly 1", n_backups() == 1, f"have {n_backups()}")
    check("D2 prune returned the removed paths", len(removed) == 2, str(len(removed)))

    # ── E — KEEP=0 disables pruning (unbounded, explicit opt-out) ────────────
    os.environ["LK_BACKUP_KEEP"] = "0"
    before = n_backups()
    M.backup(); M.backup()
    check("E KEEP=0 keeps all backups", n_backups() == before + 2, f"{before}->{n_backups()}")
finally:
    time.strftime = _orig_strftime

print()
if FAILS:
    print(f"FAILED ({len(FAILS)}): " + ", ".join(FAILS))
    sys.exit(1)
print("test_backup OK")
