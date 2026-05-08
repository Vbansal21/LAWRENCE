# LAWRENCE

Local Agentic Watcher Reasoning on Edge Node Contextualizing Engine.

LAWRENCE is a local-first assistant framework built around a **single kernel with parallel internal facets**. It prioritizes responsive interaction, durable Markdown memory, policy-aware tooling, and replaceable model backends.

## Current Status

- Repository is bootstrapped and runnable.
- Parallel-facet kernel baseline is implemented.
- Memory distillation to Markdown is implemented.
- Zettelkasten note operations are implemented (create/search/tag filter/link suggestion/multi-hop graph).
- Desktop shell and system hooks are scaffolded.
- Provider/tool/web integrations are wired through replaceable interfaces.
- n8n CE showcase workflows (9) are initialized for llama.cpp-first orchestration with LM Studio fallback.

Detailed status: [docs/IMPLEMENTATION_STATUS.md](/home/user/LAWRENCE/docs/IMPLEMENTATION_STATUS.md)

## Core Runtime Model

For each turn (query, trigger phrase, hotkey, or meaningful context event):

1. Kernel creates a frozen `TurnContextSnapshot`.
2. Kernel dispatches facets concurrently: context, memory, journaling, web, tools, fast reasoning, slow reasoning.
3. Merge layer emits immediate output and optional deferred refinement.
4. Distillation writes durable Markdown notes to `memory/vault`.

Architecture details: [docs/ARCHITECTURE.md](/home/user/LAWRENCE/docs/ARCHITECTURE.md)

## Why This Scaffolding Exists

The structure is intentionally modular so each subsystem can evolve independently without breaking others:

- **API-first core** enables future clients (mobile/smart devices) without rewriting logic.
- **Contracts-first design** keeps adapters interchangeable (LM Studio, llama.cpp, Gemini, OpenAI-compatible, later vLLM).
- **Markdown-first memory** keeps durable storage transparent, portable, and inspectable.
- **Connector boundaries** isolate external integration volatility (MCP/n8n/tools/APIs).
- **Workflow/config separation** keeps orchestration and policy editable without deep code edits.

## Repository Scaffold

```text
LAWRENCE/
  apps/
    desktop/                    # Tauri + React shell (overlay/UI surface)
  crates/
    system-hooks/               # Rust boundary for screen/audio/hotkey/window hooks
  services/
    kernel/                     # FastAPI assistant kernel (implemented baseline)
    context-fabric/             # Context fabric boundary docs
    memory/                     # Memory service boundary docs
    retrieval/                  # Retrieval service boundary docs
    llm-gateway/                # Provider gateway boundary docs
    speech/                     # Speech/STT/TTS boundary docs
    tools/                      # Tool orchestration boundary docs
    web/                        # Web retrieval boundary docs
    policy/                     # Policy/privacy boundary docs
    obs/                        # Observability boundary docs
  modules/
    connectors/
      mcp/                      # MCP connector module boundary
      n8n/                      # n8n connector module boundary
  memory/
    vault/                      # Canonical durable markdown zettel/journal/log store
  workflows/
    default_turn.yaml           # Parallel turn workflow definition
  config/
    default.yaml                # Runtime policy/routing defaults
  data/
    analaytics/
      HMM-dynamic-user-interaction-adaptation/
                                # Seeded analytics/docs/logs/journals/workflow records
  docs/                         # Architecture, coverage audit, runbooks, risk register
```

## Implemented Interfaces (Week 1 Contracts)

- `TurnContextSnapshot`
- `FacetResult`
- `MergeDecision`
- `ToolActionProposal`
- `DistillationRecord`
- `LLMProviderAdapter`

Contract reference: [docs/interfaces.md](/home/user/LAWRENCE/docs/interfaces.md)

## n8n Showcase and LLM Runtime

- n8n workflows: [modules/connectors/n8n/README.md](/home/user/LAWRENCE/modules/connectors/n8n/README.md)
- n8n workflow docs: [docs/N8N_WORKFLOWS.md](/home/user/LAWRENCE/docs/N8N_WORKFLOWS.md)
- n8n runtime scripts: [infra/n8n/start.sh](/home/user/LAWRENCE/infra/n8n/start.sh), [infra/n8n/docker-compose.yml](/home/user/LAWRENCE/infra/n8n/docker-compose.yml)
- llama.cpp runtime scripts: [infra/llm/start-llamacpp.sh](/home/user/LAWRENCE/infra/llm/start-llamacpp.sh), [infra/llm/status-llamacpp.sh](/home/user/LAWRENCE/infra/llm/status-llamacpp.sh)
- Kernel-to-n8n webhook alias routing is configured in [config/default.yaml](/home/user/LAWRENCE/config/default.yaml) (`integrations.workflow_paths`).
- Provider gateway supports local-first HTTP calls to:
  - `llama.cpp` (default local runtime path)
  - `LM Studio` (local fallback/alternate)
  - cloud adapters for Gemini/OpenAI-compatible endpoints (policy-gated)

## Documentation Index

- Start here for future contributors/agents: [docs/AGENT_HANDOFF.md](/home/user/LAWRENCE/docs/AGENT_HANDOFF.md)
- IEEE-style technical paper source: [docs/papers/LAWRENCE_v0_1_ieee.tex](/home/user/LAWRENCE/docs/papers/LAWRENCE_v0_1_ieee.tex)
- Changelog: [CHANGELOG.md](/home/user/LAWRENCE/CHANGELOG.md)
- Plan coverage and blindspots: [docs/PLAN_COVERAGE.md](/home/user/LAWRENCE/docs/PLAN_COVERAGE.md)
- Architecture: [docs/ARCHITECTURE.md](/home/user/LAWRENCE/docs/ARCHITECTURE.md)
- Implementation status: [docs/IMPLEMENTATION_STATUS.md](/home/user/LAWRENCE/docs/IMPLEMENTATION_STATUS.md)
- Schemas: [docs/SCHEMAS.md](/home/user/LAWRENCE/docs/SCHEMAS.md)
- Risk register: [docs/RISK_REGISTER.md](/home/user/LAWRENCE/docs/RISK_REGISTER.md)
- Operations runbook: [docs/OPERATIONS.md](/home/user/LAWRENCE/docs/OPERATIONS.md)
- n8n workflows: [docs/N8N_WORKFLOWS.md](/home/user/LAWRENCE/docs/N8N_WORKFLOWS.md)

## Quick Start (Kernel)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn lawrence_kernel.main:app --reload --app-dir services/kernel
```

Health endpoint:

```bash
curl http://127.0.0.1:8000/health
```

Turn endpoint:

```bash
curl -X POST http://127.0.0.1:8000/v1/turns \
  -H "Content-Type: application/json" \
  -d '{"trigger_type":"user_query","user_query":"Summarize what I was doing","context":{"active_app":"browser"}}'
```

Memory note create endpoint:

```bash
curl -X POST http://127.0.0.1:8000/v1/memory/notes \
  -H "Content-Type: application/json" \
  -d '{"note_type":"knowledge_note","title":"llama.cpp integration","summary":"Hook n8n workflows to local llama.cpp","tags":["llamacpp","n8n"],"entities":["lawrence"],"source_refs":["manual"]}'
```

Memory search endpoint:

```bash
curl "http://127.0.0.1:8000/v1/memory/search?query=llama.cpp%20n8n&tags=n8n&top_k=5"
```

## Quick Start (WSL: n8n Visual Editor + Qwen llama.cpp)

1. Start local Qwen runtime:

```bash
bash infra/llm/start-llamacpp.sh
```

2. Start n8n and import workflows:

```bash
bash infra/n8n/start.sh
```

3. Run the kernel API:

```bash
source .venv/bin/activate
uvicorn lawrence_kernel.main:app --reload --app-dir services/kernel --host 127.0.0.1 --port 8000
```

4. Open visual node editor:
- WSL side: `http://127.0.0.1:5678`
- Windows host side: `http://localhost:5678`

Useful status checks:

```bash
bash infra/llm/status-llamacpp.sh
bash infra/n8n/status.sh
```

## Policy and Privacy Defaults

- Telemetry disabled by default.
- Cloud usage disabled by default.
- Action confirmation required by default.
- Raw capture intended to be transient; distilled memory persists.

## License

This repository currently carries a non-commercial licensing intent via PolyForm Noncommercial reference. See [LICENSE](/home/user/LAWRENCE/LICENSE).
