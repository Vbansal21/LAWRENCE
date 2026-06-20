"""Unified hybrid recall over the agent's OWN memory (N-02 — RET).

This is the keystone of the autonomous context spine: the *probe* the watcher
uses to recall the right context on its own, instead of replaying a recency tail.
It indexes everything the agent remembers about itself and its user — atomic
notes, chat transcripts, the rolling working-memory summaries, the daily event
log, and journal entries — into one store and answers ``recall(query)`` with a
fused, provenance-tagged bundle.

Three retrieval *arms* run against that store and are combined with **Reciprocal
Rank Fusion** (parameterless, robust to per-arm score scales):

  - **lexical**  SQLite FTS5 / BM25 over the indexed text (exact-term recall).
  - **vector**   cosine over dense embeddings (semantic recall) — LOCAL-FIRST via
                 ``model.embed`` (see [[lawrence-local-first]]); if no embedding
                 backend is available the arm is simply skipped, never failing the
                 recall (degrade to lexical+graph).
  - **graph**    neighbourhood expansion over ``NoteStore`` edges/links, so a node
                 the user explicitly linked surfaces alongside its relevant peers.

After fusion the base RRF score is shaped by the paper's north-star
``S_ret = βℓL + βvV + βgG + βrR + βhH − βpP``:

  - a **recency** multiplier (R) — recent memory outranks stale memory;
  - a **link boost** (G) — a node touched by an explicit user ``link`` edge is
    promoted (the "weighted relevance" decision: a link raises ranking);
  - a **delete penalty** (P) — a node the user deleted is excluded; the exclusion
    is reversible (the node stays indexed, only suppressed at recall time).

One durable store of truth: SQLite holds text + the (optional) embedding blob, and
the in-memory :class:`~lk.retrieval.vectors.VectorIndex` is rebuilt from it on
load — so there is no second on-disk file to keep in sync. Stdlib-only on the core
path (invariant I4); numpy, when present, only accelerates the vector scan.
"""
from __future__ import annotations

import hashlib
import math
import re
import sqlite3
import time
from array import array
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .vectors import VectorIndex

REPO_ROOT = Path(__file__).resolve().parents[3]
DB_PATH   = REPO_ROOT / "memory" / "memory_index.db"

# ── fusion / shaping constants (the β's of S_ret; tunable, deliberately mild) ──
RRF_K          = 60      # standard Reciprocal Rank Fusion damping
ARM_DEPTH      = 50      # candidates pulled per arm before fusion
VECTOR_MIN_COS = 0.15    # floor: below this the vector arm treats a hit as noise
RECENCY_WEIGHT = 0.30    # βr: a just-touched node scores up to +30%
RECENCY_HALFLIFE_DAYS = 30.0
LINK_BOOST     = 0.50    # βg: an explicitly linked node is promoted +50%

_WORD_RE = re.compile(r"[A-Za-z0-9_]+")


def _tokens(text: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text or "") if len(w) > 1]


def _fts_match_query(query: str) -> str:
    """Build a safe FTS5 MATCH expression from free text: OR of quoted terms.

    Quoting each token sidesteps FTS5 operator syntax (``-``, ``*``, ``:``, ``"``)
    so arbitrary user/recall text can never raise a malformed-query error."""
    terms = list(dict.fromkeys(_tokens(query)))[:24]
    return " OR ".join(f'"{t}"' for t in terms)


def _recency_boost(ts: float, now: float, *, weight: float = RECENCY_WEIGHT,
                   halflife_days: float = RECENCY_HALFLIFE_DAYS) -> float:
    """Multiplicative nudge in [1, 1+weight]; fades to 1.0 with age. Never
    penalises (an old-but-relevant memory is nudged down, not buried)."""
    if ts <= 0:
        return 1.0
    age_days = max(0.0, (now - ts) / 86400.0)
    fresh01 = 0.5 ** (age_days / halflife_days)   # exponential half-life decay
    return 1.0 + weight * fresh01


@dataclass
class RecallResult:
    """One recalled memory item, provenance-tagged for the model + UI."""
    node_id:     str
    source_kind: str        # note | chat | rolling | log | journal | …
    ts:          float
    title:       str
    text:        str
    score:       float = 0.0
    arms:        tuple[str, ...] = ()    # which arms surfaced it (lexical/vector/graph)


@dataclass
class _Row:
    node_id: str
    source_kind: str
    ts: float
    title: str
    text: str
    text_hash: str


def _rrf(rankings: dict[str, list[str]], *, k: int = RRF_K) -> dict[str, float]:
    """Reciprocal Rank Fusion: score(d) = Σ_arm 1/(k + rank_arm(d)). Each arm is an
    ordered list of node_ids (best first). Absent from an arm = no contribution."""
    fused: dict[str, float] = {}
    for ids in rankings.values():
        for rank, node_id in enumerate(ids):
            fused[node_id] = fused.get(node_id, 0.0) + 1.0 / (k + rank + 1)
    return fused


class MemoryIndex:
    """Hybrid lexical+vector+graph index over the agent's own memory.

    ``notes`` (optional :class:`~lk.ctx.notes.NoteStore`) supplies the graph arm
    and the link/delete edge signals. ``embed_fn`` (optional) supplies the vector
    arm; when ``None`` the index lazily uses ``lk.model.embed`` (local-first) and
    silently skips the vector arm if no embedding backend is available.
    """

    def __init__(
        self,
        path: Path = DB_PATH,
        *,
        notes: Any = None,
        embed_fn: Callable[[list[str]], list[list[float]]] | None = None,
    ) -> None:
        self._notes = notes
        self._embed_fn = embed_fn
        path.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(str(path), check_same_thread=False)
        self._con.execute("PRAGMA journal_mode=WAL")
        self._fts5 = self._init_schema()
        self._vec = VectorIndex()
        self._load_vectors()

    def set_notes(self, notes: Any) -> None:
        """Attach (or replace) the NoteStore that powers the graph arm + link/delete
        edge signals. Lets the kernel build the index before the NoteStore exists."""
        self._notes = notes

    @property
    def notes(self) -> Any:
        """The attached NoteStore (graph arm + durable-note formation), or None.
        Read-only handle so the kernel can promote turns to durable notes (N-71)
        without threading a second object through every call site."""
        return self._notes

    # ── schema / load ───────────────────────────────────────────────────────────

    def _init_schema(self) -> bool:
        cur = self._con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS mem (
                node_id     TEXT PRIMARY KEY,
                source_kind TEXT NOT NULL,
                ts          REAL NOT NULL,
                title       TEXT,
                text        TEXT NOT NULL,
                text_hash   TEXT NOT NULL,
                embedding   BLOB,
                embed_dim   INTEGER NOT NULL DEFAULT 0
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mem_kind ON mem(source_kind)")
        cur.execute("CREATE TABLE IF NOT EXISTS mem_deleted (node_id TEXT PRIMARY KEY)")
        fts5 = False
        try:
            cur.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS mem_fts USING fts5(
                    node_id UNINDEXED, title, text, tokenize='porter unicode61'
                )
            """)
            fts5 = True
        except sqlite3.OperationalError:
            pass   # FTS5 unavailable — lexical arm falls back to LIKE
        self._con.commit()
        return fts5

    def _load_vectors(self) -> None:
        """Rebuild the in-memory VectorIndex from the embedding blobs in SQLite —
        SQLite is the single source of truth, so there is no separate vector file
        to fall out of sync."""
        cur = self._con.cursor()
        for node_id, blob, dim in cur.execute(
            "SELECT node_id, embedding, embed_dim FROM mem WHERE embedding IS NOT NULL"
        ):
            if not blob or not dim:
                continue
            vec = array("f")
            vec.frombytes(blob)
            if len(vec) == dim:
                self._vec.add(node_id, vec)

    # ── embedding (local-first, best-effort) ────────────────────────────────────

    def _embed(self, texts: list[str]) -> list[list[float]] | None:
        """Embed ``texts`` via the injected fn or local-first ``model.embed``.
        Returns ``None`` (arm unavailable) on any failure — recall then degrades to
        the lexical+graph arms rather than erroring."""
        if not texts:
            return []
        fn = self._embed_fn
        if fn is None:
            try:                                  # lazy import keeps the core stdlib-only (I4)
                from .. import model as _model
                fn = _model.embed
            except Exception:
                return None
        try:
            out = fn(texts)
        except Exception:
            return None
        if not out or len(out) != len(texts) or not all(out):
            return None
        return out

    # ── write ───────────────────────────────────────────────────────────────────

    def upsert(
        self, node_id: str, source_kind: str, text: str,
        *, ts: float | None = None, title: str = "", embed: bool = True,
    ) -> bool:
        """Insert or replace one memory node. Idempotent by ``node_id``; skips
        re-embedding when the text is unchanged (hash match). Returns True when the
        stored content actually changed."""
        node_id = (node_id or "").strip()
        text = (text or "").strip()
        if not node_id or not text:
            return False
        if ts is None:
            ts = time.time()
        h = hashlib.sha1(text.encode("utf-8")).hexdigest()

        cur = self._con.cursor()
        prev = cur.execute(
            "SELECT text_hash, embedding, embed_dim FROM mem WHERE node_id=?", (node_id,)
        ).fetchone()
        # Skip only when the text is unchanged AND the embedding state is already
        # satisfied — so a fast embed=False pass doesn't block a later embed=True
        # pass from filling in the vector arm for the same node.
        if prev and prev[0] == h and (not embed or (prev[2] or 0) > 0):
            return False

        emb_blob: bytes | None = None
        emb_dim = 0
        vec_row: array | None = None
        if embed:
            vecs = self._embed([text])
            if vecs:
                vec_row = array("f", vecs[0])
                emb_blob, emb_dim = vec_row.tobytes(), len(vec_row)

        cur.execute(
            """INSERT INTO mem (node_id, source_kind, ts, title, text, text_hash, embedding, embed_dim)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(node_id) DO UPDATE SET
                 source_kind=excluded.source_kind, ts=excluded.ts, title=excluded.title,
                 text=excluded.text, text_hash=excluded.text_hash,
                 embedding=excluded.embedding, embed_dim=excluded.embed_dim""",
            (node_id, source_kind, ts, title, text, h, emb_blob, emb_dim),
        )
        if self._fts5:
            cur.execute("DELETE FROM mem_fts WHERE node_id=?", (node_id,))
            cur.execute("INSERT INTO mem_fts (node_id, title, text) VALUES (?,?,?)",
                        (node_id, title, text))
        self._con.commit()

        if vec_row is not None:
            self._vec.add(node_id, vec_row)
        elif node_id in self._vec:
            self._vec.remove(node_id)   # text changed and no longer embeddable
        return True

    def add_many(self, items: Iterable[tuple[str, str, str]], *, embed: bool = True) -> int:
        """Upsert many ``(node_id, source_kind, text)`` triples; returns changed count."""
        return sum(1 for nid, kind, text in items if self.upsert(nid, kind, text, embed=embed))

    # ── delete penalty (P) — reversible suppression ─────────────────────────────

    def mark_deleted(self, node_id: str) -> None:
        """Suppress ``node_id`` from recall (the −P term). Reversible; the node
        stays indexed so :meth:`clear_deleted` fully restores it."""
        node_id = (node_id or "").strip()
        if not node_id:
            return
        self._con.execute("INSERT OR IGNORE INTO mem_deleted (node_id) VALUES (?)", (node_id,))
        self._con.commit()

    def clear_deleted(self, node_id: str) -> None:
        self._con.execute("DELETE FROM mem_deleted WHERE node_id=?", ((node_id or "").strip(),))
        self._con.commit()

    def _deleted_set(self) -> set[str]:
        return {r[0] for r in self._con.execute("SELECT node_id FROM mem_deleted")}

    # ── graph signals (G) via NoteStore ─────────────────────────────────────────

    def _linked_nodes(self) -> set[str]:
        """Node ids touched by an explicit user ``link`` edge — these get the +G
        boost. Empty when there is no NoteStore or no edges."""
        notes = self._notes
        if notes is None or not hasattr(notes, "_read_edges"):
            return set()
        linked: set[str] = set()
        try:
            for e in notes._read_edges():
                if e.get("kind", "link") == "link":
                    linked.add(str(e.get("src", "")))
                    linked.add(str(e.get("dst", "")))
        except Exception:
            return set()
        linked.discard("")
        return linked

    def _graph_expand(self, seeds: list[str], *, limit: int = ARM_DEPTH) -> list[str]:
        """Neighbourhood expansion: peers of the seed nodes via NoteStore edges +
        note links/backlinks, ranked by how many seeds reach them."""
        notes = self._notes
        if notes is None or not hasattr(notes, "neighborhood"):
            return []
        freq: dict[str, int] = {}
        seed_set = set(seeds)
        for s in seeds[:limit]:
            try:
                nb = notes.neighborhood(s)
            except Exception:
                continue
            peers = [*nb.get("out", []), *nb.get("in", []),
                     *nb.get("links", []), *nb.get("backlinks", [])]
            for p in peers:
                p = str(p)
                if p and p not in seed_set:
                    freq[p] = freq.get(p, 0) + 1
        return [n for n, _ in sorted(freq.items(), key=lambda kv: kv[1], reverse=True)][:limit]

    # ── read ─────────────────────────────────────────────────────────────────────

    def _lexical(self, query: str, depth: int) -> list[str]:
        cur = self._con.cursor()
        if self._fts5:
            match = _fts_match_query(query)
            if match:
                try:
                    rows = cur.execute(
                        """SELECT node_id FROM mem_fts WHERE mem_fts MATCH ?
                           ORDER BY bm25(mem_fts) LIMIT ?""",
                        (match, depth),
                    ).fetchall()
                    return [r[0] for r in rows]
                except sqlite3.OperationalError:
                    pass   # fall through to LIKE
        words = [w for w in _tokens(query) if len(w) > 2][:6]
        if not words:
            return []
        cond = " OR ".join("text LIKE ?" for _ in words)
        params = tuple(f"%{w}%" for w in words) + (depth,)
        rows = cur.execute(f"SELECT node_id FROM mem WHERE {cond} LIMIT ?", params).fetchall()
        return [r[0] for r in rows]

    def _vector(self, query: str, depth: int) -> list[str]:
        if len(self._vec) == 0:
            return []
        qv = self._embed([query])
        if not qv:
            return []
        # Dense retrieval always returns top_k; floor out near-orthogonal noise so
        # a weak cosine can't inject an unrelated node into the fused bundle.
        return [nid for nid, cos in self._vec.search(qv[0], top_k=depth) if cos >= VECTOR_MIN_COS]

    def _rows_for(self, node_ids: Iterable[str]) -> dict[str, _Row]:
        ids = list(dict.fromkeys(node_ids))
        if not ids:
            return {}
        out: dict[str, _Row] = {}
        cur = self._con.cursor()
        # chunk the IN() to stay well under SQLite's variable limit
        for i in range(0, len(ids), 400):
            chunk = ids[i:i + 400]
            ph = ",".join("?" for _ in chunk)
            for r in cur.execute(
                f"SELECT node_id, source_kind, ts, title, text, text_hash "
                f"FROM mem WHERE node_id IN ({ph})", chunk
            ):
                out[r[0]] = _Row(*r)
        return out

    def recall(self, query: str, *, k: int = 8, depth: int = ARM_DEPTH) -> list[RecallResult]:
        """Fused recall over own memory. Returns up to ``k`` provenance-tagged
        results, best first. Empty query or empty index → ``[]``."""
        query = (query or "").strip()
        if not query:
            return []

        lex = self._lexical(query, depth)
        vec = self._vector(query, depth)
        graph = self._graph_expand(list(dict.fromkeys([*lex, *vec])), limit=depth)

        rankings: dict[str, list[str]] = {}
        if lex:   rankings["lexical"] = lex
        if vec:   rankings["vector"] = vec
        if graph: rankings["graph"] = graph
        if not rankings:
            return []
        arms_for: dict[str, set[str]] = {}
        for arm, ids in rankings.items():
            for nid in ids:
                arms_for.setdefault(nid, set()).add(arm)

        fused = _rrf(rankings)
        deleted = self._deleted_set()
        linked = self._linked_nodes()
        rows = self._rows_for(fused.keys())
        now = time.time()

        scored: list[RecallResult] = []
        for nid, base in fused.items():
            if nid in deleted or nid not in rows:
                continue
            row = rows[nid]
            score = base * _recency_boost(row.ts, now)
            if nid in linked:
                score *= (1.0 + LINK_BOOST)
            scored.append(RecallResult(
                node_id=nid, source_kind=row.source_kind, ts=row.ts,
                title=row.title, text=row.text, score=score,
                arms=tuple(sorted(arms_for.get(nid, ()))),
            ))
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:k]

    # ── introspection / lifecycle ───────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        cur = self._con.cursor()
        total = cur.execute("SELECT COUNT(*) FROM mem").fetchone()[0]
        by_kind = dict(cur.execute("SELECT source_kind, COUNT(*) FROM mem GROUP BY source_kind"))
        embedded = cur.execute("SELECT COUNT(*) FROM mem WHERE embed_dim>0").fetchone()[0]
        deleted = cur.execute("SELECT COUNT(*) FROM mem_deleted").fetchone()[0]
        return {"nodes": total, "embedded": embedded, "deleted": deleted,
                "vectors": len(self._vec), "by_kind": by_kind, "fts5": self._fts5}

    def close(self) -> None:
        self._con.close()


def format_recall(results: list[RecallResult], *, max_chars: int = 1800,
                  per_item: int = 360) -> str:
    """Render a recall bundle for injection into the model's turn context.

    Provenance-tagged so the model knows this is its OWN memory (notes / past
    chats / observations), distinct from web sources. Budget-bounded: oldest-ranked
    items drop first once ``max_chars`` is reached."""
    if not results:
        return ""
    lines = ["[RECALLED MEMORY — from your own notes, past chats, and observations]"]
    used = 0
    for r in results:
        snippet = " ".join((r.text or "").split())
        if len(snippet) > per_item:
            snippet = snippet[:per_item].rstrip() + "…"
        entry = f"- ({r.source_kind}) {snippet}"
        if used + len(entry) > max_chars:
            break
        lines.append(entry)
        used += len(entry)
    return "\n".join(lines)
