> **CONCEPTUAL REFERENCE ONLY.** Describes the target design, not the running code. The FastAPI/n8n implementation it references was replaced by `services/lk/`. For current implementation truth see `README.md` and `docs/IMPLEMENTATION_PLAN.md`.

# Operations Runbook

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn lawrence_kernel.main:app --reload --app-dir services/kernel
```

## Health Check

```bash
curl http://127.0.0.1:8000/health
```

## Turn Check

```bash
curl -X POST http://127.0.0.1:8000/v1/turns \
  -H "Content-Type: application/json" \
  -d '{"trigger_type":"user_query","user_query":"What should I do next?","context":{"active_app":"editor"}}'
```

## Testing

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q
```

## n8n CE Setup (Showcase)

WSL/local command path:

```bash
bash infra/n8n/start.sh
bash infra/n8n/status.sh
```

`start.sh` imports all workflow JSON files and auto-activates:
- `wf-00-agentic-kernel-loop`
- `wf-02-web-search`
- `wf-03-zettel-ingest-link`
- `wf-05-llamacpp-fast-slow`

It also sets `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` by default so workflow expressions can use env-backed base URLs.

Visual editor:
- WSL: `http://127.0.0.1:5678`
- Windows host: `http://localhost:5678` (with localhost forwarding enabled)

Stop:

```bash
bash infra/n8n/stop.sh
```

## llama.cpp Setup (Qwen 3.5 4B Q4_0 baseline)

Start/stop/status:

```bash
bash infra/llm/start-llamacpp.sh
bash infra/llm/status-llamacpp.sh
bash infra/llm/stop-llamacpp.sh
```

Default model path:
- `models/Qwen3.5-4B-Q4_0.gguf`

## LLM Runtime Endpoints

- llama.cpp expected at `http://127.0.0.1:8080`
- LM Studio expected at `http://127.0.0.1:1234`
- Provider config lives in `config/default.yaml`

## Failure Handling (Current)

- Facet timeout: result returns timeout payload; merge proceeds.
- Facet exception: result returns error payload; merge proceeds.
- Distillation write failure: currently not retried (needs spool queue).

## Security/Privacy Defaults

- Telemetry disabled.
- Cloud disabled by default.
- Action confirmation required by policy.
