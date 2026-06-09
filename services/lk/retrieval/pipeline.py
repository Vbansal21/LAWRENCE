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

from dataclasses import dataclass

from .db     import SemanticDB, StoredChunk
from .ranker import rank
from .web    import WebChunk, search_and_fetch

DB_MIN_HITS  = 3    # if DB has fewer than this for a query, hit the web too
FRESH_PER_Q  = 3    # max web results to fetch per query when DB insufficient
TOP_K        = 6    # final chunks returned to the model


@dataclass
class CitedResult:
    citation_num: int
    url: str
    title: str
    text: str    # the ranked chunk text


def _db_to_chunk(sc: StoredChunk, query: str) -> WebChunk:
    return WebChunk(url=sc.url, title=sc.title, text=sc.text, query=query)


class RetrievalPipeline:
    def __init__(self, db: SemanticDB | None = None) -> None:
        self._db = db or SemanticDB()
        # live-patchable via /set retrieval-top-k / retrieval-fresh / retrieval-db-min
        self.top_k       = TOP_K
        self.fresh_per_q = FRESH_PER_Q
        self.db_min_hits = DB_MIN_HITS

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

        all_chunks: list[WebChunk] = []
        seen_texts: set[str] = set()
        hits_by_query: dict[str, int] = {}

        # 1. Check DB — collect hits and track per-query count in one pass
        for q in queries:
            db_hits = self._db.search(q, top_k=self.db_min_hits * 2)
            hits_by_query[q] = len(db_hits)
            for sc in db_hits:
                if sc.text not in seen_texts:
                    seen_texts.add(sc.text)
                    all_chunks.append(_db_to_chunk(sc, q))

        # 2. Decide what needs a web fetch — trigger for any query below the threshold,
        # not just zero-hit queries (1–2 cached hits is still "insufficient context")
        needs_web = [q for q, n in hits_by_query.items() if n < self.db_min_hits]
        if not needs_web and len(all_chunks) < self.db_min_hits:
            needs_web = queries

        if needs_web:
            fresh = search_and_fetch(needs_web, max_per_query=self.fresh_per_q)
            # 3. Store new chunks
            by_url: dict[str, list[WebChunk]] = {}
            for c in fresh:
                by_url.setdefault(c.url, []).append(c)
            for url, chunks in by_url.items():
                self._db.upsert(url, chunks[0].title, [c.text for c in chunks])
            # add to candidate pool
            for c in fresh:
                if c.text not in seen_texts:
                    seen_texts.add(c.text)
                    all_chunks.append(c)

        if not all_chunks:
            return []

        # 4. Re-rank
        texts  = [c.text for c in all_chunks]
        ranked = rank(queries, texts)   # [(index, score), ...]

        # 5. Build CitedResult list (top_k, URL-deduplicated)
        results: list[CitedResult] = []
        seen_urls: set[str] = set()
        for idx, _score in ranked:
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
        lines.append(f"\n[{r.citation_num}] {r.title or r.url}")
        lines.append(f"    {preview}")
    return "\n".join(lines)


def format_for_model(results: list[CitedResult]) -> str:
    """Full citation blocks for injection into the model's context."""
    if not results:
        return ""
    lines = ["[RETRIEVED SOURCES]"]
    for r in results:
        lines.append(f"\n[{r.citation_num}] {r.title or r.url}")
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
        lines.append(f"- [{r.citation_num}] [{label}]({r.url})")
    return "\n".join(lines)
