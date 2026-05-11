---
id: dillylang::adr-001
description: Decision to lock DSPy as the v0 runtime substrate
tags: [architecture, substrate, v0]
created: 2026-04-30
status: active
---

# 001 — DSPy as v0 substrate

## Status

Accepted

## Context

The pipeline system needs a substrate for structured LLM calls: prompt
rendering, structured output parsing, retry logic, and signature
validation. Two paths were considered:

1. **Build on DSPy** — use `dspy.Module` as the operator base class,
   `dspy.Signature` for input/output contracts, `dspy.Predict` for LLM
   calls, and DSPy's built-in tracing as the trace viewer foundation.
2. **Build standalone** — implement structured output handling, retry
   logic, and signature validation from scratch.

The pantry vocabulary (operator taxonomy, recipes, execution models) is
substrate-independent by design. The substrate choice is an
implementation concern, not a conceptual one.

## Decision

Lock DSPy as the v0 substrate.

- Each `Operator` wraps or subclasses `dspy.Module`.
- Input/output contracts map to `dspy.Signature` plus local schema
  validation where DSPy's type system is not strict enough.
- Combinators (`pipe`, `parallel`, `map`, `filter`) are library code
  over DSPy modules.
- `bind` returns a new module with prefilled signature fields.
- DSPy's trace/inspection facilities are the starting point for the
  trace viewer, augmented to emit the project's `TraceEntry` shape.

A standalone runtime is out of scope for v0.

## Why DSPy over standalone

- **Less substrate work.** DSPy provides primitives for structured output
  handling, LLM call management, and retry infrastructure. The project
  runner owns the exact policy (repair-once/fail-loud, final schema
  enforcement via local validation), but DSPy handles the lower-level
  plumbing. Building standalone would add ~2 days to the roadmap.
- **Tracing foundation.** DSPy has built-in trace/inspection that can
  be augmented rather than built from zero.
- **Community and ecosystem.** DSPy has an active community, optimizer
  infrastructure (for future prompt tuning), and model-agnostic LLM
  dispatch.

## Why this could be wrong

- DSPy's `Signature` system may be too rigid for some operator schemas
  (nested objects, union types, optional fields).
- DSPy's tracing may not map cleanly to the project's `TraceEntry`
  shape, requiring wrapper code that partially negates the "less work"
  benefit.
- DSPy is a moving target — breaking changes in DSPy releases could
  create maintenance burden.

## Consequences

- Implementation uses DSPy idioms. Contributors need DSPy familiarity.
- If DSPy blocks a core requirement, revisit this decision rather than
  working around it. Reversal signals: inability to represent nested or
  union-typed schemas without excessive wrappers, trace mismatch requiring
  more wrapper code than a standalone trace would, or unstable API
  causing repeated breakage across DSPy releases.
- The spec's type sketches (§5) are written substrate-independently so
  the vocabulary remains portable if the substrate changes. [[THIS grounds: urn:unique_reference:dillylang::spec-index]]
