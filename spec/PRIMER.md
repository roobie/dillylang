---
id: dillylang::spec-primer
description: Lean operational reference for the Dillylang vocabulary — schemas, combinators, failure semantics
tags: [spec, reference]
created: 2026-05-06
status: active
---

[[THIS is_grounded_by: urn:unique_reference:dillylang::spec-index]]

# Dillylang — Spec Primer

Lean operational reference. For design rationale, history, and open
questions see `spec/INDEX.md`.

**Line budget: this file must stay under 500 lines.**

## What this is

Typed vocabulary of orthogonal thinking moves (operators), composable
into recipes. Not an agent framework — no loops, no tool use. Recipes
are deliberate compositions of pure-ish operators.

```python
refine = pipe(decompose, parallel(invert, rotate), synthesize)
result = refine.run({"problem": "..."})
```

Every run emits an inspectable trace. Trace persistence is opt-in.

---

## Core types

```python
class Artifact:
    id: str              # unique within a pipeline run
    operator: str        # which operator produced this
    step_index: int      # position in pipeline
    data: dict[str, Any] # the operator's structured output
    status: "success" | "repair_succeeded" | "failed" | "partial"
    errors: list[ItemError] | None

class ItemError:
    item_id: str
    error_kind: str      # "parse_failure" | "llm_error" | "predicate_error"
    message: str

class RunResult:
    output: Artifact | list[Artifact]
    trace: list[TraceEntry]
    status: "success" | "partial" | "failed" | "budget_exhausted"
    errors: list[ItemError] | None

class Operator[I, O]:
    name: str
    input_schema: Schema[I]
    output_schema: Schema[O]
    render: Callable[[I, Context], Prompt]
    parse: Callable[[LLMResponse], O]
    config: OperatorConfig

    def bind(self, **partial) -> Operator: ...
    def run(self, input: I, ctx: Context) -> RunResult: ...

class Context:
    problem: str                    # immutable original input
    artifacts: dict[str, Artifact]  # keyed by "{operator_name}_{step_index}"
    trace: list[TraceEntry]
    budget: Budget

class Budget:
    max_llm_calls: int    # ceiling: 7
    max_tokens: int       # ~30K total per pipeline
    max_wall_time_ms: int # 60_000
    llm_calls_used: int
    tokens_used: int
    elapsed_ms: int
```

### Dataflow rules

- Source operator with no upstream receives initial user input.
- `pipe` passes each step's output to the next.
- `parallel` fans same input to every branch; returns artifact list.
- `map`/`filter` operate on explicit collections.
- Transformers render both upstream artifact and `Context.problem` into prompt.
- `synthesize` must acknowledge every upstream artifact by id or defer to `open_questions`.
- LLMs emit artifact IDs to reference existing artifacts, never regenerated copies.

### Budget defaults

```
floor:      3 LLM calls
sweet_spot: 4-5 LLM calls (near-saturation)
ceiling:    7 LLM calls (drift dominates past this)
```

---

## Operator schemas

All operators emit structured output validated against schema.
On parse failure: ONE repair retry, then fail loud.

### Transformers (9 operators, 6 axes)

**`decompose`** — compositionality axis, reduce. Input: `{ "focus": str | None }`.

```json
{
  "axioms": [{ "statement": str, "justification": str }],
  "derivations": [{ "claim": str, "depends_on": [str] }],
  "assumptions": [{ "statement": str, "load_bearing": bool, "testable": str }]
}
```

**`synthesize`** — compositionality axis, recombine. Receives upstream artifact(s).

```json
{
  "proposal": { "statement": str, "rationale": str },
  "incorporates": [{ "source_artifact_id": str, "contribution": str }],
  "tradeoffs": [{ "gained": str, "given_up": str }],
  "open_questions": [str],
  "conflicts_addressed": [{ "conflict": str, "resolution": "resolved" | "deferred" | "accepted_as_tradeoff" }],
  "confidence": "low" | "medium" | "high"
}
```

Anti-instruction: "If your proposal feels like a weighted average, you have
not synthesized — you have summarized. Try again." Each upstream artifact must
be acknowledged or deferred. Silent dropping is forbidden. Six base fields are
the minimum contract; domain recipes may add top-level keys but never shadow
base fields (ADR-006).

**`invert`** — valence axis. Munger/Jacobi inversion.

```json
{
  "anti_goals": [str],
  "failure_modes": [{ "mode": str, "mechanism": str, "likelihood": "low" | "medium" | "high", "severity": "recoverable" | "costly" | "fatal", "preventable_by": str }],
  "near_misses": [str]
}
```

**`rotate`** — frame axis. Input: `{ "target_frame": str | None }`.

```json
{
  "original_axis": str,
  "rotations": [{ "new_axis": str, "rotation_kind": "axis_change" | "viewpoint_change", "restated_problem": str, "what_becomes_visible": [str], "what_recedes": [str] }]
}
```

Probe for the *implicit subject* of the original framing and rotate to alternatives.

**`analogize`** — substrate axis. Input: `{ "domains": list[str] | None }`.

```json
{
  "problem_signature": str,
  "analogies": [{ "domain": str, "analog": str, "mechanism_mapping": str, "transferable_insight": str, "stowaways": [str] }]
}
```

`stowaways` surfaces what *doesn't* transfer cleanly.

**`abstract`** — abstraction axis, upward.

```json
{
  "principles": [{ "statement": str, "grounding": [str], "abstraction_level": str }],
  "source_pattern": str
}
```

**`concretize`** — abstraction axis, downward.

```json
{
  "instances": [{ "description": str, "derivation": str, "constraints_applied": [str] }],
  "target_domain": str
}
```

**`constrain`** — feasibility axis, tighten.

```json
{
  "constraints_added": [{ "constraint": str, "justification": str, "impact": str }],
  "impact_on_solution_space": str,
  "tradeoffs": [{ "gained": str, "given_up": str }]
}
```

**`relax`** — feasibility axis, loosen.

```json
{
  "constraints_removed": [{ "original_constraint": str, "relaxation": str, "justification": str }],
  "new_possibilities": [str],
  "risks_introduced": [str]
}
```

### Judges (4 operators)

**`evaluate`** — requires bound `criterion`.

```json
{
  "criterion": str,
  "verdict": "pass" | "partial" | "fail",
  "evidence": [str],
  "rationale": str,
  "confidence": "low" | "medium" | "high"
}
```

**`rank`** — orders artifacts by criteria, returns IDs only.

```json
{
  "ranked": [{ "artifact_id": str, "scores": { "<criterion>": "high" | "medium" | "low" }, "rationale": str }],
  "top_k_ids": [str]
}
```

**`classify`** — assigns labels from taxonomies. Input: `{ "taxonomies": dict[str, list[str]] }`.
Single-label per taxonomy, closed-set. Include escape label when coverage isn't exhaustive.

```json
{
  "classifications": [{ "taxonomy": str, "label": str, "rationale": str, "confidence": "low" | "medium" | "high" }]
}
```

**`compare`** — pairwise judgment on exactly two artifacts. Input: `{ "criterion": str }`.

```json
{
  "criterion": str,
  "winner": str,
  "rationale": str,
  "comparison_points": [{ "dimension": str, "artifact_a_assessment": str, "artifact_b_assessment": str }],
  "confidence": "low" | "medium" | "high"
}
```

---

## Combinators

### Pipeline combinators

**`pipe(op1, op2, ..., opN)`** — sequential. Each output feeds the next.

**`parallel(op1, ..., opN)`** — fan-out on same input. Concurrent. Returns artifact list.

**`bind(op, **partial_input)`** — currying. Returns operator with smaller input requirement.

**`branch(taxonomy_name, routes, default)`** — conditional dispatch on `classify` labels.
`default` is required (no implicit fallback). Typical pattern:

```python
pipe(
  bind(classify, taxonomies={"type": ["strategic", "tactical"]}),
  branch("type", {"strategic": wide_pass, "tactical": refine}, default=refine)
)
```

### Collection combinators

**`map(op, collection)`** — apply op to each element. Concurrent.

**`filter(predicate_op, collection)`** — keep elements where predicate passes.
Verdict mapping: `pass` => keep, `partial` => keep, `fail` => drop.
Options: `keep_partial=false`, `fail_on_predicate_error=true`.

### Compile-time transforms

`bind` and `identity` do not appear in runtime traces. A bound operator
traces as its underlying operator.

---

## Failure semantics

### Per-operator

1. Validate input. Fail immediately on invalid.
2. Call LLM with structured output.
3. Parse and validate output. On failure: ONE repair retry, then fail loud.
4. On success: append to `context.artifacts`, trace with `status: "success"`.

### Pipeline-level

- **`pipe`:** short-circuits on failure.
- **`parallel`:** runs all branches. Failed branches marked partial; successful outputs still available.
- **`map`:** same as parallel — element failures don't halt.
- **`filter`:** predicate errors are fail-closed (item dropped, error recorded). `fail_on_predicate_error=true` promotes to combinator failure.

### Budget exhaustion

Halt mid-pipeline. Return partial trace. Final entry indicates budget exhaustion, not operator failure.

---

## Shipped recipes

**`refine`** — 3 axes, 4 calls. General decision-support.

```python
refine = pipe(decompose, parallel(invert, rotate), synthesize)
```

**`wide_pass`** — 4 axes, 5 calls. Strategic questions.

```python
wide_pass = pipe(parallel(decompose, invert, rotate, analogize), synthesize)
```

---

## Architecture

Three layers, strict dependency direction:

| Layer | Package | Dependencies |
|---|---|---|
| Vocabulary | `dillylang.vocab` | None (leaf) |
| Substrate | `dillylang.operators`, `.combinators`, `.runner`, `.trace` | vocab |
| Analysis | `dillylang.skills`, `.recipes`, `.validation` | vocab, substrate |

Vocabulary layer has zero runtime dependencies. Adapter boundary between
vocabulary types and DSPy types lives in substrate layer.

---

## Key constraints

- No agent loops, runtime tool use, or autonomous behavior.
- Budget ceiling: 7 LLM calls. Sweet spot: 4-5.
- `synthesize` is highest-leverage prompt. Spend disproportionate time on it.
- Don't add operators without two independent recipe demands (ADR-007).
- Don't synthesize without curation past ~5 upstream artifacts.
- Steering parameters are declared schema fields; `bind` does typed currying (ADR-007).
- Code uses neutral names (`Operator`, `Pipeline`, `Context`). Cooking metaphor is for docs only.
