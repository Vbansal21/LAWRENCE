# Changelog

All notable changes to LAWRENCE are documented in this file.

## [0.1.0-alpha.3] - 2026-03-11

### Added
- Added WSL-friendly lifecycle scripts for n8n:
  - `infra/n8n/start.sh` now supports `N8N_RUNTIME=auto|docker|local`.
  - `infra/n8n/status.sh` for health/pid checks.
  - `infra/n8n/stop.sh` now stops both docker and local-mode runs.
- Added llama.cpp lifecycle scripts:
  - `infra/llm/start-llamacpp.sh`
  - `infra/llm/status-llamacpp.sh`
  - `infra/llm/stop-llamacpp.sh`
- Added automatic core workflow activation in n8n startup:
  - `wf-00-agentic-kernel-loop`
  - `wf-02-web-search`
  - `wf-03-zettel-ingest-link`
  - `wf-05-llamacpp-fast-slow`

### Changed
- Updated n8n and operations docs for WSL-local startup and visual editor access.
- Updated root README with explicit WSL quick-start path for:
  - local llama.cpp
  - n8n workflow import/start
  - node-based editor URL
- Corrected workflow count references from 8 to 9 where applicable.
- Added kernel `n8n` webhook alias mapping (`integrations.workflow_paths`) for n8n CE v2 production URLs.
- Hardened n8n workflow JSONs for runtime compatibility:
  - explicit HTTP methods on request nodes,
  - valid JSON-body expressions,
  - stable `lastNode` behavior for `web-search` and `zettel-ingest` webhooks.
- Tuned `wf-05-llamacpp-fast-slow` token budgets for usable local latency on CPU:
  - fast branch `max_tokens=32`
  - slow branch `n_predict=64`
- Switched default provider order to `llamacpp -> lmstudio -> gemini -> openai_compatible`.
- Added fast-facet fallback path when local generation exceeds a short budget, preventing empty immediate responses.

## [0.1.0-alpha.2] - 2026-03-10

### Added
- Added Zettelkasten engine with operational features in `services/kernel/lawrence_kernel/zettelkasten.py`:
  - note create/read/update
  - hybrid search (lexical + cosine-style vector similarity)
  - tag-filtered lookup
  - automatic related-link suggestion
  - multi-hop graph traversal (`N` clicks away)
- Added memory API routes:
  - `POST /v1/memory/notes`
  - `GET /v1/memory/search`
  - `GET /v1/memory/graph/{note_id}`
- Added n8n client integration `services/kernel/lawrence_kernel/n8n_client.py`.
- Added n8n Community Edition workflow showcase (`modules/connectors/n8n/workflows`):
  - turn intake parallel fan-out
  - web-search webhook
  - zettel ingest/link
  - zettel search+graph expansion
  - llama.cpp fast/slow generation
  - LM Studio fallback generation
  - tool approval gate
  - scheduled daily journal synthesis
- Added workflow docs and import mapping for n8n.
- Added real-data seeding in analytics path for adaptation/journal/log/workflow records.
- Expanded tests to validate Zettelkasten create/search/graph behaviors.

### Changed
- `LLMGateway` moved from echo-only adapters to HTTP-capable adapters with fallback behavior.
- Provider configuration now supports per-provider endpoints/models/timeouts.
- `ToolService` now includes web/zettel-oriented tool proposals and n8n-backed execution entrypoint.
- `WebRetrievalService` now uses n8n webhook integration with fallback path.
- `MarkdownMemoryStore` now writes through Zettelkasten service and applies auto-link enrichment.
- Retrieval now uses Zettelkasten search and multi-hop neighborhood awareness.

### Verified
- Python package compiles.
- Kernel tests pass (`3 passed`).
- New memory endpoints and zettel graph behavior are covered by tests.

### Remaining Gaps
- Real screen/audio/hotkey capture runtime integration is still pending.
- Real authenticated Gemini/OpenAI-compatible cloud calls require env key wiring and policy hardening.
- Retrieval does not yet include BM25 + dedicated ANN index (currently lexical + lightweight cosine fallback).
- MCP and n8n execution still needs production-grade retry/backoff/observability.
- Slow-loop recursive critique/refine tree is still baseline-level.

## [0.1.0-alpha.1] - 2026-03-10

### Added
- Initialized repository and monorepo structure for LAWRENCE.
- Added non-commercial license placeholder based on PolyForm Noncommercial intent.
- Added root project docs and baseline configuration.
- Added Python kernel package with typed contracts and parallel facet baseline.
- Added desktop scaffold and system-hooks scaffold.

### Changed
- Reworked tests to avoid environment-specific `TestClient` hangs by invoking async routes/kernel directly.
- Hardened orchestrator facet timeout/error handling to use proper `FacetType` values.
