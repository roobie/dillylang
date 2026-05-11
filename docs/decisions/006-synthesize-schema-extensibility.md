---
id: dillylang::adr-006
description: Synthesize's §6 schema is a minimum integration contract — extensions add domain-specific fields while preserving base semantics
tags: [operator, schema, synthesize, extensibility]
created: 2026-04-30
status: active
---

# 006 — Synthesize schema extensibility (minimum contract, not maximum)

## Status

Accepted

## Context

Three threads converge on the same conclusion: synthesize's §6 schema
defines a floor, not a ceiling.
[[THIS is_grounded_by: urn:unique_reference:dillylang::spec-index]]

**The fragile-renderer problem.** `design_recipe` needs typed pipeline
stages (`operator`, `role`, `bindings`, `axis`) in synthesize output so
its renderer can produce recipe definitions. The original design assumed
the renderer could extract these from `proposal.statement` prose. It
cannot — LLM-generated pseudocode is not reliably parseable into typed
structures. The fix: extend synthesize output with a `recipe_structure`
object containing typed fields the renderer reads directly.
`skill_to_dillylang` has the same latent issue — its
`DillylangSkillDescription` is a deterministic projection of the full
artifact collection, and its renderer faces the same prose-parsing
fragility.
[[THIS grounds: urn:unique_reference:dillylang::recipe-plan-design-recipe]]
[[THIS grounds: urn:unique_reference:dillylang::recipe-plan-skill-to-dillylang]]

**DSPy signatures are additive.** The v0 substrate (ADR-001) naturally
supports field extension — adding output fields to a DSPy signature
doesn't require modifying the base signature class. The runtime already
handles this. Extensibility is the path of least resistance, not an
architectural stretch.
[[THIS is_grounded_by: urn:unique_reference:dillylang::adr-001]]

**The base fields have coherent integration semantics.** The six §6
fields — `proposal`, `incorporates`, `tradeoffs`, `open_questions`,
`conflicts_addressed`, `confidence` — form a complete integration
contract. They answer: "what did you do with what you received?" Every
synthesis acknowledges upstream artifacts, surfaces conflicts, and makes
tradeoffs explicit. Domain-specific payload (`recipe_structure`, skill
descriptions, etc.) is orthogonal to this contract. The base fields are
the integration guarantee; extensions carry the domain-specific payload.

Two independent recipes arriving at the same conclusion — from different
directions (recipe design vs. skill translation) — is the strongest
evidence that this is a general property of synthesize, not a
task-specific accommodation.

## Decision

Three rules govern synthesize schema extensibility.

### Rule 1: Base fields are always required

Every synthesize invocation — standard or extended — must populate all
six base fields per §6. This is the integration contract. Omitting base
fields (e.g. dropping `conflicts_addressed` because "there were no
conflicts") is a schema violation, not a simplification. The base fields
exist to force the synthesis prompt to do the hard cognitive work of
integration; skipping them means the synthesis hasn't happened.

### Rule 2: Extensions are additive top-level keys

Domain-specific fields are added as new top-level keys in the output
schema (e.g. `recipe_structure`). They do not modify, reinterpret, or
shadow base field semantics. An extended schema is a strict superset of
the base schema.

`design_recipe`'s extended schema illustrates this:

```json
{
  "proposal": { "statement": "...", "rationale": "..." },
  "incorporates": [{ "source_artifact_id": "...", "contribution": "..." }],
  "tradeoffs": [{ "gained": "...", "given_up": "..." }],
  "open_questions": ["..."],
  "conflicts_addressed": [{ "conflict": "...", "resolution": "..." }],
  "confidence": "low | medium | high",

  "recipe_structure": {
    "name": "str",
    "purpose": "str",
    "definition": "str (Dillylang pseudocode)",
    "existing_recipe": "str | null",
    "stages": [
      {
        "operator": "str",
        "role": "str",
        "bindings": { "field": "value" },
        "axis": "str | null"
      }
    ],
    "cost": "int",
    "depth": "int",
    "axes": ["str"]
  }
}
```

The first six fields are unchanged from §6. `recipe_structure` is
additive — removing it yields a valid base schema.

### Rule 3: Extension semantics belong to the recipe, not the operator

The synthesize operator's prompt template is parameterized to request
extension fields when configured. The base prompt logic — acknowledge
all upstream artifacts, forbid silent dropping, anti-averaging
instruction — is invariant across all invocations. Extension fields get
their own prompt section; they don't dilute or modify the base synthesis
instructions.

This means the synthesize operator remains one operator with one
cognitive job (integrate upstream perspectives into a coherent whole).
Extensions expand the output surface, not the cognitive operation.

### Implementation mechanism in DSPy

Recipe-specific synthesize modules extend the base signature with
additional output fields:

```python
class SynthesizeSignature(dspy.Signature):
    """Base synthesis — spec §6 integration contract."""
    proposal = dspy.OutputField()
    incorporates = dspy.OutputField()
    tradeoffs = dspy.OutputField()
    open_questions = dspy.OutputField()
    conflicts_addressed = dspy.OutputField()
    confidence = dspy.OutputField()

class SynthesizeRecipeSignature(SynthesizeSignature):
    """Extended synthesis for design_recipe."""
    recipe_structure = dspy.OutputField(
        desc="typed pipeline definition with stages, bindings, and axes"
    )
```

DSPy's `OutputField` is additive — subclassing preserves all base fields
without modification. The base signature class is the single source of
truth for the integration contract.

## Why this could be wrong

**Schema drift.** Without discipline, extensions proliferate and
synthesize becomes a dumping ground for whatever the recipe wants the LLM
to produce. Mitigation: every extension field must have a named consumer
(renderer, downstream operator). Fields without consumers are dead
weight. Recipe plans should document the consumer for each extension
field.

**Prompt dilution.** Adding extension fields increases the output surface
area the LLM must fill. If extension fields are complex (as
`recipe_structure` is — nested objects, arrays of stage definitions),
the base fields may receive less attention. The integration contract
degrades silently: `incorporates` entries become perfunctory,
`conflicts_addressed` gets an empty array even when conflicts exist.
Mitigation: monitor base field quality in extended synthesis runs. If
`incorporates` or `conflicts_addressed` quality degrades, the extension
is too heavy for a single LLM call and should be split into a separate
step.

**Validation burden.** Runtime must validate base fields (always) and
extension fields (per-recipe) — two validation layers. DSPy's type
system handles structural validation; semantic validation (did the LLM
actually acknowledge all upstream artifacts, or just list them?) remains
a prompt-quality problem regardless of extensibility.

## Consequences

- Unblocks implementation of both `design_recipe` and
  `skill_to_dillylang`, which list this as a pre-implementation blocker.
  [[THIS grounds: urn:unique_reference:dillylang::recipe-plan-design-recipe]]
  [[THIS grounds: urn:unique_reference:dillylang::recipe-plan-skill-to-dillylang]]
- Spec §6 should be updated to note that the synthesize schema is
  extensible — a paragraph after the schema block stating the
  minimum-contract semantics and pointing to this ADR. (Downstream task.)
  [[THIS grounds: urn:unique_reference:dillylang::spec-index]]
- Establishes pattern: future meta-recipes that produce structured
  artifacts can extend synthesize without requesting a new operator or a
  spec change.
- Does **not** change synthesize's identity as the "rebuild step."
  Extensions add typed payload; the cognitive operation is unchanged.
- Prompt dilution is the risk to watch. The first extended synthesis runs
  (`design_recipe` day 5-6 per spec §11) will be the empirical test —
  compare base field quality between standard and extended invocations.
