---
id: dillylang::adr-009
description: ComputeMetricsNode uses is_combinator=True to bypass budget tracking for deterministic computation
tags: [architecture, pipeline, budget]
created: 2026-05-05
status: active
---

# 009 — Deterministic Pipeline Steps via is_combinator Routing

[[THIS is_grounded_by: urn:unique_reference:dillylang::adr-008]]

## Status

Accepted

## Context

The analyze meta-skill pipeline has the shape:

```python
pipe(compute_metrics_node, bind(evaluate, criterion="..."))
```

`compute_metrics` is a pure deterministic function (no LLM call). It computes
static orthogonality metrics from a `DillylangSkillDescription`'s operator list
and pseudocode structure. It needs to appear as a pipeline step so the result
flows naturally through `pipe()` to `evaluate`.

The pipeline router (`execute_node` in `_routing.py`) has two paths:

| Flag | Routing | Budget | Trace |
|------|---------|--------|-------|
| `is_combinator=True` | `.run()` directly | No deduction | No emission |
| `is_combinator=False` | `run_operator_with_retry` | Deducts 1 call | Emits TraceEntry |

`compute_metrics` is deterministic and should not consume budget or emit trace
entries (there is no LLM interaction to record).

## Decision

`ComputeMetricsNode` sets `is_combinator = True` to use the direct `.run()`
path. This is a deliberate reuse of the combinator routing mechanism for a
deterministic computation that is not technically a combinator.

The alternative -- running `compute_metrics` outside the pipeline and passing
results separately -- was rejected because it breaks the composable `pipe()`
pattern and forces the `analyze` function to manage data flow manually instead
of leveraging the pipeline runner.

## Consequences

- Deterministic pipeline steps bypass budget tracking. Correct: they use zero
  LLM calls.
- They also bypass trace emission. Acceptable: deterministic steps have no LLM
  interaction to trace; the result is stored in `ctx.artifacts` for the renderer.
- Future deterministic pipeline steps should follow this same pattern.
- If trace emission for deterministic steps becomes desirable, a third routing
  path (`is_deterministic`) could be added to `execute_node`, but this is not
  needed now.
