from __future__ import annotations

from lawrence_kernel.models import FacetResult, FacetType, MergeDecision, TurnContextSnapshot


def merge_facet_results(snapshot: TurnContextSnapshot, results: list[FacetResult]) -> MergeDecision:
    fast = _first(results, FacetType.fast_reasoning)
    slow = _first(results, FacetType.slow_reasoning)
    memory = _first(results, FacetType.memory)
    web = _first(results, FacetType.web)

    immediate = "No fast response available."
    if fast:
        immediate = fast.payload.get("response", immediate)

    overlay_updates: list[str] = []
    if memory:
        overlay_updates.append(f"Memory hits: {len(memory.payload.get('hits', []))}")
    if web:
        overlay_updates.append(f"Web hits: {len(web.payload.get('hits', []))}")

    followups: list[str] = []
    if slow and slow.payload.get("response"):
        followups.append("Slow refinement is available for review.")

    return MergeDecision(
        turn_id=snapshot.turn_id,
        immediate_response=immediate,
        deferred_allowed=True,
        deferred_response=(slow.payload.get("response") if slow else None),
        overlay_updates=overlay_updates,
        followups=followups,
        structured_outputs={"context_version": snapshot.context_version},
    )


def _first(results: list[FacetResult], facet_type: FacetType) -> FacetResult | None:
    for result in results:
        if result.facet_type == facet_type:
            return result
    return None
