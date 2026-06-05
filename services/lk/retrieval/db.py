"""Persistent semantic store for retrieved web content.

SQLite + FTS5 (full-text search with BM25 built in). Falls back to a LIKE-based
search if FTS5 is not available in the local SQLite build.

Stored chunks are deduplicated by URL + content hash. Re-fetching a URL already
in the DB is skipped unless the content has changed (hash comparison).

This is the "local NotebookLM" layer: once content is retrieved and stored,
future queries on overlapping topics hit the DB instead of the web.
"""
from __future__ import annotations

import hashlib
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DB_PATH   = REPO_ROOT / "memory" / "retrieval.db"
TTL_DAYS  = 30   # stale after N days; re-fetch if needed


@dataclass
class StoredChunk:
    url: str
    title: str
    text: str
    score: float = 0.0


class SemanticDB:
    def __init__(self, path: Path = DB_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(str(path), check_same_thread=False)
        self._con.execute("PRAGMA journal_mode=WAL")  # safe for concurrent read+write
        self._fts5 = self._init_schema()

    def _init_schema(self) -> bool:
        cur = self._con.cursor()
        # raw chunks table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id          INTEGER PRIMARY KEY,
                url         TEXT NOT NULL,
                title       TEXT,
                text        TEXT NOT NULL,
                text_hash   TEXT NOT NULL,
                ts_fetched  REAL NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_url ON chunks(url)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_hash ON chunks(text_hash)")

        # try FTS5
        fts5 = False
        try:
            cur.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                    url, title, text, content='chunks', content_rowid='id',
                    tokenize='porter unicode61'
                )
            """)
            fts5 = True
        except sqlite3.OperationalError:
            pass  # FTS5 unavailable — fall back to LIKE

        self._con.commit()
        return fts5

    # ── write ─────────────────────────────────────────────────────────────────

    def upsert(self, url: str, title: str, chunks: list[str]) -> int:
        """Insert new chunks for url. Skips chunks already present by content hash. Returns count inserted."""
        cur = self._con.cursor()
        now = time.time()
        inserted = 0
        for text in chunks:
            h = hashlib.sha1(text.encode()).hexdigest()
            if cur.execute("SELECT 1 FROM chunks WHERE text_hash=?", (h,)).fetchone():
                continue
            cur.execute(
                "INSERT INTO chunks (url, title, text, text_hash, ts_fetched) VALUES (?,?,?,?,?)",
                (url, title, text, h, now),
            )
            if self._fts5:
                rowid = cur.lastrowid
                cur.execute(
                    "INSERT INTO chunks_fts(rowid, url, title, text) VALUES (?,?,?,?)",
                    (rowid, url, title, text),
                )
            inserted += 1
        self._con.commit()
        return inserted

    # ── read ──────────────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 10) -> list[StoredChunk]:
        cur = self._con.cursor()
        if self._fts5:
            # FTS5 BM25 — negate because bm25() returns negative scores
            safe_q = query.replace('"', '""')
            try:
                rows = cur.execute(
                    """SELECT c.url, c.title, c.text, -bm25(chunks_fts)
                       FROM chunks_fts f JOIN chunks c ON f.rowid = c.id
                       WHERE chunks_fts MATCH ?
                       ORDER BY bm25(chunks_fts)
                       LIMIT ?""",
                    (safe_q, top_k),
                ).fetchall()
                return [StoredChunk(url=r[0], title=r[1], text=r[2], score=r[3]) for r in rows]
            except sqlite3.OperationalError:
                pass  # malformed query — fall through to LIKE

        # fallback: keyword LIKE search
        words = [w for w in query.split() if len(w) > 3][:6]
        if not words:
            return []
        conditions = " OR ".join("text LIKE ?" for _ in words)
        params = tuple(f"%{w}%" for w in words) + (top_k,)
        rows = cur.execute(
            f"SELECT url, title, text FROM chunks WHERE {conditions} LIMIT ?", params
        ).fetchall()
        return [StoredChunk(url=r[0], title=r[1], text=r[2]) for r in rows]

    def url_known(self, url: str) -> bool:
        cur = self._con.cursor()
        row = cur.execute(
            "SELECT ts_fetched FROM chunks WHERE url=? LIMIT 1", (url,)
        ).fetchone()
        if not row:
            return False
        age_days = (time.time() - row[0]) / 86400
        return age_days < TTL_DAYS

    def close(self) -> None:
        self._con.close()
