# Plan Coverage Audit

This document checks whether the agreed LAWRENCE v0.1 plan has been transcribed into implementation artifacts and identifies blindspots, failure modes, and alternatives.

## Coverage Summary

Legend:
- `Implemented`: code/docs present and runnable.
- `Scaffolded`: interfaces and module boundaries exist, but behavior is stubbed.
- `Missing`: not yet implemented in code.

| Plan Area | Status | Evidence |
|---|---|---|
| Single kernel with parallel facets | Implemented | `services/kernel/lawrence_kernel/orchestrator.py`, `facets.py` |
| Frozen context snapshot per turn | Implemented | `TurnContextSnapshot` model + `ContextFabric.create_snapshot` |
| Fast + slow loop parallel execution | Implemented (baseline) | `run_fast_reasoning_facet`, `run_slow_reasoning_facet` launched together |
| Merge arbitration immediate + deferred | Implemented (baseline) | `merge.py` |
| Markdown canonical durable memory | Implemented (baseline) | `memory.py` writing frontmatter + body |
| Distill transient context to durable notes | Implemented (baseline) | `write_distillation` |
| Retrieval from memory for relevance | Implemented (simple) | `retrieval.py` lexical scoring |
| Local-first provider modularity | Implemented (baseline) | `llm_gateway.py` HTTP-capable adapters + provider order/endpoints/models |
| Provider fallback and capabilities routing | Implemented (baseline) | local-first selection + adapter fallback behavior |
| Tool proposal branch | Implemented | `tools.py`, tool facet |
| MCP connector | Scaffolded | module boundary docs only |
| n8n connector | Implemented (baseline) | `n8n_client.py` + 8 n8n workflow JSONs |
| Web retrieval parallel branch | Implemented (n8n-backed with fallback) | `web.py`, web facet |
| Privacy/policy gate | Implemented (baseline) | `policy.py`, policy state injection |
| Human confirmation requirement | Scaffolded | represented in policy flags/tool proposals; no executor yet |
| Alter-ego/main-ego split | Scaffolded concept | slow/final separation represented, no explicit policy modules yet |
| Audio primary interaction | Scaffolded | desktop UI exists; no live STT pipeline wired |
| Expressive TTS optional mode | Scaffolded | style hints in `speech.py`; no TTS engine integration |
| Screen/audio hooks and context watcher | Missing runtime wiring | Rust hooks are placeholders |
| Hybrid retrieval (vector+BM25+graph+recency) | Partially Implemented | lexical + lightweight cosine + graph neighborhood; BM25/ANN missing |
| Context-version stale result dropping | Implemented | orchestrator filters results by `context_version` |
| Packaging + setup defaults | Scaffolded | Tauri + config files present, no release pipeline |

## Nuance and Complexity Coverage

### Parallel Semantics
- Covered: facets run concurrently; system does not wait for one stage to finish before others.
- Gap: no backpressure/queue management yet for high-frequency triggers.

### Local-First With Replaceable Backends
- Covered: provider gateway abstraction prevents provider-specific branching in orchestration.
- Gap: real adapter clients, retries, circuit breakers, and cloud redaction path are not complete.

### Memory-First Assistant Behavior
- Covered: durable Markdown notes are written each turn, retrieval feeds reasoning.
- Gap: no robust zettel link scoring and no graph index yet.

### Operational Safety
- Covered: policy flags and action confirmation intent modeled in contract.
- Gap: no actual tool execution sandbox + user confirmation UX loop yet.

### Emotion/Prosody Scope
- Covered: prosody descriptor and TTS style hinting included as baseline.
- Gap: no STT prosody extraction from real audio frames yet.

## Blindspots Identified

1. Write amplification risk in note distillation at high event frequency.
- Mitigation: introduce batching and note coalescing windows.

2. Retrieval drift from noisy logs.
- Mitigation: distillation quality score + periodic note compaction.

3. Parallel branch overload on modest hardware.
- Mitigation: facet priority scheduler and adaptive timeout budgeting.

4. Provider fragmentation across local/cloud protocols.
- Mitigation: strict adapter conformance test suite and capability registry.

5. Policy ambiguity for always-on web branch.
- Mitigation: explicit policy precedence table (user toggle > privacy mode > per-turn override).

## Failure Alternatives (Fallback Paths)

- If local model is unavailable:
  - fallback to alternate local adapter in order,
  - then optional cloud adapter if policy allows.
- If web retrieval fails:
  - continue with local memory/context-only answer + deferred retry note.
- If journaling write fails:
  - enqueue distillation record to local spool file and retry.
- If slow loop fails/timeouts:
  - keep fast-loop output and attach failure metadata to log.
- If tool execution is blocked:
  - return proposal-only mode with rationale and manual steps.

## Recommendation

The plan is **transcribed at architecture and contract level**, with a runnable baseline kernel. It is **not yet fully realized** at integration depth. Next implementation focus should be Week 2-5 delivery items: real hooks, real providers, real retrieval stack, and concrete connector integrations.
