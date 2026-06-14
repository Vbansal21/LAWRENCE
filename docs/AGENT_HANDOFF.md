> **CONCEPTUAL REFERENCE ONLY.** Describes the target design, not the running code. The FastAPI/n8n implementation it references was replaced by `services/lk/`. For current implementation truth see `README.md` and `docs/IMPLEMENTATION_PLAN.md`.

# Agent Handoff

This document is the shortest correct starting point for another agent continuing work on LAWRENCE.

## What LAWRENCE Is

LAWRENCE is a local-first assistant framework built around one assistant kernel with multiple parallel internal facets.

Non-negotiable project shape:
- one kernel, not multiple competing agent runtimes
- parallel evidence branches, not a sequential capture -> retrieve -> think -> log pipeline
- Markdown/Zettelkasten is the canonical durable memory store
- local-first inference and storage
- audio + text are primary interaction surfaces
- screen/visual capture is secondary and mainly for context
- fast loop gives immediate usefulness
- slow loop refines on the same turn later

## Current Chosen Implementation Path

The repo does not implement every possible architecture from the planning phase. It implements one practical v0.1 path:

- desktop-first host surface: `Tauri + React`
- API-first kernel boundary for later mobile/smart-device clients
- Python `FastAPI` kernel
- `llama.cpp` as the primary local LLM runtime
- `LM Studio` as a local alternate/fallback path
- `n8n CE` as the current workflow/tool/web showcase layer
- Markdown vault as durable memory

This is intentional. Do not "correct" it back to a more abstract web-first architecture unless there is a concrete product reason.

## Source Of Truth Order

When continuing work, read in this order:

1. [README.md](/home/user/LAWRENCE/README.md)
2. [docs/ARCHITECTURE.md](/home/user/LAWRENCE/docs/ARCHITECTURE.md)
3. [docs/PLAN_COVERAGE.md](/home/user/LAWRENCE/docs/PLAN_COVERAGE.md)
4. [docs/IMPLEMENTATION_STATUS.md](/home/user/LAWRENCE/docs/IMPLEMENTATION_STATUS.md)
5. [docs/interfaces.md](/home/user/LAWRENCE/docs/interfaces.md)
6. [docs/SCHEMAS.md](/home/user/LAWRENCE/docs/SCHEMAS.md)
7. [docs/OPERATIONS.md](/home/user/LAWRENCE/docs/OPERATIONS.md)
8. [docs/N8N_WORKFLOWS.md](/home/user/LAWRENCE/docs/N8N_WORKFLOWS.md)
9. [docs/RISK_REGISTER.md](/home/user/LAWRENCE/docs/RISK_REGISTER.md)

If two docs appear to conflict:
- prefer the current implementation docs over older planning assumptions
- prefer explicit implementation-path delta notes over inferred intent

## Important Scope Decisions Already Resolved

These points were debated and are intentionally resolved:

- web retrieval:
  - original grounding leaned conditional-only
  - current repo path uses default-on parallel web retrieval in baseline config
  - it still remains policy-gated and should stay configurable
- platform surface:
  - original grounding leaned more PWA/web-first
  - current repo is desktop-first for v0.1 because system integration matters more than purity
- cognition split:
  - alter-ego = internal structure/refinement/critique
  - main ego = final surfaced style/polish
  - not a visible two-persona product
- emotional voice:
  - prosody-aware adaptation is in scope
  - advanced emotional modeling is not a v0.1 blocker
- memory:
  - SQL/vector stores may exist as auxiliary indexes
  - Markdown is still the durable source of truth

## What Works Now

Baseline working path:
- FastAPI kernel runs
- turn endpoint runs
- parallel facets dispatch
- fast + slow responses merge into immediate/deferred outputs
- Markdown note writing works
- zettel search/tagging/link suggestion/multi-hop traversal works at a baseline level
- local provider gateway works with HTTP-style adapters
- n8n workflows exist and can be imported/activated
- `llama.cpp` runtime path works with the current WSL setup

## What Is Only Scaffolded

Do not mistake these for complete subsystems:

- real microphone/screen/hotkey watcher runtime
- real STT/TTS pipeline
- full MCP execution transport
- recommendation system as its own service
- bounded recursive slow-loop critique/refine tree
- strong provider retries/backoff/circuit breakers
- production-grade tool confirmation UX and actuation sandbox
- reminder/calendar/latest-chat live providers

## Current Environment Assumptions

Known-good environment during current setup:
- WSL Linux
- kernel: `127.0.0.1:8000`
- n8n: `127.0.0.1:5678`
- llama.cpp: `127.0.0.1:8080`
- LM Studio optional: `127.0.0.1:1234`
- baseline model: `models/Qwen3.5-4B-Q4_0.gguf`

Use the runbook in [docs/OPERATIONS.md](/home/user/LAWRENCE/docs/OPERATIONS.md) rather than inventing new startup commands first.

## Architectural Invariants

These should remain stable unless there is a deliberate redesign:

- `TurnContextSnapshot`, `FacetResult`, `MergeDecision`, `ToolActionProposal`, and `DistillationRecord` are anti-coupling contracts
- facet outputs should be mergeable without provider-specific logic in orchestration
- durable notes must keep stable frontmatter fields
- transient raw capture should expire; distilled notes persist
- tool execution must stay behind policy/confirmation boundaries
- context versioning must remain the stale-result guard

## How To Evaluate A Proposed Change

A change is probably correct if it improves one of these without violating the invariants:
- fast-loop responsiveness
- retrieval relevance
- Markdown memory quality
- replaceability of providers/connectors
- privacy/policy clarity
- ability to run on modest local hardware

A change is probably wrong if it:
- hardcodes provider-specific behavior into core orchestration
- moves durable memory away from Markdown as source of truth
- turns parallel facets into a serial pipeline
- assumes cloud dependence by default
- adds emotional or recommendation complexity before core capture/retrieval quality

## Highest-Value Next Work

If continuing implementation, the best next steps are:

1. real capture/runtime wiring for screen/audio/hotkeys
2. stronger retrieval stack: BM25/ANN/graph rescoring
3. policy-confirmed tool execution loop
4. real STT/TTS integration
5. slow-loop bounded critique/refine pass
6. recommendation subsystem only after the above are stable

## Common Misreads To Avoid

- LAWRENCE is not "just a chatbot with memory".
- n8n is not the assistant brain; it is one workflow/tool/web integration layer.
- the current web branch being default-on does not mean web is the primary source of truth.
- slow loop is not required before first response.
- recommendation output is part of the product direction, but not yet a distinct implemented service.

## Handoff Judgment

Another agent can continue productively from the repo now, but only if it treats:
- the docs above as the grounding set
- the current codebase as one practical v0.1 implementation path
- the missing pieces as implementation gaps, not unresolved product intent
