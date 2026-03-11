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
