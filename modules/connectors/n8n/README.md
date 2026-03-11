# n8n Community Edition Workflows (LAWRENCE)

This module initializes a concrete n8n CE showcase aligned with the LAWRENCE plan.

## Workflow Set (9 total)

0. `wf-00-agentic-kernel-loop.json`
- Primary agentic workflow.
- Runs kernel turn, extracts tool proposal, optionally executes tool, responds with merged outcome.

1. `wf-01-turn-intake-parallel.json`
- Entry workflow for user turns.
- Fan-out pattern for web retrieval + memory enrichment + provider call.

2. `wf-02-web-search.json`
- Web retrieval webhook workflow consumed by kernel web facet/tool calls.

3. `wf-03-zettel-ingest-link.json`
- Distillation ingestion into zettel format, auto-tag and link candidate pass.

4. `wf-04-zettel-search-graph.json`
- Query zettel notes, tag filter, and multi-hop neighbor expansion.

5. `wf-05-llamacpp-fast-slow.json`
- LLM generation workflow using llama.cpp endpoint first.

6. `wf-06-lmstudio-fallback.json`
- LM Studio fallback when llama.cpp path is unavailable.

7. `wf-07-tool-approval-gate.json`
- Human-confirmation gate for medium/high-risk tool proposals.

8. `wf-08-daily-journal-synthesis.json`
- Scheduled journal synthesis from context logs and top linked notes.

## Import Steps

1. Start n8n CE locally.
2. In n8n UI, import JSON workflows from `workflows/`.
3. Set environment vars in n8n:
- `LAWRENCE_KERNEL_BASE=http://127.0.0.1:8000`
- `LLAMACPP_BASE=http://127.0.0.1:8080`
- `LMSTUDIO_BASE=http://127.0.0.1:1234`
- `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`
4. Activate the workflows.

## One-command local start

```bash
bash infra/n8n/start.sh
```

Behavior:
- `N8N_RUNTIME=auto` (default) picks Docker if available, otherwise local CLI mode (WSL-friendly).
- Imports all workflows from `modules/connectors/n8n/workflows`.
- Auto-activates core workflows used by the kernel:
  - `wf-00-agentic-kernel-loop`
  - `wf-02-web-search`
  - `wf-03-zettel-ingest-link`
  - `wf-05-llamacpp-fast-slow`

Visual editor URL:
- `http://127.0.0.1:5678` (inside WSL)
- `http://localhost:5678` (from Windows host, if WSL localhost forwarding is enabled)

Status/stop:

```bash
bash infra/n8n/status.sh
bash infra/n8n/stop.sh
```

## Webhook Routing Used By Kernel

n8n CE v2 registers production paths with workflow/node prefixes. LAWRENCE maps those paths in:
- `config/default.yaml` -> `integrations.workflow_paths`

Current mapped aliases:
- `web-search` -> `/webhook/wf-02-web-search/webhook%2520web%2520search/lawrence/web-search`
- `zettel-ingest` -> `/webhook/wf-03-zettel-ingest-link/webhook%2520zettel%2520ingest/lawrence/zettel-ingest`

Kernel client reference: `services/kernel/lawrence_kernel/n8n_client.py`.
