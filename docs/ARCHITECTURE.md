# LAWRENCE Architecture (Current + Target)

## Current Runtime Topology

- Desktop shell (Tauri + React) calls kernel HTTP API.
- Kernel creates a frozen turn snapshot and dispatches parallel facets.
- Facet outputs are merged into immediate/deferred responses.
- Distillation writes canonical Markdown notes under `memory/vault`.

## Assistant Kernel Facets

- `context`: derives current context summary from trigger + metadata.
- `memory`: recalls prior notes.
- `journaling`: prepares distillation signal.
- `web`: external evidence branch (currently stubbed).
- `tools`: proposes agentic actions.
- `fast_reasoning`: low-latency response path.
- `slow_reasoning`: deeper delayed refinement path.

## Contracts-First Design

Core objects are intentionally stable:
- `TurnContextSnapshot`
- `FacetResult`
- `MergeDecision`
- `ToolActionProposal`
- `DistillationRecord`

These contracts are the anti-coupling boundary across modules.

## Why This Scaffolding Structure

- `apps/` isolates user-facing clients from kernel internals.
- `services/` isolates stateful backend concerns into swappable domains.
- `modules/connectors/` isolates external integration churn.
- `memory/vault` enforces Markdown as canonical durable memory.
- `workflows/` carries orchestration intent separate from code.
- `config/` externalizes policy/routing decisions.

This allows staged hardening without rewiring the entire system.
