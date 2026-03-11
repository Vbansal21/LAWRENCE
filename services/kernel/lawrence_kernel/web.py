from __future__ import annotations

from lawrence_kernel.n8n_client import N8NClient


class WebRetrievalService:
    def __init__(self, n8n_client: N8NClient, max_results: int = 5) -> None:
        self._n8n = n8n_client
        self._max = max_results

    async def fetch(self, query: str | None) -> list[dict[str, str]]:
        if not query:
            return []

        result = await self._n8n.trigger_workflow("web-search", {"query": query, "limit": self._max})
        if result.get("ok"):
            data = result.get("data", {})
            hits = data.get("hits") if isinstance(data, dict) else None
            if isinstance(hits, list):
                return [
                    {
                        "title": str(item.get("title", "untitled")),
                        "url": str(item.get("url", "")),
                        "snippet": str(item.get("snippet", "")),
                    }
                    for item in hits[: self._max]
                ]

        # Fallback when n8n is offline or not configured.
        return [
            {
                "title": "web-search-fallback",
                "url": "local://web-search-unavailable",
                "snippet": f"n8n web workflow unavailable; query retained: {query}",
            }
        ]
