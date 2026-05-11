# Operator Output Fields — Quick Reference

Field names for each operator's output schema. Use these to produce
schema-shaped YAML in Model C traces. For full descriptions, steering
parameters, and prompt guidance, see `spec/INDEX.md` §4.

## Transformers

### decompose
- `axioms[]` — statement, justification
- `derivations[]` — claim, depends_on[]
- `assumptions[]` — statement, load_bearing, testable

### synthesize
- `proposal` — statement, rationale
- `incorporates[]` — source_artifact_id, contribution
- `tradeoffs[]` — gained, given_up
- `open_questions[]`
- `conflicts_addressed[]` — conflict, resolution (resolved|deferred|accepted_as_tradeoff)
- `confidence` — low|medium|high

### invert
- `anti_goals[]`
- `failure_modes[]` — mode, mechanism, likelihood (low|medium|high), severity (recoverable|costly|fatal), preventable_by
- `near_misses[]`

### rotate
- `original_axis`
- `rotations[]` — new_axis, rotation_kind (axis_change|viewpoint_change), restated_problem, what_becomes_visible[], what_recedes[]

### analogize
- `problem_signature`
- `analogies[]` — domain, analog, mechanism_mapping, transferable_insight, stowaways[]

### abstract
- `principles[]` — statement, grounding[], abstraction_level
- `source_pattern`

### concretize
- `instances[]` — description, derivation, constraints_applied[]
- `target_domain`

### constrain
- `constraints_added[]` — constraint, justification, impact
- `impact_on_solution_space`
- `tradeoffs[]` — gained, given_up

### relax
- `constraints_removed[]` — original_constraint, relaxation, justification
- `new_possibilities[]`
- `risks_introduced[]`

## Judges

### evaluate
- `criterion`
- `verdict` — pass|partial|fail
- `evidence[]`
- `rationale`
- `confidence` — low|medium|high

### rank
- `ranked[]` — artifact_id, scores{criterion: high|medium|low}, rationale
- `top_k_ids[]`

### classify
- `classifications[]` — taxonomy, label, rationale, confidence (low|medium|high)

### compare
- `criterion`
- `winner` — artifact_id or "tie"
- `rationale`
- `comparison_points[]` — dimension, artifact_a_assessment, artifact_b_assessment
- `confidence` — low|medium|high
