> **CONCEPTUAL REFERENCE ONLY.** Describes the target design, not the running code. The FastAPI/n8n implementation it references was replaced by `services/lk/`. For current implementation truth see `README.md` and `docs/IMPLEMENTATION_PLAN.md`.

# LAWRENCE Interface Contracts

## TurnContextSnapshot

- turn_id
- ts
- trigger_type
- user_query
- screen_ref
- audio_ref
- thread_ref
- app_ref
- time_ref
- reminder_ref
- latest_chat_refs
- policy_state
- context_version

Current implementation note:
- snapshot fields already preserve the richer current-context shape from the planning spec
- not all providers are live yet (`reminder_ref`, `latest_chat_refs`, richer thread/calendar sources)

## FacetResult

- turn_id
- facet_type
- confidence
- latency_ms
- payload_ref
- citations
- actions
- context_version

Evidence model intent:
- each facet contributes its own evidence stream
- merge consumes facet outputs without forcing a sequential stage order

## MergeDecision

- turn_id
- immediate_response
- deferred_allowed
- overlay_updates
- followups
- structured_outputs

## LLMProviderAdapter

Current baseline:
- `health()`
- `capabilities()`
- `generate(prompt, mode)`

Target extension from planning scope:
- `stream(...)`
- `embed(...)`
- `list_models()`
- `normalize_error(...)`

The repo currently implements the minimum subset needed for the chosen v0.1 path and leaves the rest as planned adapter-surface growth.

## ToolActionProposal

- `tool`
- `args`
- `risk_level`
- `requires_confirmation`
- `policy_basis`

## DistillationRecord

- `source_ref`
- `distilled_into`
- `retention_policy`
- `expires_at`

## Zettel Frontmatter Contract

Required durable metadata:
- `id`
- `type`
- `created_at`
- `updated_at`
- `entities`
- `tags`
- `links`
- `source_refs`
- `confidence`
- `privacy_level`

## Zettel/Memory API

### POST /v1/memory/notes

Request fields:
- note_type
- title
- summary
- tags[]
- entities[]
- source_refs[]
- links[]
- confidence
- privacy_level

Response:
- note_id
- path

### GET /v1/memory/search

Query params:
- query
- tags (comma separated)
- top_k

Response:
- query
- tags[]
- results[] with note_id/path/score/tags/title/links

### GET /v1/memory/graph/{note_id}

Query params:
- max_hops

Response:
- note_id
- max_hops
- nodes[] (note graph neighborhood)
