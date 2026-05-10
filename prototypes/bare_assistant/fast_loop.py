from __future__ import annotations

from pathlib import Path


def acknowledge(user_text: str, images: list[Path], audios: list[Path], web_enabled: bool) -> str:
    parts = ["captured text"]
    if images:
        parts.append(f"{len(images)} image/screenshot item(s)")
    if audios:
        parts.append(f"{len(audios)} audio item(s)")
    parts.append("web retrieval on" if web_enabled else "web retrieval off")
    query = user_text.strip() or "(no explicit query)"
    return f"Acknowledged: {', '.join(parts)}. Query: {query}"

