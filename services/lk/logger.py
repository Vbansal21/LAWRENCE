"""JSONL turn log — one JSON line per turn, daily files under memory/logs/."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

_LOG_DIR = Path(__file__).resolve().parents[2] / "memory" / "logs"


def write_turn(entry: dict[str, object]) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path  = _LOG_DIR / f"{today}.jsonl"
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass
