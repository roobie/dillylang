---
id: dillylang::adr-003
description: Decision to exclude irreducibles from the v0 decompose operator
tags: [operators, decompose, v0]
created: 2026-04-30
status: active
---

# 003 — Irreducibles excluded from v0 decompose

## Status

Accepted

## Context

The original handoff document included an `irreducibles` field [[THIS is_grounded_by: urn:unique_reference:dillylang::handoff-v0]]
in the `decompose` operator's output schema — defined as "minimum
statements sufficient to reconstruct" the original claim. During spec
review, this was identified as a distinct cognitive operation from
decomposition.

`decompose` does structural analysis: find axioms, trace derivations,
surface assumptions. `irreducibles` is a compression/projection
operation: given the structural analysis, what is the minimal
reconstruction set? These are related but separable, and combining
them in one operator risks both being done shallowly on complex inputs.

## Decision

Exclude `irreducibles` from the v0 `decompose` schema. The v0 schema
contains `axioms`, `derivations`, and `assumptions` only.

If recipes need a minimal-reconstruction step, it can be:
- A post-processing function over `decompose` output (no LLM call).
- A separate lightweight operator if the compression requires LLM
  judgment.
- Reintroduced into `decompose` if v0 usage shows the two operations
  are inseparable in practice.

## Why not keep it

- **Operator design principle: "if you find yourself building a clever
  operator, it's probably two operators."** Decomposition and compression
  are different operations. Bundling them in one prompt risks both being
  done shallowly.
- **Prompt quality.** On complex inputs, the LLM will do one operation
  well and phone in the other. Narrower prompts produce better output.
- **Schema simplicity.** Three output sections are easier to validate
  and render in the trace viewer than four.

## Consequences

- `decompose` is narrower and more focused.
- The future option to add irreducibles (as a separate step or
  reintegrated) is preserved.
- Recipes that relied on irreducibles in the original design
  conversation will need to either skip the step or add an explicit
  compression stage.
