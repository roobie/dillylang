---
id: dillylang::adr-004
description: Conservative canonization gate for promoting exploratory prose into durable docs
tags: [process, documentation, canonization]
created: 2026-04-30
status: active
---

# 004 — Canonization gate for durable documentation

## Status

Accepted

## Context

The project produces useful exploratory prose: riffs, reviews, design
discussion, self-application results, and model analyses. Some of it should
become canonical documentation, but promoting prose directly risks spec bloat,
duplication, and vague philosophy.

Self-application of the `canonize_prose` recipe (applying the canonization
pipeline to its own design conversation) surfaced a key finding: good
canonization requires routing claims to the right artifact, not just judging
whether they're spec-worthy. This is the same routing problem that `classify`
solves at runtime — documentation routing and recipe selection are the same
primitive.

## Decision

Use a conservative canonization gate before promoting exploratory prose into
durable project docs. This applies to promoting exploratory prose and model
analysis into canonical docs, not to typo fixes, link updates, or mechanical
maintenance.

`extract claims → route destination → judge fitness (destination-relative) → rank → synthesize patch-like text`

A claim is documentation-worthy only if it is durable, operational,
non-obvious, scoped, and low-regret.

Claims that are inspirational only, duplicative, speculative, runtime-transient,
or better suited for an ADR/open question are not promoted into the canonical
spec.

Destination routing matters. A surviving claim should be routed to one of:
`spec`, `ADR`, `AGENTS.md`, `open question`, `archive/provenance`, or `discard`.

## Why this could be wrong

- The gate may become too conservative and discard useful intuition.
- It adds process overhead for small documentation updates.
- "Low-regret" and "non-obvious" are judgment calls and can vary by reviewer.

## Predicate calibration

The five predicates are judgment calls without anchoring examples. These
accepted/rejected pairs set the threshold — not exhaustively, but enough
to detect drift.

**Durable:** Will this still be true in 6 months, or is it tied to current implementation state?

- Rejected: "The DSPy adapter handles retries." (Implementation detail — changes when the adapter changes.)
- Accepted: "Operators are typed functions with explicit input/output schemas." (Structural property that survives refactoring.)

**Operational:** Does this tell an implementer what to do, or just what to value?

- Rejected: "Quality matters for operator output." (Desideratum, not instruction.)
- Accepted: "Every operator must emit a TraceEntry on completion, including on failure." (Testable constraint.)

**Non-obvious:** Would a competent reader already know this from the code or spec?

- Rejected: "Pydantic validates operator schemas." (Directly visible in the codebase.)
- Accepted: "The canonization pipeline is structurally equivalent to a `classify` application." (Cross-cutting insight not visible in any single file.)

**Scoped:** Does this belong in one place, or does it sprawl across concerns?

- Rejected: "The project should have good documentation practices." (Unbounded — touches every file.)
- Accepted: "Claims routed to `spec` must satisfy all five predicates; claims routed to `ADR` need only durable + non-obvious." (Bounded to the routing step.)

**Low-regret:** If this turns out to be wrong, how expensive is the reversal?

- Rejected: "All operators must use DSPy signatures." (Reversal requires rewriting every operator.)
- Accepted: "Exploratory prose is archived at `archive/provenance/` rather than deleted." (Reversal is a directory move.)

## Trigger

The gate fires on any PR or commit that adds or substantially modifies content
in canonical doc paths: `spec/`, `AGENTS.md`, `CLAUDE.md`, `docs/decisions/`.

Excluded: typo fixes, link updates, formatting-only changes, and mechanical
maintenance (these don't promote exploratory prose — they maintain existing
canonical docs).

This is a soft gate — it reminds the contributor to apply the predicates, but
does not block merge. Hard gating is premature at current project maturity.

## Consequences

- Canonical docs should stay tighter and less vibe-heavy.
- Reviews/riffs can still be valuable without being copied verbatim.
- `classify` gains an additional v1 justification: documentation routing,
  not only runtime recipe selection. [[THIS grounds: urn:unique_reference:dillylang::spec-index]]
- Until `classify` exists, routing can be approximated with `evaluate`,
  `rank`, and human judgment.
- Pipeline ordering revised to route-first: see ADR-010. [[THIS grounds: urn:unique_reference:dillylang::adr-010]]
