---
id: note-20260310-zettel-linking
type: implementation_note
created_at: 2026-03-10T22:47:00Z
updated_at: 2026-03-10T22:47:00Z
tags: [zettelkasten, retrieval, links]
links: [note-20260310-kernel-bootstrap, impl-observation-20260310]
source_refs: [services/kernel/lawrence_kernel/zettelkasten.py, services/kernel/lawrence_kernel/retrieval.py]
---

## Observation

Zettel linking now includes both direct suggestions and multi-hop traversal, enabling "multi-click away" discovery of related notes.

## Impact

The memory facet can return richer context than plain lexical snippets, improving delayed reasoning and journaling quality.

## Action

Upgrade retrieval with ANN/BM25 for larger vaults and keep graph expansion bounded by hop and node limits.
