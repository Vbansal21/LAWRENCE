from __future__ import annotations

from typing import Any

from lawrence_kernel.models import ToolActionProposal
from lawrence_kernel.n8n_client import N8NClient


class ToolService:
    def __init__(self, n8n_client: N8NClient) -> None:
        self._n8n = n8n_client

    def propose_actions(self, query: str | None) -> list[ToolActionProposal]:
        if not query:
            return []

        proposals: list[ToolActionProposal] = []
        lowered = query.lower()

        if "search" in lowered or "find" in lowered or "web" in lowered:
            proposals.append(
                ToolActionProposal(
                    tool="web.search",
                    args={"query": query},
                    risk_level="low",
                    requires_confirmation=False,
                    policy_basis="query_contains_search",
                )
            )

        if "note" in lowered or "journal" in lowered or "zettel" in lowered:
            proposals.append(
                ToolActionProposal(
                    tool="memory.zettel.create",
                    args={"summary": query},
                    risk_level="low",
                    requires_confirmation=False,
                    policy_basis="knowledge_capture_intent_detected",
                )
            )

        if "run" in lowered or "execute" in lowered:
            proposals.append(
                ToolActionProposal(
                    tool="local.command",
                    args={"intent": query},
                    risk_level="medium",
                    requires_confirmation=True,
                    policy_basis="execution_intent_detected",
                )
            )

        return proposals

    async def execute_action(self, proposal: ToolActionProposal) -> dict[str, Any]:
        if proposal.tool == "web.search":
            return await self._n8n.trigger_workflow("web-search", proposal.args)
        if proposal.tool == "memory.zettel.create":
            return await self._n8n.trigger_workflow("zettel-ingest", proposal.args)
        if proposal.tool == "local.command":
            return {
                "ok": False,
                "error": "local.command execution is disabled in baseline; confirmation pipeline required",
            }
        return {"ok": False, "error": f"unsupported tool: {proposal.tool}"}
