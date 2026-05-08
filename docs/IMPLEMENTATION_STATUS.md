# Implementation Status

## Done Now

- Runnable FastAPI kernel.
- Parallel facet dispatch.
- Merge decision output (immediate + deferred).
- Distilled Markdown memory writes.
- Zettelkasten note engine:
  - note create
  - search with tags
  - lightweight vector similarity
  - link suggestion
  - multi-hop graph traversal
- Provider gateway abstraction with HTTP-capable llama.cpp/LM Studio/cloud adapter paths and fallback behavior.
- Policy baseline and tool proposal modeling with n8n-backed execution entrypoint.
- Desktop and system hook scaffolding.
- n8n CE workflow showcase (9 workflows) for intake/web/zettel/llm/tool/journal paths.
- Tests for health + turn processing + zettel create/search/graph.

## Partially Done

- Policy engine (gating modeled, enforcement depth pending).
- Speech (prosody + style hints only).
- Retrieval (lexical + lightweight cosine; full ANN/BM25 still pending).
- Tooling/web integrations (n8n path present; production hardening pending).
- Current-context richness (reminders/latest chats/calendar/thread providers modeled in contracts, not yet live).
- Slow-loop quality path (separate slow pass exists; recursive critique/refine remains pending).

## Not Started

- Real STT/TTS pipelines.
- Real screen/audio/hotkey capture integration.
- Dedicated ANN index + BM25 retrieval stack.
- MCP transport execution.
- Recommendation system as a distinct service/module.
- Provider auth management and production retries/backoff.
- Release packaging and installers.
