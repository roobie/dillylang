---
id: dillylang::adr-007
description: Formalize focus and target_frame as declared steering parameters on decompose and rotate; establish the input-schema pattern
tags: [operator, schema, input, bind, decompose, rotate, steering-parameter]
created: 2026-04-30
status: active
---

# 007 — Operator input schemas: steering parameters (`focus`, `target_frame`)

## Status

Accepted

## Context

Three threads converge on the same gap: the spec declares
`input_schema: Schema[I]` on the `Operator` class (§5, line 321) but
never populates it for most operators. `bind` promises schema-level
currying — "returns a new operator with the partial input pre-applied;
the new operator has a smaller input requirement" (§7, lines 656-659).
Without declared input schemas, `bind` is injecting ad-hoc text, not
narrowing a typed contract.
[[THIS is_grounded_by: urn:unique_reference:dillylang::spec-index]]

**The gap in §6.** Section 6 defines output schemas for all operators
but input schemas for only one: `rank` (lines 614-618, with `artifacts`,
`criteria`, `top_k`). `decompose` (lines 457-485), `rotate`
(lines 510-533), `evaluate` (lines 592-605), and `analogize`
(lines 535-555) have output schemas only. Yet the spec uses `bind` with
undeclared parameters throughout: `bind(evaluate, criterion="X")`,
`bind(analogize, domains=[...])`, `bind(rotate, target="...")`.

**Two independent recipe plans depend on undeclared fields.**
`design_recipe` uses `bind(decompose, focus="requirements, constraints,
success criteria, assumptions about the problem")` (line 81-83).
`skill_to_dillylang` uses `bind(decompose, focus="entrypoint, trigger,
inputs, outputs, stages, assumptions, control flow")` (lines 106-108)
and `bind(rotate, target_frame="Dillylang operator and combinator
vocabulary")` (lines 125-128). Both plans explicitly call these "formal
input parameters" and list their confirmation as a pre-implementation
blocker (design-recipe.PLAN.md lines 461-464).
[[THIS is_grounded_by: urn:unique_reference:dillylang::recipe-plan-design-recipe]]
[[THIS is_grounded_by: urn:unique_reference:dillylang::recipe-plan-skill-to-dillylang]]

The skill-to-dillylang plan (line 426) states the design question
cleanly: "If `focus` and `target_frame` are formal, other recipes can
bind different values and get predictable behavior. If they're ad-hoc,
each recipe's bindings are opaque."

**`target` vs `target_frame` name collision.** The spec's v1 patterns
(§9, line 793) use `bind(rotate, target="strongest_form_of_position")`.
The recipe plans use `target_frame`. These cannot both be canonical.

## Decision

### Two categories of operator input

The spec's dataflow contract (§5, lines 344-367) already defines the
primary data channel: each operator receives the upstream value (`input`)
plus the immutable `Context`. The upstream value is the artifact or
problem string flowing through the pipeline — managed by combinators
(`pipe` passes output to next step, `parallel` fans out the same input).
This data input is not declared in `input_schema` for most operators;
it's the implicit pipeline channel.

`input_schema` declares the additional structured fields the operator
accepts — the fields that `bind` can pre-fill. These are **steering
parameters**: they shape how the operator processes its data input
without changing what data it receives.

Properties of steering parameters:

- **Declared in `input_schema`** and validated before prompt rendering.
  They appear in traces as structured input, not opaque prompt text.
- **Optional with sensible defaults.** An unbound operator still works
  on its data input without domain-specific steering. Binding narrows
  focus; omitting gives full-scope behavior.
- **Rendered into the prompt.** The operator's `render` function
  interpolates them into the prompt template alongside the data input
  and `Context.problem`.
- **Bindable and composable.** Because they are declared schema fields,
  `bind` narrows a typed contract — exactly what §7 line 658 promises.

`rank` is the exception that proves the rule: its `input_schema`
includes both a data field (`artifacts: [Artifact]`) and steering
parameters (`criteria`, `top_k`). `rank` needs `artifacts` explicitly
declared because it operates on a collection assembled from context, not
the single upstream value that `pipe` passes. For `decompose` and
`rotate`, the data input is the implicit upstream value — only steering
parameters need declaration.

This distinction is operational, not just taxonomic: the runtime handles
data flow through combinators; `bind` handles steering parameters through
schema-level currying. Two separate mechanisms, clearly separated.

### `focus` on `decompose`

`decompose`'s input schema declares one steering parameter. The upstream
value (problem text or artifact) flows through the implicit data channel
per the dataflow contract.

```python
# input_schema (steering parameters; data arrives via pipeline)
{
    "focus": str | None  # optional; None = full-scope decomposition
}
```

When bound, `focus` narrows decomposition to specified structural
aspects. It is rendered into the prompt as a directive steering the
axiom search toward particular dimensions of the problem.

When unbound (`None`), decompose performs general structural
decomposition per §6 — "a search for axioms" over the full input.

Output schema is unchanged regardless of binding — `focus` shapes what
the LLM decomposes, not the structure of the result. This distinguishes
steering parameters from ADR-006's synthesize output extensibility, which
adds output fields.
[[THIS is_grounded_by: urn:unique_reference:dillylang::adr-006]]

Examples from recipe plans:

- `bind(decompose, focus="requirements, constraints, success criteria,
  assumptions about the problem")` — narrows to goal-structure analysis
  for `design_recipe`.
- `bind(decompose, focus="entrypoint, trigger, inputs, outputs, stages,
  assumptions, control flow")` — narrows to behavioral-contract analysis
  for `skill_to_dillylang`.

### `target_frame` on `rotate`

Same pattern as `decompose`: one steering parameter, data via pipeline.

```python
# input_schema (steering parameters; data arrives via pipeline)
{
    "target_frame": str | None  # optional; None = open-ended frame exploration
}
```

When bound, `target_frame` names the frame of reference to rotate
toward. When unbound (`None`), rotate performs open-ended frame
exploration with the implicit-subject probe per §6. Output schema
unchanged.

**Canonical name is `target_frame`, not `target`.** The spec's v1
patterns (line 793) use `target`. `target_frame` wins because:

1. It is self-documenting — the name says what kind of target: a frame
   of reference. `target` is ambiguous on an operator whose job is
   frame-change.
2. The v1 patterns are explicitly planning sketches ("named patterns for
   v1"), not canonical declarations. Renaming `target` to `target_frame`
   in those patterns is a non-breaking editorial fix.

The v1 patterns also use `bind(rotate, adversarial=true)` and
`bind(rotate, perturbed_axis="...")`. These are not formalized here —
they are v1 sketches that may evolve. When v1 patterns are implemented,
each should be evaluated as a candidate steering parameter or a separate
operator variant. This ADR establishes the pattern; future parameters
follow the same process.

### Broader principle: declare input schemas for all operators

The following operators have steering parameters used in spec examples
or recipe plans but not formally declared:

| Operator | Parameter | Status |
|---|---|---|
| `decompose` | `focus` | **Formalized here** |
| `rotate` | `target_frame` | **Formalized here** |
| `evaluate` | `criterion` | Downstream — formalize when implementing |
| `analogize` | `domains` | Downstream — formalize when implementing |
| `rank` | `criteria`, `top_k` | Already formalized in §6 |

New steering parameters should default to requiring at least two
independent recipe demands before formalization — the same threshold
`focus` and `target_frame` cleared — unless a parameter is required by
an operator's core semantics (as `criterion` is for `evaluate`: §6 line
594-595 describes it as "conditional — requires a criterion to be
bound"). This aligns with §13's anti-pattern: "Don't pad operators with
config flags."

**`criterion` on `evaluate` deserves special note.** Unlike `focus` and
`target_frame`, which are optional, `criterion` appears required — an
unbound `evaluate` has no criterion to judge against. This makes it a
required steering parameter with no sensible default. `evaluate` without
a bound criterion should fail at input validation. Formalizing `criterion`
is deferred to `evaluate`'s implementation, but the semantics are clear.

### Implementation in DSPy

In DSPy, both the data input and steering parameters are `InputField`s
on the signature. The data input carries the upstream value; steering
parameters are optional fields that `bind` pre-fills. The exact
mechanism for optional fields should follow DSPy's supported pattern
(verify against DSPy docs during implementation):
[[THIS is_grounded_by: urn:unique_reference:dillylang::adr-001]]

```python
class DecomposeSignature(dspy.Signature):
    """Separate what's load-bearing from what's assumed."""
    # Data input — upstream value from pipeline
    problem_text = dspy.InputField(
        desc="problem statement or upstream artifact to decompose"
    )
    # Steering parameter — bound by recipes via bind()
    focus = dspy.InputField(
        default=None,
        desc="structural aspects to focus decomposition on"
    )
    # Output fields (unchanged from §6)
    axioms = dspy.OutputField()
    derivations = dspy.OutputField()
    assumptions = dspy.OutputField()

class RotateSignature(dspy.Signature):
    """Change the axis of inquiry."""
    problem_text = dspy.InputField(
        desc="problem statement or upstream artifact to rotate"
    )
    target_frame = dspy.InputField(
        default=None,
        desc="frame of reference to rotate toward"
    )
    original_axis = dspy.OutputField()
    rotations = dspy.OutputField()
```

The runtime maps the upstream pipeline value to `problem_text` (or
equivalent data field). `bind(decompose, focus="X")` pre-fills `focus`,
producing a new signature where `focus` is no longer a free input.

## Why this could be wrong

**Steering vs. data may not be cleanly separable.** `focus` could be
seen as part of the problem specification rather than operator
configuration. If the distinction proves unprincipled in practice, the
two categories collapse into a flat input schema — no harm done, but
wasted vocabulary. The operational test: a steering parameter is part of
the declared schema, appears in traces as structured input, and is
validated before prompt rendering. If a field fails this test, it's data
or prompt text, not a steering parameter.

**Optional-with-default may mask underspecification.** An unbound
`decompose` that "performs general structural decomposition" sounds
reasonable but may produce unfocused output that downstream operators
cannot use effectively. If recipes routinely bind `focus` because the
unbound default is too vague to be useful, then `focus` is optional in
theory but required in practice — a leaky abstraction. Monitor whether
unbound invocations appear in real pipelines.

**Parameter sprawl.** Once the pattern exists, it is tempting to add
steering parameters to every operator. Each parameter adds surface area
to the prompt template and increases the testing matrix. Mitigation: the
two-recipe-or-core-semantics threshold, and §13's existing warning
against config-flag padding.

**The `target` → `target_frame` rename.** Anyone who read the spec and
used `target` must update. Low risk: the v1 patterns are planning
sketches, not shipped API, and no implementation code exists yet.

## Consequences

- Resolves the final pre-implementation blocker for both `design_recipe`
  and `skill_to_dillylang`.
  [[THIS grounds: urn:unique_reference:dillylang::recipe-plan-design-recipe]]
  [[THIS grounds: urn:unique_reference:dillylang::recipe-plan-skill-to-dillylang]]
- Spec §6 should add input schema sections for `decompose` and `rotate`
  (downstream editorial task).
  [[THIS grounds: urn:unique_reference:dillylang::spec-index]]
- Spec §9 v1 patterns should rename `target` to `target_frame`
  (downstream editorial, ~4 lines).
- `bind` semantics are now grounded: `bind(decompose, focus="X")` narrows
  a declared field, not ad-hoc text injection. The resulting operator has
  a concrete, smaller input requirement — exactly what §7 promises.
- Complements ADR-006: ADR-006 addresses output-side extensibility
  (additive fields on synthesize), ADR-007 addresses input-side
  formalization (steering parameters on all operators). Together they
  complete the operator schema picture.
- `criterion` on `evaluate` is the next candidate. Unlike
  `focus`/`target_frame` it appears required, not optional. Formalize
  during `evaluate` implementation.
- Does not change any output schemas. Steering parameters shape prompts;
  output structure is invariant.
