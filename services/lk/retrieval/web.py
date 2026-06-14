"""Web search + full-page content extraction + chunking.

Search:  provider chain — DDG html → DDG lite → SearXNG (if configured) →
         Brave (if API key). DDG bot-blocks bursts with HTTP 202 "anomaly"
         pages (diagnosed 2026-06-12), so searches are paced ≥1s apart and a
         blocked provider sits out a 5-minute cooldown while the chain falls
         through to the next one. Failures are COUNTED (search_stats()), never
         silently swallowed into an empty result list without trace.
Extract: trafilatura if installed, else HTML paragraph extraction fallback
Chunk:   ~500 char segments on sentence/word boundaries

Returns list[WebChunk] — each chunk carries its source URL, page title, and text.

Optional providers via environment:
  LK_SEARXNG_URL    base URL of a SearXNG instance with JSON output enabled
  LK_BRAVE_API_KEY  Brave Search API subscription token
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

CHUNK_SIZE   = 500
FETCH_TIMEOUT = 10
MAX_WORKERS   = 4
DDG_MAX       = 6   # results per query from DDG

_UA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Accept": "text/html",
}

_BLOCK_COOLDOWN_SECS = 300    # a bot-blocked provider sits out this long
_SEARCH_MIN_INTERVAL = 1.0    # pacing between any two DDG-family searches


@dataclass
class WebChunk:
    url: str
    title: str
    text: str
    query: str = ""   # which query produced this (for attribution)


# ── provider chain state ──────────────────────────────────────────────────────

class _BotBlocked(Exception):
    """Provider returned a captcha/anomaly page instead of results."""


_stats_lock = threading.Lock()
_stats: dict[str, dict[str, int]] = {}      # provider → {"ok","fail","blocked"}
_cooldown_until: dict[str, float] = {}      # provider → monotonic deadline
_last_error: list[str] = [""]

_pace_lock = threading.Lock()
_last_search_ts = [0.0]


def search_stats() -> dict[str, object]:
    """Per-provider counters + last error — surfaced in /health (G5: retrieval
    must fail loudly, not silently)."""
    with _stats_lock:
        return {
            "providers": {k: dict(v) for k, v in _stats.items()},
            "cooling_down": sorted(
                k for k, t in _cooldown_until.items() if t > time.monotonic()
            ),
            "last_error": _last_error[0],
        }


def _bump(provider: str, key: str) -> None:
    with _stats_lock:
        _stats.setdefault(provider, {"ok": 0, "fail": 0, "blocked": 0})[key] += 1


def _pace() -> None:
    """Keep ≥_SEARCH_MIN_INTERVAL between DDG searches — parallel query bursts
    are exactly what triggers the anomaly block."""
    with _pace_lock:
        wait = _last_search_ts[0] + _SEARCH_MIN_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_search_ts[0] = time.monotonic()


def _http_get(url: str, headers: dict[str, str] | None = None, timeout: int = 15) -> tuple[int, str]:
    req = urllib.request.Request(url, headers=headers or _UA_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def _check_block(status: int, html: str) -> None:
    low = html[:4000].lower()
    if status in (202, 403) or "captcha" in low or "anomal" in low or "challenge" in low:
        raise _BotBlocked(f"HTTP {status} bot-block page")


# ── providers (each returns [{url, title}]) ───────────────────────────────────

def _parse_uddg_results(html: str, title_pattern: str, max_results: int) -> list[dict[str, str]]:
    """Both DDG variants link results through uddg= redirect params."""
    raw_urls = re.findall(r"uddg=([^&\"']+)", html)
    titles   = re.findall(title_pattern, html, re.DOTALL)
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


def _search_ddg_html(query: str, max_results: int) -> list[dict[str, str]]:
    _pace()
    params = urllib.parse.urlencode({"q": query, "kl": "us-en"})
    status, html = _http_get(f"https://html.duckduckgo.com/html/?{params}")
    _check_block(status, html)
    return _parse_uddg_results(html, r'class="result__a"[^>]*>(.*?)</a>', max_results)


def _search_ddg_lite(query: str, max_results: int) -> list[dict[str, str]]:
    _pace()
    params = urllib.parse.urlencode({"q": query, "kl": "us-en"})
    status, html = _http_get(f"https://lite.duckduckgo.com/lite/?{params}")
    _check_block(status, html)
    return _parse_uddg_results(html, r"class=['\"]result-link['\"][^>]*>(.*?)</a>", max_results)


def _search_searxng(query: str, max_results: int) -> list[dict[str, str]]:
    base = os.environ.get("LK_SEARXNG_URL", "").strip().rstrip("/")
    if not base:
        raise RuntimeError("LK_SEARXNG_URL not configured")
    params = urllib.parse.urlencode({"q": query, "format": "json"})
    status, body = _http_get(f"{base}/search?{params}")
    if status != 200:
        raise RuntimeError(f"searxng HTTP {status}")
    data = json.loads(body)
    return [{"url": r.get("url", ""), "title": r.get("title", "")}
            for r in data.get("results", [])[:max_results] if r.get("url")]


def _search_brave(query: str, max_results: int) -> list[dict[str, str]]:
    key = os.environ.get("LK_BRAVE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("LK_BRAVE_API_KEY not configured")
    params = urllib.parse.urlencode({"q": query, "count": max_results})
    status, body = _http_get(
        f"https://api.search.brave.com/res/v1/web/search?{params}",
        headers={"X-Subscription-Token": key, "Accept": "application/json"},
    )
    if status != 200:
        raise RuntimeError(f"brave HTTP {status}")
    data = json.loads(body)
    return [{"url": r.get("url", ""), "title": r.get("title", "")}
            for r in (data.get("web") or {}).get("results", [])[:max_results] if r.get("url")]


_PROVIDERS: list[tuple[str, object]] = [
    ("ddg_html", _search_ddg_html),
    ("ddg_lite", _search_ddg_lite),
    ("searxng",  _search_searxng),   # only if LK_SEARXNG_URL set
    ("brave",    _search_brave),     # only if LK_BRAVE_API_KEY set
]

_warned_blocks: set[str] = set()


def ddg_search(query: str, max_results: int = DDG_MAX) -> list[dict[str, str]]:
    """Provider-chain web search (name kept for backward compatibility).
    Returns [{url, title}] from the first provider that delivers; failures are
    counted in search_stats() and bot-blocked providers cool down for 5 min."""
    now = time.monotonic()
    last_exc = ""
    for name, fn in _PROVIDERS:
        if _cooldown_until.get(name, 0.0) > now:
            continue
        try:
            results = fn(query, max_results)   # type: ignore[operator]
            if results:
                _bump(name, "ok")
                return results
            _bump(name, "fail")
            last_exc = f"{name}: 0 results"
        except _BotBlocked as e:
            _bump(name, "blocked")
            _cooldown_until[name] = time.monotonic() + _BLOCK_COOLDOWN_SECS
            last_exc = f"{name}: {e}"
            if name not in _warned_blocks:
                _warned_blocks.add(name)
                print(f"[retrieval] {name} bot-blocked — cooling down "
                      f"{_BLOCK_COOLDOWN_SECS}s, falling through", file=sys.stderr)
        except Exception as e:
            _bump(name, "fail")
            last_exc = f"{name}: {type(e).__name__}: {e}"
    if last_exc:
        _last_error[0] = last_exc
    return []


# ── content extraction ────────────────────────────────────────────────────────

def _fetch_html(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers=_UA_HEADERS)
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
    Search all queries (paced/serialized inside the provider chain — parallel
    DDG bursts trigger bot-blocks), then fetch+extract+chunk pages in parallel.
    Returns all chunks, URL-deduplicated, preserving source attribution.
    """
    seen_urls: set[str] = set()
    search_results: list[tuple[dict[str, str], str]] = []
    all_chunks: list[WebChunk] = []

    # Phase 1: searches — sequential by design (see _pace)
    for q in queries:
        try:
            for r in ddg_search(q, max_per_query):
                if r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    search_results.append((r, q))
        except Exception:
            pass

    # Phase 2: all page fetches in parallel
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        fetch_futures = {pool.submit(fetch_and_chunk, r, q): (r, q) for r, q in search_results}
        for f in as_completed(fetch_futures):
            try:
                all_chunks.extend(f.result())
            except Exception:
                pass

    return all_chunks
