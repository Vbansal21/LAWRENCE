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

## Distillation Principle

Raw context is transient. Durable storage is distilled and structured.

## Retrieval Bundle (Target)

Will include:
- lexical hits
- vector hits
- recency boosts
- link-neighborhood expansions
- provenance markers for each evidence item
