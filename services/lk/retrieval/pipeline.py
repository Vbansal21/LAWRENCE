"""Retrieval pipeline — Perplexity-style.

Flow for each set of query variants:
  1. Check SemanticDB for cached content (avoid re-fetching known URLs)
  2. Run web search + fetch + extract for queries with insufficient DB hits
  3. Store new chunks in SemanticDB (persistent, cited)
  4. BM25 re-rank all candidates (DB + fresh) against all query variants
  5. Return top-K as formatted citation blocks

The caller (kernel/invoke.py) receives a list of CitedResult with:
  - citation_num: [N] for inline reference in the model's answer
  - url, title, snippet: source metadata
  - text: ranked chunk text injected into model context
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass

from .db     import SemanticDB, StoredChunk
from .ranker import rank
from .web    import WebChunk, search_and_fetch

DB_MIN_HITS  = 3    # if DB has fewer than this for a query, hit the web too
FRESH_PER_Q  = 3    # max web results to fetch per query when DB insufficient
TOP_K        = 6    # final chunks returned to the model

# §10 diversity controls
MAX_CHUNKS_PER_URL    = 3      # candidate-pool cap so one page can't crowd the corpus
RECENCY_WEIGHT        = 0.15   # mild: a just-fetched web row scores up to +15%
RECENCY_HALFLIFE_DAYS = 14.0   # boost fades to ~0 after this many days

_WS    = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]")


def _norm_chunk(text: str) -> str:
    """Normalise chunk text for near-duplicate detection: lowercase, drop
    punctuation, collapse whitespace. Two chunks differing only in casing,
    spacing, or punctuation collapse to the same key. Structured comparison on
    the text field — not a fragile substring hack."""
    return _WS.sub(" ", _PUNCT.sub(" ", text.lower())).strip()


def _is_local(url: str) -> bool:
    """Ingested local documents (``file://``) are durable, not web-stale."""
    return url.startswith("file://")


def _recency_factor(is_local: bool, ts: float, now: float, *,
                    weight: float = RECENCY_WEIGHT,
                    halflife_days: float = RECENCY_HALFLIFE_DAYS) -> float:
    """Multiplicative ranking nudge. Local ingested files are never stale (1.0,
    no decay). Web rows with a known fetch timestamp get a small boost that fades
    to 0 with age; unknown-timestamp rows are neutral. Never penalises (>= 1.0),
    so a relevant old source is nudged, not buried."""
    if is_local or ts <= 0:
        return 1.0
    age_days = max(0.0, (now - ts) / 86400.0)
    fresh01 = max(0.0, 1.0 - age_days / halflife_days)
    return 1.0 + weight * fresh01


@dataclass
class CitedResult:
    citation_num: int
    url: str
    title: str
    text: str    # the ranked chunk text
    category: str = "web"   # web | doc | notes — for the unified RetrievalEngine bundle


def _is_linkable(url: str) -> bool:
    """A citation renders as a clickable link only for real fetchable locations.
    Own-memory citations (``memory://<node_id>``) are provenance, not links."""
    return url.startswith(("http://", "https://", "file://"))


def _cat_tag(r: "CitedResult") -> str:
    """Short provenance tag for a cited item (notes→memory; doc/web as-is)."""
    return "memory" if r.category == "notes" else r.category


def _db_to_chunk(sc: StoredChunk, query: str) -> WebChunk:
    return WebChunk(url=sc.url, title=sc.title, text=sc.text, query=query)


class RetrievalPipeline:
    def __init__(self, db: SemanticDB | None = None) -> None:
        self._db = db or SemanticDB()
        # live-patchable via /set retrieval-top-k / retrieval-fresh / retrieval-db-min
        self.top_k       = TOP_K
        self.fresh_per_q = FRESH_PER_Q
        self.db_min_hits = DB_MIN_HITS
        # §10 per-URL candidate cap — an instance attr so the deep-search shallow
        # copy inherits it (deep search widens breadth but still obeys the cap).
        self.max_chunks_per_url = MAX_CHUNKS_PER_URL

    def _dedup_and_cap(
        self, cands: list[tuple[WebChunk, float, bool]],
    ) -> list[tuple[WebChunk, float, bool]]:
        """Collapse near-duplicate chunks (normalised text) and cap chunks per
        URL. Order-preserving: the first occurrence of a normalised text and the
        first ``max_chunks_per_url`` chunks of any URL survive. §10a + §10b."""
        seen_norm: set[str] = set()
        per_url: dict[str, int] = {}
        out: list[tuple[WebChunk, float, bool]] = []
        for chunk, ts, local in cands:
            key = _norm_chunk(chunk.text)
            if not key or key in seen_norm:
                continue
            if per_url.get(chunk.url, 0) >= self.max_chunks_per_url:
                continue
            seen_norm.add(key)
            per_url[chunk.url] = per_url.get(chunk.url, 0) + 1
            out.append((chunk, ts, local))
        return out

    def retrieve(self, queries: list[str], top_k: int | None = None) -> list[CitedResult]:
        """
        Run the full pipeline for a list of query variants.
        Returns top_k CitedResult objects, ranked by relevance.
        top_k defaults to self.top_k (live-patchable via /set retrieval-top-k).
        """
        if not queries:
            return []
        if top_k is None:
            top_k = self.top_k

        # candidate = (chunk, ts_fetched, is_local); DB rows first, then fresh web
        db_cands: list[tuple[WebChunk, float, bool]] = []
        hits_by_query: dict[str, int] = {}

        # 1. Check DB — collect hits and track per-query count in one pass
        for q in queries:
            db_hits = self._db.search(q, top_k=self.db_min_hits * 2)
            hits_by_query[q] = len(db_hits)
            for sc in db_hits:
                db_cands.append((_db_to_chunk(sc, q), sc.ts_fetched, _is_local(sc.url)))

        # 2. Decide what needs a web fetch — trigger for any query below the threshold,
        # not just zero-hit queries (1–2 cached hits is still "insufficient context").
        # The secondary count uses NORMALISED text so near-dup cache rows don't
        # masquerade as sufficient breadth.
        needs_web = [q for q, n in hits_by_query.items() if n < self.db_min_hits]
        if not needs_web and len({_norm_chunk(c.text) for c, _, _ in db_cands}) < self.db_min_hits:
            needs_web = queries

        web_cands: list[tuple[WebChunk, float, bool]] = []
        if needs_web:
            fresh = search_and_fetch(needs_web, max_per_query=self.fresh_per_q)
            # 3. Store new chunks
            by_url: dict[str, list[WebChunk]] = {}
            for c in fresh:
                by_url.setdefault(c.url, []).append(c)
            for url, chunks in by_url.items():
                self._db.upsert(url, chunks[0].title, [c.text for c in chunks])
            now = time.time()   # just fetched → maximally fresh
            web_cands = [(c, now, _is_local(c.url)) for c in fresh]

        # 3b. Collapse near-duplicate chunks + cap per URL BEFORE ranking (§10a/b)
        cands = self._dedup_and_cap(db_cands + web_cands)
        if not cands:
            return []

        all_chunks = [c for c, _, _ in cands]
        metas      = [(ts, local) for _, ts, local in cands]

        # 4. Re-rank, then apply a mild recency nudge (§10c)
        ranked = rank(queries, [c.text for c in all_chunks])   # [(index, score), ...]
        now = time.time()
        adjusted = sorted(
            ((i, s * _recency_factor(metas[i][1], metas[i][0], now)) for i, s in ranked),
            key=lambda x: x[1], reverse=True,
        )

        # 5. Build CitedResult list (top_k, URL-deduplicated; stable source numbers)
        results: list[CitedResult] = []
        seen_urls: set[str] = set()
        for idx, _score in adjusted:
            if len(results) >= top_k:
                break
            chunk = all_chunks[idx]
            # one citation per URL (avoid duplicating same page)
            if chunk.url in seen_urls:
                continue
            seen_urls.add(chunk.url)
            results.append(CitedResult(
                citation_num=len(results) + 1,
                url=chunk.url,
                title=chunk.title,
                text=chunk.text,
            ))

        return results


def format_snippets(results: list[CitedResult], chars: int = 150) -> str:
    """
    Preview format — title + first N chars of each chunk.
    The model sees this on the first response pass; it can request
    expand_sources:[N] to get full text on a second pass.
    """
    if not results:
        return ""
    lines = ["[RETRIEVED SOURCES — previews; use expand_sources:[N] for full text]"]
    for r in results:
        preview = r.text[:chars].rstrip()
        if len(r.text) > chars:
            preview += "…"
        label = r.title or (r.url if _is_linkable(r.url) else "(your memory)")
        lines.append(f"\n[{r.citation_num}] ({_cat_tag(r)}) {label}")
        lines.append(f"    {preview}")
    return "\n".join(lines)


def format_for_model(results: list[CitedResult]) -> str:
    """Full citation blocks for injection into the model's context."""
    if not results:
        return ""
    lines = ["[RETRIEVED SOURCES]"]
    for r in results:
        label = r.title or (r.url if _is_linkable(r.url) else "(your memory)")
        lines.append(f"\n[{r.citation_num}] ({_cat_tag(r)}) {label}")
        if _is_linkable(r.url):
            lines.append(f"    URL: {r.url}")
        lines.append(f"    {r.text}")
    return "\n".join(lines)


def format_citations(results: list[CitedResult]) -> str:
    """Short citation list for appending to the answer.

    Emitted as a Markdown section with proper ``[title](url)`` links so the MDX
    renderer in the desktop UI shows clickable sources; in a plain terminal it
    still reads cleanly as ``- [N] title (url)``.
    """
    if not results:
        return ""
    lines = ["", "---", "**Sources**", ""]
    for r in results:
        label = (r.title or r.url).replace("[", "(").replace("]", ")")
        if _is_linkable(r.url):
            lines.append(f"- [{r.citation_num}] ({_cat_tag(r)}) [{label}]({r.url})")
        else:   # own-memory provenance — no clickable link
            lines.append(f"- [{r.citation_num}] ({_cat_tag(r)}) {label}")
    return "\n".join(lines)


def evidence_assets(results: list[CitedResult], *, snippet_chars: int = 240) -> list[dict]:
    """Map a unified evidence bundle to typed asset cards (FR-008): the desktop
    bridge can push these as scrollable Perplexity-style source cards instead of
    scraping Markdown links from the answer. Card rendering is the UI's job."""
    assets: list[dict] = []
    for r in results:
        kind = {"web": "webpage", "doc": "document", "notes": "memory"}.get(r.category, r.category)
        snippet = " ".join((r.text or "").split())[:snippet_chars]
        assets.append({
            "id":       f"src-{r.citation_num}",
            "kind":     kind,
            "category": r.category,
            "title":    r.title or (r.url if _is_linkable(r.url) else "your memory"),
            "url":      r.url if _is_linkable(r.url) else "",
            "snippet":  snippet,
        })
    return assets
