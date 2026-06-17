> **⌫ ARCHIVED 2026-06-17 — staged for removal, NOT deleted.** Original: `docs/RISK_REGISTER.md`.
> **What it was:** conception risk register R1–R10.
> **What survives & where:** R2 retrieval-irrelevance / R6 web-overuse / R8 memory-graph-drift / R10 slow-loop-recursion → `docs/PLAN.md` self-alignment checks (N-02 / N-05 / N-07); R4 tool-policy → N-25.
> **Status:** conception risks folded into the relevant PLAN nodes' self-alignment lists.

# Risk Register

## R1: Parallel Facet Resource Saturation
- Probability: Medium
- Impact: High
- Mitigation: adaptive facet budget scheduler, per-facet queue limits.

## R2: Retrieval Irrelevance
- Probability: Medium
- Impact: High
- Mitigation: quality-scored distillation + periodic note compaction.

## R3: Provider API Drift
- Probability: High
- Impact: Medium
- Mitigation: provider contract tests and compatibility matrix.

## R4: Policy Gaps During Tool Execution
- Probability: Medium
- Impact: High
- Mitigation: confirmation gate middleware before any execution path.

## R5: Over-scope on Emotion Features
- Probability: Medium
- Impact: Medium
- Mitigation: keep prosody hints optional until core reliability is stable.

## R6: Web Retrieval Overuse
- Probability: Medium
- Impact: Medium
- Mitigation: keep web retrieval policy-gated, confidence-weighted, and configurable even when the current implementation path defaults it on.

## R7: Multimodal Capture Too Heavy for Modest Hardware
- Probability: Medium
- Impact: High
- Mitigation: low-resolution change detection, selective higher-resolution capture, and aggressive transient distillation.

## R8: Memory Graph Drift Over Time
- Probability: Medium
- Impact: High
- Mitigation: periodic re-linking, confidence re-scoring, stale-note consolidation, and distillation quality thresholds.

## R9: Backend / Adapter Sprawl
- Probability: Medium
- Impact: Medium
- Mitigation: certify a narrow local-first adapter set first and keep all others behind strict contracts.

## R10: Slow-Loop Recursion Explosion
- Probability: Medium
- Impact: High
- Mitigation: strict limits on candidate count, branch count, depth, and total latency budget.
