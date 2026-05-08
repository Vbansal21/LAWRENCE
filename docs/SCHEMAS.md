# Schemas and Data Conventions

## Canonical Durable Note (Markdown + Frontmatter)

Required fields:
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

Common durable note types:
- `context_log`
- `journal_daily`
- `task_note`
- `knowledge_note`

Optional structured fields by note/facet:
- `source_refs`
- `links`
- `entities`
- `tags`
- speech/prosody descriptors when relevant

## Content Body Principle

- fixed metadata skeleton
- dynamic semantic body
- flexible note content guided by schema, note type, and facet-specific prompting

Hard-structured output is primarily intended for:
- logs
- journals
- memory writes
- retrieval/indexing
- specialized inference pipelines

Fast conversational output can remain freer.

## Distillation Principle

Raw context is transient. Durable storage is distilled and structured.

Retention intent:
- raw capture remains ephemeral by default
- distilled artifacts persist in Markdown
- short-lived transient buffers may exist for journaling/refinement/restart-safe continuity

## Retrieval Bundle (Target)

Will include:
- lexical hits
- vector hits
- recency boosts
- link-neighborhood expansions
- provenance markers for each evidence item
- recent-thread context
- current-context distillations
- relevant journal fragments
- optional web findings when the web branch is active

## Temporal / Contextual Metadata Intent

Current-context schemas are intended to be able to reference:
- active app / active window
- time/date
- thread continuity
- reminder/calendar-derived context
- latest chat references
- stale-context / changed-context signals
