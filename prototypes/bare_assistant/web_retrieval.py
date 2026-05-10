from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request


def search_web(query: str, limit: int = 3) -> list[dict[str, str]]:
    if not query.strip():
        return []

    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    request = urllib.request.Request(url, headers={"User-Agent": "LAWRENCE-bare-assistant/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            body = response.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return [{"title": "web unavailable", "url": "local://web-error", "snippet": str(exc)}]

    hits: list[dict[str, str]] = []
    blocks = re.findall(r'<a rel="nofollow" class="result__a" href="(.*?)">(.*?)</a>.*?<a class="result__snippet".*?>(.*?)</a>', body, re.S)
    for raw_url, raw_title, raw_snippet in blocks[:limit]:
        hits.append(
            {
                "title": _clean(raw_title),
                "url": _decode_duckduckgo_url(html.unescape(raw_url)),
                "snippet": _clean(raw_snippet),
            }
        )
    return hits


def _clean(value: str) -> str:
    value = re.sub(r"<.*?>", "", value)
    return html.unescape(value).strip()


def _decode_duckduckgo_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    query = urllib.parse.parse_qs(parsed.query)
    if "uddg" in query and query["uddg"]:
        return query["uddg"][0]
    return value
