from __future__ import annotations

import asyncio
import time

from lawrence_kernel.llm_gateway import LLMGateway
from lawrence_kernel.models import FacetResult, FacetType, TurnContextSnapshot
from lawrence_kernel.retrieval import RetrievalService
from lawrence_kernel.speech import SpeechService
from lawrence_kernel.tools import ToolService
from lawrence_kernel.web import WebRetrievalService


async def run_context_facet(snapshot: TurnContextSnapshot) -> FacetResult:
    start = time.perf_counter()
    await asyncio.sleep(0)
    summary = f"app={snapshot.app_ref or 'unknown'} trigger={snapshot.trigger_type}"
    return FacetResult(
        turn_id=snapshot.turn_id,
        facet_type=FacetType.context,
        confidence=0.8,
        latency_ms=_latency_ms(start),
        payload={"summary": summary, "entities": [snapshot.app_ref] if snapshot.app_ref else []},
        context_version=snapshot.context_version,
    )


async def run_memory_facet(snapshot: TurnContextSnapshot, retrieval: RetrievalService) -> FacetResult:
    start = time.perf_counter()
    hits = retrieval.recall(snapshot)
    return FacetResult(
        turn_id=snapshot.turn_id,
        facet_type=FacetType.memory,
        confidence=0.65 if hits else 0.2,
        latency_ms=_latency_ms(start),
        payload={"summary": f"{len(hits)} memory hits", "hits": hits},
        citations=[h["path"] for h in hits],
        context_version=snapshot.context_version,
    )


async def run_journaling_facet(snapshot: TurnContextSnapshot) -> FacetResult:
    start = time.perf_counter()
    await asyncio.sleep(0)
    summary = f"Ready to distill turn {snapshot.turn_id}"
    return FacetResult(
        turn_id=snapshot.turn_id,
        facet_type=FacetType.journaling,
        confidence=0.9,
        latency_ms=_latency_ms(start),
        payload={"summary": summary},
        context_version=snapshot.context_version,
    )


async def run_web_facet(snapshot: TurnContextSnapshot, web: WebRetrievalService, enabled: bool) -> FacetResult:
    start = time.perf_counter()
    hits = await web.fetch(snapshot.user_query) if enabled else []
    summary = "web disabled" if not enabled else f"{len(hits)} web hits"
    return FacetResult(
        turn_id=snapshot.turn_id,
        facet_type=FacetType.web,
        confidence=0.45 if hits else 0.1,
        latency_ms=_latency_ms(start),
        payload={"summary": summary, "hits": hits},
        citations=[h.get("url", "") for h in hits],
        context_version=snapshot.context_version,
    )


async def run_tool_facet(snapshot: TurnContextSnapshot, tools: ToolService, enabled: bool) -> FacetResult:
    start = time.perf_counter()
    actions = tools.propose_actions(snapshot.user_query) if enabled else []
    summary = f"{len(actions)} tool proposals"
    return FacetResult(
        turn_id=snapshot.turn_id,
        facet_type=FacetType.tools,
        confidence=0.6 if actions else 0.2,
        latency_ms=_latency_ms(start),
        payload={"summary": summary},
        actions=actions,
        context_version=snapshot.context_version,
    )


async def run_fast_reasoning_facet(snapshot: TurnContextSnapshot, llm: LLMGateway, speech: SpeechService) -> FacetResult:
    start = time.perf_counter()
    prompt = snapshot.user_query or "Provide a concise context-aware update."
    try:
        # Keep fast facet responsive even if local generation is slow on CPU-only hosts.
        response = await asyncio.wait_for(llm.fast_generate(prompt), timeout=2.0)
    except Exception:
        response = f"[fast-fallback] {prompt}"
    prosody = speech.describe_prosody(snapshot.user_query)
    tts_style = speech.tts_style(prosody)
    return FacetResult(
        turn_id=snapshot.turn_id,
        facet_type=FacetType.fast_reasoning,
        confidence=0.75,
        latency_ms=_latency_ms(start),
        payload={
            "summary": "fast reasoning complete",
            "response": response,
            "prosody": prosody,
            "tts_style": tts_style,
        },
        context_version=snapshot.context_version,
    )


async def run_slow_reasoning_facet(snapshot: TurnContextSnapshot, llm: LLMGateway) -> FacetResult:
    start = time.perf_counter()
    prompt = (
        "Perform a deeper refinement of this request with structured critique: "
        + (snapshot.user_query or "No explicit user query.")
    )
    response = await llm.slow_generate(prompt)
    return FacetResult(
        turn_id=snapshot.turn_id,
        facet_type=FacetType.slow_reasoning,
        confidence=0.7,
        latency_ms=_latency_ms(start),
        payload={"summary": "slow reasoning complete", "response": response},
        context_version=snapshot.context_version,
    )


def _latency_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)
