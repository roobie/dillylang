---
id: dillylang::adr-005
description: Formalize the classify operator's output schema, input contract, and design constraints
tags: [operator, schema, judge, classify]
created: 2026-04-30
status: active
---

# 005 — classify operator schema

## Status

Accepted

## Context

`classify` is referenced throughout the spec as the highest-priority
addition (§12) and "the router operator that enables automatic recipe
selection." It appears in §4 (Tier 2 judge: "discrete label from
taxonomy"), §9 (canonization pattern, meta-recipe shapes), and §12
(highest-leverage single addition). ADR-004 explicitly identifies
`classify` as the forcing function for documentation canonization
routing. [[THIS is_grounded_by: urn:unique_reference:dillylang::adr-004]]

Despite this, the spec provides only a one-liner — no output schema, no
input contract, no design constraints. Two independent recipe designs
(`skill_to_dillylang`, `design_recipe`) converged on an identical
proposed schema for `classify`. Both list the missing schema as a
high-severity implementation blocker.
[[THIS grounds: urn:unique_reference:dillylang::recipe-plan-skill-to-dillylang]]
[[THIS grounds: urn:unique_reference:dillylang::recipe-plan-design-recipe]]

The convergence across two unrelated use cases — skill categorization
(execution model + recipe shape) and problem categorization (problem
type + recipe shape) — provides strong evidence that the proposed schema
is not task-specific but reflects `classify`'s general structure.

The spec's identity/provenance invariant (§5) already anticipates this
operator: "applies especially to selection and judgment operators such
as `rank`, `filter`, future `classify`, and future `compare`."

## Decision

### Output schema

```json
{
  "classifications": [
    {
      "taxonomy": "str",
      "label": "str",
      "rationale": "str",
      "confidence": "low | medium | high"
    }
  ]
}
```

### Input contract

`classify` accepts a `taxonomies` parameter: a mapping from taxonomy name
to a list of valid labels.

```python
classify(taxonomies: dict[str, list[str]])
```

### Design constraints

**Single-label per taxonomy.** Each taxonomy produces exactly one
classification object in the output array. The runtime validates
uniqueness on the `taxonomy` key. The array structure accommodates
multiple taxonomies per call, not multiple labels within one taxonomy.
Multi-label classification is a different operation — if needed, it
would be a separate operator or a future schema extension.

**Closed-set labels.** The returned label must be a member of the
provided taxonomy's label list. The operator assigns labels; it does not
create them or do open-ended reasoning. Open-ended labeling would be a
different operator.

**Escape hatch via taxonomy design.** Taxonomies that cannot guarantee
exhaustive coverage must include an explicit escape label (`"other"`,
`"unknown"`, `"none"`). This puts the burden on the recipe designer
defining the taxonomy, not on the operator. The operator's closed-set
validation is strict: without an escape label, the LLM will force a bad
fit — a silent, hard-to-detect failure mode.

**Rationale required.** Every classification includes a rationale
explaining why the label was chosen. This matches `evaluate`'s pattern
and enables prompt iteration and audit.

**Confidence required.** Every classification includes a confidence
level. This enables downstream decisions: filter on low confidence,
route differently based on confidence, flag uncertain classifications
for human review. Ambiguity belongs in `rationale` + `confidence: "low"`
— a separate `open_questions` field would duplicate what confidence
already communicates and diverge from `evaluate`'s pattern.

**Multiple taxonomies per call.** A single `classify` invocation resolves
all provided taxonomies in one LLM call. Both recipe plans use two
taxonomies per invocation — splitting into separate calls would double
the budget cost for no quality gain when taxonomies are related.

### Relationship to other operators

`classify` is to `evaluate` as categorization is to judgment: `evaluate`
produces `pass`/`partial`/`fail` against a criterion, `classify` produces
a label from a taxonomy.

`classify` + `branch` (future combinator) = the router pattern. `classify`
labels; `branch` dispatches based on the label. Together they enable
conditional pipeline construction.

Unlike `rank`, `classify` operates on a single artifact, not a collection.
Unlike `evaluate`, it produces a discrete label rather than a graded
verdict. Both share the judge-tier pattern of requiring rationale and
confidence. [[THIS grounds: urn:unique_reference:dillylang::spec-index]]

## Why this could be wrong

- **Multi-taxonomy shallowness.** Resolving multiple unrelated taxonomies
  in a single call might produce shallow rationale per classification. If
  taxonomies require deep domain reasoning, splitting into separate calls
  (at budget cost) may produce better results. Empirical — monitor
  rationale quality in early recipe runs.
- **Escape-hatch burden on designers.** The mandatory escape label policy
  shifts complexity to taxonomy design. Recipe designers must think about
  coverage upfront. If they forget an escape label, the failure mode
  (forced bad fit) is silent. A runtime warning for taxonomies lacking an
  escape label could mitigate this, but adds complexity to the operator.
- **Schema minimalism.** The schema may be too minimal for future use
  cases: hierarchical taxonomies (e.g. "generative > diverge-curate-
  converge"), weighted multi-label classification, or taxonomy evolution
  across pipeline runs. These would require schema extensions. The
  current design preserves the option — the `classifications` array is
  extensible per entry — but doesn't provision for them.

## Consequences

- Unblocks implementation of both meta-recipes (`skill_to_dillylang`,
  `design_recipe`), both of which list the missing schema as a
  high-severity blocker.
- Establishes judge-operator precedent: Tier 2 operators require both
  confidence and rationale. This is consistent with `evaluate` and
  should inform future judge operators (`compare`, any additions).
- Enables the `classify` + `branch` router pattern for canonization
  (ADR-004) and recipe selection (`design_recipe`).
- Spec §4 (pantry table) and §6 (operator schemas) should be updated to
  include `classify`'s schema. This is a downstream task, not part of
  this ADR.
