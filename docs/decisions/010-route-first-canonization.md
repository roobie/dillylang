---
id: dillylang::adr-010
description: Invert canonization pipeline to route destination before quality judgment
tags: [process, documentation, canonization]
created: 2026-05-09
status: active
---

# 010 — Route-first canonization: destination before quality judgment

[[THIS is_grounded_by: urn:unique_reference:dillylang::adr-004]]

## Status

Accepted

## Context

ADR-004 defines the canonization pipeline as:

`extract claims → judge canonization fitness → route destination → rank → synthesize`

Decomposition of ADR-004 revealed that quality assessment is
destination-dependent (what's "operational" for the spec differs from what's
"operational" for an ADR). Judging before routing forces the reviewer to apply
a single threshold across all destinations, which is structurally
underdetermined.

Inversion surfaced the specific failure mechanism: the spec is the
highest-status destination. When quality judgment precedes routing, reviewers
unconsciously frame the question as "is this good enough for spec?" Claims
that would make strong ADRs or open questions are either over-promoted to spec
(adding noise) or discarded (losing value). The destination taxonomy exists on
paper but prestige gradient distorts actual routing decisions.

## Decision

Invert the pipeline ordering to route-first:

`extract claims → route destination → judge fitness (destination-relative) → rank → synthesize`

Route destination is now the first substantive decision after extraction.
Quality judgment follows, applying destination-relative criteria: spec claims
must satisfy all five predicates at full strength; ADR claims need primarily
durable + non-obvious; open questions need only non-obvious + scoped.

The question changes from "is this good enough?" (which defaults to
spec-grade) to "where does this belong, and does it meet that destination's
bar?"

## Why this could be wrong

- Routing without quality filtering may anchor the reviewer on destination:
  "it's in the ADR pile, so it must be worth recording." Low-quality claims
  get a destination before being filtered, which may make them harder to
  discard.
- Destination-relative predicates are more complex to apply than a single
  uniform threshold. The reviewer must hold different standards simultaneously.
- If `classify` is implemented to automate routing, the operator's routing
  criteria must be encoded per-destination — more configuration surface than
  a single quality gate.

## Consequences

- ADR-004's pipeline description is historical context; this ADR records the
  updated operating sequence.
- The five predicates from ADR-004 remain, but their thresholds become
  destination-relative. ADR-004's calibration examples anchor the spec-grade
  threshold; lighter examples for other destinations can be added as needed.
- The `classify` operator (when implemented) maps naturally to the routing
  step — its output is a destination tag, not a quality score.
- Reviewers asking "where does this belong?" before "is this good enough?"
  should reduce both spec bloat (over-promotion) and value loss (discarding
  strong-but-not-spec-grade claims).
