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

## FacetResult

- turn_id
- facet_type
- confidence
- latency_ms
- payload_ref
- citations
- actions
- context_version

## MergeDecision

- turn_id
- immediate_response
- deferred_allowed
- overlay_updates
- followups
- structured_outputs

## LLMProviderAdapter

- health()
- capabilities()
- generate(prompt, mode)

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
