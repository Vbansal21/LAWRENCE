"""Document ingestion — the NotebookLM half of retrieval (plan P6.T2).

ingest(path_or_url) converts any supported document (PDF, DOCX, HTML, CSV,
EPUB, video, plain text, web page — see converters.py) into chunks and stores
them in the SemanticDB. From then on every turn's retrieval can cite it like a
web source, with a stable file:// (or original http) URL.

Entry points: `lk ingest PATH|URL`, bridge `POST /ingest`, and UI attachments
saved with "persist".
"""
from __future__ import annotations

from pathlib import Path

from ..converters import convert
from .db import SemanticDB
from .web import chunk_text

# suffix → converter kind (mirrors the UI's attachment classification)
_KIND_BY_SUFFIX = {
    ".pdf": "pdf", ".docx": "document", ".doc": "document", ".odt": "document",
    ".rtf": "document", ".pptx": "presentation", ".pptm": "presentation",
    ".xlsx": "spreadsheet", ".xlsm": "spreadsheet", ".ods": "spreadsheet",
    ".csv": "spreadsheet", ".tsv": "spreadsheet",
    ".json": "structured data", ".jsonl": "structured data",
    ".yaml": "structured data", ".yml": "structured data", ".xml": "structured data",
    ".html": "html", ".htm": "html", ".epub": "ebook",
    ".mp4": "video", ".mkv": "video", ".webm": "video", ".mov": "video",
    ".wav": "audio file", ".mp3": "audio file", ".ogg": "audio file", ".flac": "audio file",
    ".tex": "latex", ".mmd": "mermaid",
}


def _kind_for(path: Path) -> str:
    return _KIND_BY_SUFFIX.get(path.suffix.lower(), "text")


def ingest(target: str, db: SemanticDB | None = None) -> tuple[int, str]:
    """Convert + chunk + store one document or URL.
    Returns (chunks_inserted, title). Raises on unreadable input."""
    db = db or SemanticDB()

    if target.startswith(("http://", "https://")):
        url, title = target, target.rstrip("/").rsplit("/", 1)[-1] or target
        text = convert("webpage", None, url=target, name=title)
    else:
        path = Path(target).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"no such file: {path}")
        url, title = f"file://{path}", path.name
        text = convert(_kind_for(path), path, name=title)

    if not text or text.startswith(f"[{title}:"):
        # converters return "[name: …unavailable/error…]" stubs on failure
        raise RuntimeError(text or "converter produced no text")

    chunks = chunk_text(text)
    if not chunks:
        # short documents can fall under the chunker's fragment floor — keep whole
        chunks = [text[:4000]] if text.strip() else []
    if not chunks:
        raise RuntimeError("document produced no usable text")

    inserted = db.upsert(url, title, chunks)
    return inserted, title
