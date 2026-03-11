from __future__ import annotations

from lawrence_kernel.memory import MarkdownMemoryStore
from lawrence_kernel.models import TurnContextSnapshot


class RetrievalService:
    def __init__(self, memory_store: MarkdownMemoryStore) -> None:
        self._memory = memory_store

    def recall(self, snapshot: TurnContextSnapshot, top_k: int = 5) -> list[dict[str, str]]:
        query = (snapshot.user_query or "").strip()
        hits = self._memory.zettel.search(query=query, tags=None, top_k=top_k)
        out: list[dict[str, str]] = []

        for hit in hits:
            related = self._memory.zettel.multi_hop_neighbors(hit["note_id"], max_hops=2, max_nodes=8)
            out.append(
                {
                    "path": hit["path"],
                    "score": str(hit["score"]),
                    "preview": f"{hit['title']} | tags={','.join(hit.get('tags', []))}",
                    "note_id": hit["note_id"],
                    "related_count": str(max(0, len(related) - 1)),
                }
            )
        return out
