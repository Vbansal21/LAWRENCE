# n8n Community Edition Workflow Showcase

Primary files: `modules/connectors/n8n/workflows/*.json`

## Workflow inventory

1. `wf-01-turn-intake-parallel.json`
2. `wf-00-agentic-kernel-loop.json`
3. `wf-02-web-search.json`
4. `wf-03-zettel-ingest-link.json`
5. `wf-04-zettel-search-graph.json`
6. `wf-05-llamacpp-fast-slow.json`
7. `wf-06-lmstudio-fallback.json`
8. `wf-07-tool-approval-gate.json`
9. `wf-08-daily-journal-synthesis.json`

## Why these 9

They map to the project plan facets and provide an end-to-end showcase:
- direct agentic kernel loop,
- parallel intake,
- web branch,
- zettel capture/search/link,
- local LLM first (llama.cpp),
- fallback (LM Studio),
- safe tool approval,
- periodic journaling.

## Runtime expectations

- n8n CE running at `http://127.0.0.1:5678`
- LAWRENCE kernel at `http://127.0.0.1:8000`
- llama.cpp server at `http://127.0.0.1:8080`
- LM Studio API at `http://127.0.0.1:1234`

## Required n8n env vars

- `LAWRENCE_KERNEL_BASE`
- `LLAMACPP_BASE`
- `LMSTUDIO_BASE`
- `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`

## Quick run

```bash
bash infra/n8n/start.sh
```

Core workflows auto-activated by `infra/n8n/start.sh`:
- `wf-00-agentic-kernel-loop`
- `wf-02-web-search`
- `wf-03-zettel-ingest-link`
- `wf-05-llamacpp-fast-slow`

Kernel webhook alias mapping is configured in `config/default.yaml` under `integrations.workflow_paths`.
