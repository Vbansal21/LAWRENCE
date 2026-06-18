"""Dense-vector index — the vector arm of hybrid retrieval (N-01).

Exact cosine search over a packed, L2-normalised float32 matrix. numpy
accelerates the per-query scan when it is installed; a pure-Python fallback keeps
the core path stdlib-only (invariant I4) so the index still works on a bare
install. There is deliberately **no ANN dependency** (faiss/hnswlib): at
personal scale (n ≤ ~10^5 vectors of dim d) an exact O(n·d) scan is sub-
millisecond to low-millisecond, and dodges a heavy native dep until n forces it.

Vectors are normalised on insert, so cosine similarity is a plain dot product.
Persistence is stdlib (`array('f')` for the matrix + JSON for ids/dim), so an
index written with numpy installed loads fine on a numpy-less host and vice
versa.

This is a standalone primitive: N-02 (hybrid retrieval) fuses its rankings with
the FTS5 lexical arm and the NoteStore graph arm via Reciprocal Rank Fusion.
"""
from __future__ import annotations

import json
import math
from array import array
from pathlib import Path
from typing import Iterable, Sequence

try:                       # numpy only accelerates the query; never required (I4)
    import numpy as _np
except Exception:          # pragma: no cover - exercised via the forced-fallback test
    _np = None             # type: ignore[assignment]


def _l2_normalise(vec: Sequence[float]) -> list[float]:
    """Return ``vec`` scaled to unit L2 norm (a zero vector is returned as-is)."""
    norm = math.sqrt(sum(x * x for x in vec))
    if norm <= 0.0:
        return [float(x) for x in vec]
    inv = 1.0 / norm
    return [float(x) * inv for x in vec]


class VectorIndex:
    """An ordered, id-addressable set of unit vectors with cosine top-k search.

    ``add`` is idempotent per id (re-adding replaces the vector). The dimension
    is fixed by the first vector (or by ``dim=``) and every later vector must
    match it.
    """

    def __init__(self, dim: int | None = None) -> None:
        self._dim: int | None = dim
        self._ids: list[str] = []
        self._pos: dict[str, int] = {}      # id -> row index
        self._rows: list[array] = []        # one array('f') per id (unit-normalised)
        self._matrix = None                 # cached numpy matrix; invalidated on mutation

    # ── introspection ──────────────────────────────────────────────────────────

    @property
    def dim(self) -> int | None:
        return self._dim

    @property
    def ids(self) -> list[str]:
        return list(self._ids)

    def __len__(self) -> int:
        return len(self._ids)

    def __contains__(self, id: str) -> bool:
        return id in self._pos

    # ── write ───────────────────────────────────────────────────────────────────

    def add(self, id: str, vector: Sequence[float]) -> None:
        """Insert (or replace) the unit-normalised ``vector`` under ``id``."""
        if self._dim is None:
            if not vector:
                raise ValueError("cannot infer embedding dimension from an empty vector")
            self._dim = len(vector)
        elif len(vector) != self._dim:
            raise ValueError(f"vector dim {len(vector)} != index dim {self._dim}")
        row = array("f", _l2_normalise(vector))
        if id in self._pos:
            self._rows[self._pos[id]] = row
        else:
            self._pos[id] = len(self._ids)
            self._ids.append(id)
            self._rows.append(row)
        self._matrix = None

    def add_many(self, items: Iterable[tuple[str, Sequence[float]]]) -> int:
        """Add many ``(id, vector)`` pairs; returns the count added."""
        n = 0
        for id, vec in items:
            self.add(id, vec)
            n += 1
        return n

    def remove(self, id: str) -> bool:
        """Drop ``id`` from the index. Returns True if it was present."""
        pos = self._pos.pop(id, None)
        if pos is None:
            return False
        self._ids.pop(pos)
        self._rows.pop(pos)
        for i in range(pos, len(self._ids)):   # reindex the shifted tail
            self._pos[self._ids[i]] = i
        self._matrix = None
        return True

    # ── read ────────────────────────────────────────────────────────────────────

    def _build_matrix(self):
        if self._matrix is None and _np is not None:
            if self._rows:
                self._matrix = _np.array(self._rows, dtype=_np.float32)
            else:
                self._matrix = _np.empty((0, self._dim or 0), dtype=_np.float32)
        return self._matrix

    def search(self, query: Sequence[float], top_k: int = 10) -> list[tuple[str, float]]:
        """Return up to ``top_k`` ``(id, cosine_score)`` pairs, best first.

        Scores are dot products of unit vectors, i.e. cosine in [-1, 1]. An empty
        index, an empty query, or top_k <= 0 returns ``[]``.
        """
        if not self._ids or top_k <= 0 or not query:
            return []
        if self._dim is not None and len(query) != self._dim:
            raise ValueError(f"query dim {len(query)} != index dim {self._dim}")
        q = _l2_normalise(query)

        if _np is not None:
            mat = self._build_matrix()
            scores = mat @ _np.asarray(q, dtype=_np.float32)
            k = min(top_k, scores.shape[0])
            # argpartition for the top-k, then sort just those (O(n + k log k))
            idx = _np.argpartition(-scores, k - 1)[:k]
            idx = idx[_np.argsort(-scores[idx])]
            return [(self._ids[int(i)], float(scores[int(i)])) for i in idx]

        # pure-Python fallback: exact dot product per row
        scored = [
            (self._ids[i], math.fsum(a * b for a, b in zip(row, q)))
            for i, row in enumerate(self._rows)
        ]
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored[:top_k]

    # ── persistence (stdlib; numpy-independent on disk) ──────────────────────────

    def save(self, path: str | Path) -> Path:
        """Write the index to ``<path>.json`` (meta) + ``<path>.f32`` (matrix).

        ``path`` is treated as a stem; its suffix is replaced. The float32 blob
        is row-major (len(ids) × dim) so it loads with or without numpy.
        """
        stem = Path(path).with_suffix("")
        meta = stem.with_suffix(".json")
        data = stem.with_suffix(".f32")
        meta.parent.mkdir(parents=True, exist_ok=True)
        flat = array("f")
        for row in self._rows:
            flat.extend(row)
        with open(data, "wb") as fh:
            flat.tofile(fh)
        meta.write_text(
            json.dumps({"dim": self._dim, "ids": self._ids}, ensure_ascii=False),
            encoding="utf-8",
        )
        return meta

    @classmethod
    def load(cls, path: str | Path) -> "VectorIndex":
        """Load an index previously written by :meth:`save`. A missing file
        yields an empty index (caller can lazily build it)."""
        stem = Path(path).with_suffix("")
        meta = stem.with_suffix(".json")
        data = stem.with_suffix(".f32")
        idx = cls()
        try:
            info = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return idx
        idx._dim = info.get("dim")
        ids = info.get("ids") or []
        flat = array("f")
        try:
            with open(data, "rb") as fh:
                flat.frombytes(fh.read())
        except OSError:
            return idx
        dim = idx._dim or 0
        if dim and len(flat) >= dim * len(ids):
            for i, id in enumerate(ids):
                row = flat[i * dim:(i + 1) * dim]
                idx._pos[id] = len(idx._ids)
                idx._ids.append(id)
                idx._rows.append(row)
        return idx
