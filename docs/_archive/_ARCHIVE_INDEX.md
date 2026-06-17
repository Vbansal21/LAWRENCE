# docs/_archive/ — staged for removal (NOT deleted yet)

> Created 2026-06-17 during the "for real" doc consolidation. These 14 files were
> the drifted/overlapping planning + conception lineage. Their still-valuable content
> has been consolidated into the **canonical living set** in `docs/`:
>
> - **`docs/papers/LAWRENCE_v0_1_ieee.{tex,pdf}`** — the **SOUL** (project idea/concept;
>   defines the watcher-assistant, the parallel-facet kernel, the formal **Retrieval
>   Bundle** `B_t` / `S_ret = β_ℓL+β_vV+β_gG+β_rR+β_hH−β_pP` that grounds the N-02 rework).
> - **`docs/DONE.md`** — constraint surface (D-01..D-19).
> - **`docs/PLAN.md`** — possibility space (N-01..N-30) + the embedded BUILD→AUDIT→REVISE.
> - **`docs/CLI.md`** — live operational command reference.
>
> Each file here carries an `⌫ ARCHIVED` banner at its top with its original location,
> what it was, and what-of-it-survives-and-where. **Do not treat these as current.**
> Removal is deferred to the user — kept until the consolidation is confirmed stable
> and any last extractions (e.g. relocating the I1–I9 invariants + Anthropic appendix
> out of `IMPLEMENTATION_PLAN.md`) are done.

## Index (origin → what survives → where)

| Archived file | Was | Survives → where |
|---|---|---|
| `AUTONOMY.md` | living autonomy plan (WS-*, §9/§10, FR map) | ALL → DONE.md + PLAN.md; litmus → paper |
| `NEXT_WORK_CHECKLIST.md` | near-term prioritized checklist §1–15 | ALL → DONE.md + PLAN.md (its prose was the split's source) |
| `IMPLEMENTATION_PLAN.md` | foundation plan P0–P9/V3 + **I1–I9** + Anthropic appendix | invariants I1–I9 (still cited); open tasks → PLAN; ⚠ **relocate I1–I9 + Anthropic appendix before deletion** |
| `AUDIT.md` | is-it-real scan; "Retrieval: BM25+FTS5" | regression evidence → PLAN N-02; HOLLOW/DEAD → DONE assumptions |
| `ARCHITECTURE.md` | `memory` facet "recalls notes"; audio primary/vision secondary | → paper (SOUL) + PLAN N-02/N-06 |
| `SCHEMAS.md` | "Retrieval Bundle (Target)" + note frontmatter | → paper §Retrieval-Bundle + PLAN N-02 (north star) |
| `interfaces.md` | `TurnContextSnapshot`, `embed()` | → PLAN N-01 (embed) / N-06 (snapshot) |
| `PLAN_COVERAGE.md` | hybrid-retrieval "BM25/ANN missing" | regression evidence → PLAN N-02 |
| `IMPLEMENTATION_STATUS.md` | "lexical+lightweight cosine; ANN/BM25 pending" | regression evidence → PLAN N-02 |
| `AGENT_HANDOFF.md` | project shape + "BM25/ANN/graph" next-work | → paper + PLAN N-02; stale doc-order dropped |
| `RISK_REGISTER.md` | risks R1–R10 | R2/R6/R8/R10 → PLAN N-02/N-05/N-07 self-align; R4 → N-25 |
| `OPERATIONS.md` | dead FastAPI/n8n runbook | nothing live → CLI.md/README |
| `N8N_WORKFLOWS.md` | dead n8n showcase | nothing live → paper §Workflow/Tool + PLAN N-25 |
| `COMMIT_HANDOFF.md` | one-time 2026-06-13 commit steps | obsolete (rule lives in .gitignore) |

**One open extraction before these can be deleted:** the **I1–I9 invariant wording**
and **Appendix A (Anthropic backend facts)** currently live only in
`IMPLEMENTATION_PLAN.md`. Relocate them (e.g. into a short `docs/INVARIANTS.md` or into
DONE.md's preamble) before removal. Tracked as a note in PLAN.md N-29 (doc reconcile).
