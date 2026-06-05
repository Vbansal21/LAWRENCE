"""BM25-lite scoring for re-ranking retrieved chunks against queries.

No external dependencies. Uses term frequency with document-length normalization.
Given a set of queries (different phrasings of the same information need) and a
list of text chunks, returns the chunks sorted by relevance descending.
"""
from __future__ import annotations

import re
from collections import Counter

_STOP = frozenset({
    "the", "a", "an", "is", "to", "of", "in", "and", "or", "for", "with",
    "on", "at", "it", "be", "are", "was", "this", "that", "as", "but",
    "have", "had", "not", "by", "from", "been", "its", "we", "you", "they",
    "he", "she", "which", "who", "how", "what", "when", "where", "will",
    "can", "would", "could", "should", "may", "might", "also", "than",
})

K1 = 1.5   # BM25 term saturation
B  = 0.75  # BM25 length normalization


def _tokenize(text: str) -> list[str]:
    return [w for w in re.findall(r"\b[a-z]{3,}\b", text.lower()) if w not in _STOP]


def _avg_doc_len(docs: list[list[str]]) -> float:
    if not docs:
        return 1.0
    return sum(len(d) for d in docs) / len(docs)


def bm25_score(query_terms: list[str], doc_terms: list[str], avg_dl: float) -> float:
    tf = Counter(doc_terms)
    dl = len(doc_terms) or 1
    score = 0.0
    for term in query_terms:
        if term in tf:
            f = tf[term]
            score += (f * (K1 + 1)) / (f + K1 * (1 - B + B * dl / avg_dl))
    return score


def rank(queries: list[str], chunks: list[str]) -> list[tuple[int, float]]:
    """
    Return list of (chunk_index, score) sorted by score descending.
    queries: multiple phrasings of the same need — terms are unioned.
    """
    if not chunks or not queries:
        return [(i, 0.0) for i in range(len(chunks))]

    query_terms = list({t for q in queries for t in _tokenize(q)})
    tokenized   = [_tokenize(c) for c in chunks]
    avg_dl      = _avg_doc_len(tokenized)

    scored = [
        (i, bm25_score(query_terms, tokenized[i], avg_dl))
        for i in range(len(chunks))
    ]
    return sorted(scored, key=lambda x: x[1], reverse=True)
