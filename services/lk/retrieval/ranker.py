"""Full BM25 scoring (TF-IDF with document-length normalization) for re-ranking
retrieved chunks against queries.

No external dependencies. Implements the standard BM25 formula:
  score(q, d) = Σ IDF(t) * TF_norm(t, d)

where:
  IDF(t)      = log((N - df + 0.5) / (df + 0.5) + 1)       (Robertson-Sparck Jones)
  TF_norm(t)  = (f * (K1+1)) / (f + K1 * (1 - B + B * dl/avgdl))
"""
from __future__ import annotations

import math
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


def bm25_score(
    query_terms: list[str],
    doc_terms: list[str],
    avg_dl: float,
    idf: dict[str, float],
) -> float:
    tf = Counter(doc_terms)
    dl = len(doc_terms) or 1
    score = 0.0
    for term in query_terms:
        if term in tf:
            f = tf[term]
            tf_norm = (f * (K1 + 1)) / (f + K1 * (1 - B + B * dl / avg_dl))
            score += idf.get(term, 0.0) * tf_norm
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
    term_sets   = [set(t) for t in tokenized]
    avg_dl      = _avg_doc_len(tokenized)
    n           = len(tokenized)

    # Precompute IDF for each query term over the candidate corpus
    idf: dict[str, float] = {}
    for term in query_terms:
        df = sum(1 for s in term_sets if term in s)
        idf[term] = math.log((n - df + 0.5) / (df + 0.5) + 1)

    scored = [
        (i, bm25_score(query_terms, tokenized[i], avg_dl, idf))
        for i in range(len(chunks))
    ]
    return sorted(scored, key=lambda x: x[1], reverse=True)
