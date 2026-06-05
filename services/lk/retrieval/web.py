"""Web search + full-page content extraction + chunking.

Search:  DuckDuckGo HTML endpoint (no API key, real web results)
Extract: trafilatura if installed, else HTML paragraph extraction fallback
Chunk:   ~500 char segments on sentence/word boundaries

Returns list[WebChunk] — each chunk carries its source URL, page title, and text.
"""
from __future__ import annotations

import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

CHUNK_SIZE   = 500
FETCH_TIMEOUT = 10
MAX_WORKERS   = 4
DDG_MAX       = 6   # results per query from DDG


@dataclass
class WebChunk:
    url: str
    title: str
    text: str
    query: str = ""   # which query produced this (for attribution)


# ── DDG search ────────────────────────────────────────────────────────────────

def ddg_search(query: str, max_results: int = DDG_MAX) -> list[dict[str, str]]:
    """Returns [{url, title}] — real web links, not DDG entity pages."""
    try:
        params = urllib.parse.urlencode({"q": query, "kl": "us-en"})
        url = f"https://html.duckduckgo.com/html/?{params}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
            "Accept": "text/html",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        raw_urls = re.findall(r"uddg=([^&\"]+)", html)
        titles   = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL)
        titles   = [re.sub("<[^>]+>", "", t).strip() for t in titles]

        results, seen = [], set()
        for i, raw in enumerate(raw_urls):
            u = urllib.parse.unquote(raw)
            if u in seen or not u.startswith("http"):
                continue
            seen.add(u)
            results.append({"url": u, "title": titles[i] if i < len(titles) else ""})
            if len(results) >= max_results:
                break
        return results
    except Exception:
        return []


# ── content extraction ────────────────────────────────────────────────────────

def _fetch_html(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
            "Accept": "text/html",
        })
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            raw = resp.read(512_000)   # 512KB cap
            ct = resp.headers.get("Content-Type", "")
            charset = "utf-8"
            if "charset=" in ct:
                charset = ct.split("charset=")[-1].strip().split(";")[0]
            return raw.decode(charset, errors="replace")
    except Exception:
        return ""


def _extract_trafilatura(html: str, url: str) -> str:
    try:
        import trafilatura  # type: ignore
        text = trafilatura.extract(
            html, url=url,
            include_comments=False, include_tables=True,
            no_fallback=False,
        )
        return text or ""
    except ImportError:
        return ""
    except Exception:
        return ""


def _extract_fallback(html: str) -> str:
    """Simple <p>/<article>/<section> extraction when trafilatura not available."""
    # strip script/style
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    # extract paragraphs
    paras = re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL | re.IGNORECASE)
    if not paras:
        # fall back to stripping all tags
        paras = [html]
    text = " ".join(re.sub("<[^>]+>", " ", p) for p in paras)
    # collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text[:8000]


def extract_text(html: str, url: str) -> str:
    text = _extract_trafilatura(html, url)
    if not text:
        text = _extract_fallback(html)
    return text.strip()


# ── chunking ──────────────────────────────────────────────────────────────────

def chunk_text(text: str, size: int = CHUNK_SIZE) -> list[str]:
    """Split on sentence boundaries, target ~size chars per chunk."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks, current = [], ""
    for sent in sentences:
        if not sent.strip():
            continue
        if len(current) + len(sent) > size and current:
            chunks.append(current.strip())
            current = sent
        else:
            current = (current + " " + sent).strip()
    if current:
        chunks.append(current.strip())
    return [c for c in chunks if len(c) > 60]   # drop tiny fragments


# ── fetch + extract pipeline ──────────────────────────────────────────────────

def fetch_and_chunk(result: dict[str, str], query: str) -> list[WebChunk]:
    url, title = result["url"], result["title"]
    html = _fetch_html(url)
    if not html:
        return []
    text = extract_text(html, url)
    if not text:
        return []
    return [WebChunk(url=url, title=title, text=c, query=query) for c in chunk_text(text)]


def search_and_fetch(queries: list[str], max_per_query: int = 3) -> list[WebChunk]:
    """
    Parallel DDG search for all queries, then parallel fetch+extract+chunk.
    Returns all chunks, URL-deduplicated, preserving source attribution.
    """
    seen_urls: set[str] = set()
    search_results: list[tuple[dict[str, str], str]] = []
    all_chunks: list[WebChunk] = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        # Phase 1: all DDG searches in parallel
        search_futures = {pool.submit(ddg_search, q, max_per_query): q for q in queries}
        for f in as_completed(search_futures):
            q = search_futures[f]
            try:
                for r in f.result():
                    if r["url"] not in seen_urls:
                        seen_urls.add(r["url"])
                        search_results.append((r, q))
            except Exception:
                pass

        # Phase 2: all page fetches in parallel
        fetch_futures = {pool.submit(fetch_and_chunk, r, q): (r, q) for r, q in search_results}
        for f in as_completed(fetch_futures):
            try:
                all_chunks.extend(f.result())
            except Exception:
                pass

    return all_chunks
