from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from time import perf_counter

from lawrence_kernel.config import RuntimeConfig, load_config
from lawrence_kernel.context_fabric import ContextFabric
from lawrence_kernel.facets import (
    run_context_facet,
    run_fast_reasoning_facet,
    run_journaling_facet,
    run_memory_facet,
    run_slow_reasoning_facet,
    run_tool_facet,
    run_web_facet,
)
from lawrence_kernel.llm_gateway import LLMGateway
from lawrence_kernel.memory import MarkdownMemoryStore
from lawrence_kernel.merge import merge_facet_results
from lawrence_kernel.models import FacetResult, FacetType, TurnInput, TurnResponse
from lawrence_kernel.n8n_client import N8NClient
from lawrence_kernel.policy import PolicyEngine
from lawrence_kernel.retrieval import RetrievalService
from lawrence_kernel.speech import SpeechService
from lawrence_kernel.tools import ToolService
from lawrence_kernel.web import WebRetrievalService


class AssistantKernel:
    def __init__(self, config_path: Path | None = None) -> None:
        self.config: RuntimeConfig = load_config(config_path)
        self.context_fabric = ContextFabric()
        self.policy = PolicyEngine(self.config.policy, self.config.routing)
        self.memory = MarkdownMemoryStore(self.config.retention)
        self.retrieval = RetrievalService(self.memory)

        self.llm = LLMGateway(
            provider_order=self.config.providers.order,
            local_first=self.config.providers.local_first,
            endpoints=self.config.providers.endpoints,
            models=self.config.providers.models,
            timeout_seconds=self.config.providers.timeout_seconds,
        )
        self.n8n = N8NClient(
            base_url=self.config.integrations.n8n_base_url,
            webhook_path=self.config.integrations.n8n_webhook_path,
            timeout_seconds=4.0,
            workflow_paths=self.config.integrations.workflow_paths,
        )
        self.tools = ToolService(self.n8n)
        self.speech = SpeechService()
        self.web = WebRetrievalService(self.n8n, max_results=self.config.web.max_results)

    async def handle_turn(self, turn: TurnInput) -> TurnResponse:
        snapshot = self.context_fabric.create_snapshot(turn)
        decision = self.policy.evaluate_turn(turn, snapshot)

        facets: list[tuple[str, Callable[[], Awaitable[FacetResult]]]] = [
            ("context", lambda: run_context_facet(snapshot)),
            ("memory", lambda: run_memory_facet(snapshot, self.retrieval)),
            ("journaling", lambda: run_journaling_facet(snapshot)),
            ("web", lambda: run_web_facet(snapshot, self.web, enabled=decision.allow_web)),
            ("tools", lambda: run_tool_facet(snapshot, self.tools, enabled=decision.allow_tools)),
            ("fast_reasoning", lambda: run_fast_reasoning_facet(snapshot, self.llm, self.speech)),
            ("slow_reasoning", lambda: run_slow_reasoning_facet(snapshot, self.llm)),
        ]

        tasks = [self._run_facet(name, fn) for name, fn in facets]
        facet_results = await asyncio.gather(*tasks)

        valid_results = [r for r in facet_results if r.context_version == snapshot.context_version]

        merge_decision = merge_facet_results(snapshot, valid_results)
        distillation_record = self.memory.write_distillation(snapshot, valid_results)

        return TurnResponse(
            snapshot=snapshot,
            merge_decision=merge_decision,
            facet_results=valid_results,
            distillation_records=[distillation_record],
        )

    async def _run_facet(self, name: str, fn: Callable[[], Awaitable[FacetResult]]) -> FacetResult:
        timeout_ms = self.config.routing.facet_timeouts_ms.get(name, 1500)
        started = perf_counter()
        facet_type = FacetType(name)
        try:
            result = await asyncio.wait_for(fn(), timeout=timeout_ms / 1000)
            return result
        except TimeoutError:
            elapsed = int((perf_counter() - started) * 1000)
            return FacetResult(
                turn_id="timeout",
                facet_type=facet_type,
                confidence=0.0,
                latency_ms=elapsed,
                payload={"summary": f"facet `{name}` timed out"},
                context_version=0,
            )
        except Exception as exc:  # pragma: no cover
            elapsed = int((perf_counter() - started) * 1000)
            return FacetResult(
                turn_id="error",
                facet_type=facet_type,
                confidence=0.0,
                latency_ms=elapsed,
                payload={"summary": f"facet `{name}` error", "error": str(exc)},
                context_version=0,
            )
