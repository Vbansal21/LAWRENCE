from __future__ import annotations

from pathlib import Path


def read_text_file(path: Path, max_chars: int = 12000) -> str:
    if not path.exists() or not path.is_file():
        raise RuntimeError(f"file does not exist: {path}")
    data = path.read_text(encoding="utf-8", errors="replace")
    if len(data) > max_chars:
        return data[:max_chars] + "\n...[truncated]"
    return data

