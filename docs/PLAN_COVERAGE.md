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
| Desktop-first Tauri baseline, API-first for later clients | Implemented (scaffold + docs) | `apps/desktop/`, root README, architecture docs |
| Tool proposal branch | Implemented | `tools.py`, tool facet |
| MCP connector | Scaffolded | module boundary docs only |
| n8n connector | Implemented (baseline) | `n8n_client.py` + 9 n8n workflow JSONs |
| Web retrieval parallel branch | Implemented (n8n-backed with fallback) | `web.py`, web facet |
| Web retrieval default-on policy | Implemented (baseline) | `config/default.yaml` `routing.web_parallel_default: true` |
| Privacy/policy gate | Implemented (baseline) | `policy.py`, policy state injection |
| Human confirmation requirement | Scaffolded | represented in policy flags/tool proposals; no executor yet |
| Alter-ego/main-ego split | Scaffolded concept | slow/final separation represented, no dedicated alter-ego formatter module yet |
| Audio + text as primary interaction surfaces | Scaffolded | desktop/UI/speech modules exist; no live STT/TTS pipeline wired |
| Visual/screen context as secondary watcher input | Scaffolded | snapshot fields + system-hook boundary present; no live watcher runtime yet |
| Expressive TTS optional mode | Scaffolded | style hints in `speech.py`; no TTS engine integration |
| Screen/audio hooks and watcher loop | Missing runtime wiring | Rust hooks are placeholders |
| Current context fields for reminders/latest chats/time/thread state | Partially Implemented | snapshot contract contains fields; providers not yet wired |
| Hybrid retrieval (vector+BM25+graph+recency) | Partially Implemented | lexical + lightweight cosine + graph neighborhood; BM25/ANN missing |
| Zettelkasten linking and multi-hop traversal | Implemented (baseline) | `zettelkasten.py` + graph endpoints |
| Recommendation layer as distinct subsystem | Missing | not yet separated beyond merge/tool/web outputs |
| Context-version stale result dropping | Implemented | orchestrator filters results by `context_version` |
| Slow-loop critique/refine recursion with bounded depth | Scaffolded concept | only baseline slow pass exists today |
| Modest edge hardware degradation path | Partially Implemented | timeouts/fallbacks/token limits present; no adaptive scheduler yet |
| Packaging + setup defaults | Scaffolded | Tauri + config files present, no release pipeline |

## Nuance and Complexity Coverage

### Parallel Semantics
- Covered: facets run concurrently; system does not wait for one stage to finish before others.
- Gap: no backpressure/queue management yet for high-frequency triggers.

### Surface Priority
- Covered: audio/text primacy and screen-as-context are preserved in the documented contracts and module boundaries.
- Gap: runtime behavior is still more text-centric than audio-centric because STT/TTS/capture wiring is not complete.

### Local-First With Replaceable Backends
- Covered: provider gateway abstraction prevents provider-specific branching in orchestration.
- Gap: real adapter clients, retries, circuit breakers, vLLM adapter, and cloud redaction path are not complete.

### Memory-First Assistant Behavior
- Covered: durable Markdown notes are written each turn, retrieval feeds reasoning.
- Gap: no robust zettel link scoring and no graph index yet.

### Scope Resolution From Chat
- Covered: desktop-first current platform, API-first future clients, local-first model routing, and Markdown-first memory are all captured.
- Covered: web retrieval is treated as a parallel evidence branch and is enabled by default in baseline config.
- Covered: expressive voice remains optional and reduced to prosody/style hints at v0.1 scope.
- Gap: recommendation system remains implicit rather than a separately modeled subsystem.
- Gap: reminder/calendar/latest-thread providers are part of the snapshot contract but not yet implemented as live sources.

### Deliberate Implementation-Path Deltas
- Older grounding spec: web retrieval should be conditional rather than always-on by default.
- Current chosen path: default-on web branch in baseline config, but still treated as a parallel evidence branch and intended to remain policy/user configurable.
- Older grounding spec: web/PWA-first where feasible, with native fallback.
- Current chosen path: desktop-first Tauri baseline now, while preserving API-first boundaries for future clients.
- Older grounding spec: provider/runtime list was broader at planning time.
- Current chosen path: concrete v0.1 baseline prioritizes `llama.cpp`, LM Studio, n8n, and generic cloud-compatible adapters before broader backend expansion.

### Operational Safety
- Covered: policy flags and action confirmation intent modeled in contract.
- Gap: no actual tool execution sandbox + user confirmation UX loop yet.

### Emotion/Prosody Scope
- Covered: prosody descriptor and TTS style hinting included as baseline.
- Gap: no STT prosody extraction from real audio frames yet.

### Slow Loop Ambition vs Current Baseline
- Covered: immediate + deferred response split exists and the slow loop is structurally separate.
- Gap: candidate generation, critique/merge trees, and bounded recursion depth are not yet implemented beyond a single slow pass.

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

6. Drift between documented scope and current implementation depth.
- Mitigation: keep this coverage audit updated whenever scope decisions are made in planning conversations.

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

## Completeness Judgment

The transcribed plan is now **substantially complete at the scope-and-nuance level** for this chat:
- parallel internal facets rather than sequential stages
- local-first modular backends
- Markdown/Zettelkasten canonical memory
- desktop-first now, API-first later
- audio/text primacy with visual watcher support
- privacy-aware web/tool/cloud gating
- fast-loop immediacy with slow-loop refinement

What is still incomplete is **implementation depth**, not plan transcription:
- live audio/screen watcher runtime
- recommendation subsystem separation
- reminder/calendar/latest-chat providers
- bounded recursive slow-loop refinement
- production-grade tool confirmation UX and hardening

## Recommendation

The plan is **transcribed at architecture and contract level**, with a runnable baseline kernel. It is **not yet fully realized** at integration depth. Next implementation focus should be Week 2-5 delivery items: real hooks, real providers, real retrieval stack, and concrete connector integrations.
