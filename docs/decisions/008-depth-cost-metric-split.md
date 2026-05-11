---
id: dillylang::adr-008
description: Split the conflated 'depth' metric into depth (critical path) and cost (total LLM calls)
tags: [metrics, recipe, budget]
created: 2026-05-04
status: active
---

# 008 — Depth / Cost Metric Split

## Status

Accepted

## Context

The spec (§2) defined `depth(R)` as total LLM calls, with the parenthetical
"a `parallel` of two operators counts as 2, not 1." This conflated two
distinct measurements:

- **Structural depth** — the critical path through the pipeline (sequential
  steps). A `parallel` counts as 1 regardless of branch count.
- **Total work** — the number of LLM calls consumed. A `parallel` of two
  operators counts as 2. This is what the budget ceiling (7 calls) constrains.

The word "depth" strongly connotes sequential layering. Using it for total
work created confusion: `parallel` — whose purpose is to avoid sequential
depth — appeared to increase depth. The `efficiency = coverage / depth`
metric penalized parallelization, which is counterintuitive.

## Decision

Split into two named metrics:

| Metric | Definition | What it measures |
|---|---|---|
| `depth(R)` | Critical path length through the pipeline | Structural complexity, latency |
| `cost(R)` | Total LLM calls (parallel branches each count) | Budget consumption |

`efficiency(R)` = `coverage / cost` (unchanged semantically — the denominator
was always total LLM calls, now named correctly).

### Concrete examples

| Recipe | cost | depth | coverage | efficiency |
|---|---|---|---|---|
| `refine` (pipe → parallel(2) → synthesize) | 4 | 3 | 3 | 0.75 |
| `wide_pass` (parallel(4) → synthesize) | 5 | 2 | 4 | 0.80 |
| `clarify` (pipe → pipe) | 2 | 2 | 2 | 1.00 |

## Revision (2026-05-05): efficiency splits into two metrics

`efficiency(R)` is now two metrics:

| Metric | Definition | Rationale |
|---|---|---|
| `cost_efficiency(R)` | coverage / cost | Resource-oriented: are we using LLM calls well? |
| `depth_efficiency(R)` | coverage / depth | Structural: breadth without excessive sequential depth. Substrate-independent — depth stays constant across runtimes while cost may differ. |

This avoids ambiguity about which denominator "efficiency" uses, and surfaces
a substrate-independent metric (depth_efficiency) alongside the budget-aware one
(cost_efficiency).

### Updated examples

| Recipe | cost | depth | coverage | cost_efficiency | depth_efficiency |
|---|---|---|---|---|---|
| `refine` | 4 | 3 | 3 | 0.75 | 1.0 |
| `wide_pass` | 5 | 2 | 4 | 0.80 | 2.0 |
| `clarify` | 2 | 2 | 2 | 1.00 | 1.0 |

## Consequences

- Depth now carries its natural meaning: how many sequential steps deep
  is the pipeline? This is useful for reasoning about latency and
  structural complexity.
- Cost maps directly to the budget ceiling (7 calls). Budget exhaustion
  is a cost concern, not a depth concern.
- Recipe cards in the spec and workspace docs now report both metrics.
- The `recipe_structure` extension schema (ADR-006) gains a `cost` field
  alongside the existing `depth` field.
- No code changes required — the Python source uses `depth` only in a
  test mock field unrelated to this metric.
