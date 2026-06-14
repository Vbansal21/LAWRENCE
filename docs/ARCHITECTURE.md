> **CONCEPTUAL REFERENCE ONLY.** Describes the target design, not the running code. The FastAPI/n8n implementation it references was replaced by `services/lk/`. For current implementation truth see `README.md` and `docs/IMPLEMENTATION_PLAN.md`.

# LAWRENCE Architecture (Current + Target)

## Current Runtime Topology

- Desktop shell (Tauri + React) is the current primary host surface and calls the kernel HTTP API.
- Kernel creates a frozen turn snapshot and dispatches parallel facets.
- Facet outputs are merged into immediate/deferred responses.
- Distillation writes canonical Markdown notes under `memory/vault`.
- API-first boundaries are retained so later mobile/smart-device clients can attach without rewriting the kernel.

## Interaction Priority

- Audio and text are the primary interaction surfaces.
- Visual/screen capture is secondary and is intended to contextualize the user environment rather than replace conversational I/O.
- Current-context inputs are intended to include screen, audio, active app, prior thread, time, reminders/calendar, and latest chat state when providers are available.

## Assistant Kernel Facets

- `context`: derives current context summary from trigger + metadata.
- `memory`: recalls prior notes.
- `journaling`: prepares distillation signal.
- `web`: external evidence branch (currently stubbed).
- `tools`: proposes agentic actions.
- `fast_reasoning`: low-latency response path.
- `slow_reasoning`: deeper delayed refinement path.

These facets are intended to run in parallel, not as a strict capture -> retrieve -> think -> log pipeline.

## Cognition Split

- `alter-ego`: internal structuring/refinement/critique logic, primarily associated with the slow reasoning path.
- `main ego`: user-facing phrasing/style/polish layer, primarily associated with surfaced responses.

The current implementation only expresses this split structurally. Dedicated formatting/policy layers for each side are not yet separated into explicit modules.

## Contracts-First Design

Core objects are intentionally stable:
- `TurnContextSnapshot`
- `FacetResult`
- `MergeDecision`
- `ToolActionProposal`
- `DistillationRecord`

These contracts are the anti-coupling boundary across modules.

## Local-First Runtime Strategy

- Local inference is the default path.
- Provider adapters are intended to remain swappable across `llama.cpp`, LM Studio, OpenAI-compatible backends, Gemini, and later vLLM.
- Web retrieval is treated as a parallel evidence branch and is enabled by default in baseline config, but remains policy-gated.
- Raw capture is intended to be transient; durable memory remains Markdown-first.

Implementation-path note:
- the older grounding spec leaned more conditional on web retrieval and more web/PWA-first on platform surface
- the current repository intentionally takes a desktop-first Tauri + n8n + `llama.cpp` path while keeping the same modular boundaries

## Why This Scaffolding Structure

- `apps/` isolates user-facing clients from kernel internals.
- `services/` isolates stateful backend concerns into swappable domains.
- `modules/connectors/` isolates external integration churn.
- `memory/vault` enforces Markdown as canonical durable memory.
- `workflows/` carries orchestration intent separate from code.
- `config/` externalizes policy/routing decisions.

This allows staged hardening without rewiring the entire system.
