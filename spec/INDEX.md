---
id: dillylang::spec-index
description: Design specification for the Dillylang reasoning vocabulary
tags: [design, spec, vocabulary]
created: 2026-04-30
status: active
---

# Dillylang — Formal Reasoning Vocabulary

> **Lean reference:** [`spec/PRIMER.md`](PRIMER.md) — schemas, combinators, and
> constraints in ~350 lines. This file is the full spec with design rationale,
> history, and open questions.

## 1. Project intent

A typed vocabulary of orthogonal thinking moves (operators), composable
into recipes runnable by a human, a model, or a pipeline:

```python
refine = pipe(decompose, parallel(invert, rotate), synthesize)
result = refine.run({"problem": "..."})
```

Each step produces structured output. Every pipeline run emits an
inspectable trace by default; persisting traces is optional.

### Single design principle

> **Maximize coverage of orthogonal axes of thought, subject to a depth budget.**

Every design decision is in service of this principle.

### What this is NOT

- Not an agent framework. No agent loops, tool use, or autonomous behavior.
- Not a chat interface. Recipes are constructed deliberately.
- Not a research project. The aim is weekly use on real problems.

### Relationship to existing skills

The operator's existing Claude skills (lateral-shift, phase-doc-review,
others) are Model C executions of pantry compositions — natural-language
descriptions of multi-step reasoning pipelines given to a strong LLM,
executed in a single context with structured intermediates. The pantry
vocabulary describes what well-designed skills already do.

This project's v0 is a Model A runtime for the same vocabulary, providing
trace ergonomics, targeted prompt iteration, currying, and cheaper-model
deployments that Model C does not offer. Skills become both reference
implementations and integration benchmarks for v0.

### Differentiation

The space is more crowded than it first appears. Closest prior art:

| System | Relationship |
|---|---|
| **DSPy** (Stanford NLP) | First substrate. Provides `Signature`, `Module`, `ChainOfThought`. The vocabulary is substrate-agnostic; DSPy is one implementation. |
| **MeMo** (arXiv 2402.18252) | Most direct conceptual prior art. Munger's latticework as prompting. Prompt-level, not typed+compositional. |
| **miltonian/principles** | First-principles agent generator. Single-framework; no composition layer. |
| **TRIZ-GPT, AutoTRIZ** | Single-framework operationalization (TRIZ). |
| **OpenLM/OpenOperator** (arXiv 2511.11712) | Reasoning as iterative operator application. Theoretical kin; different focus. |
| **Pehlke & Jansen** (Nov 2025) | Modular LLM pipeline with swappable framework modules. Closest architectural pattern. |
| **Multi-agent debate / persona crews** (CrewAI, AutoGen) | Treat thinking moves as personas, not typed functions. |

Our differentiation:

1. **Curated operator library** organized along orthogonal axes (~6 axes in v0; ~10 mother operators across v0 and v1).
2. **Currying / partial application** as a first-class affordance.
3. **Conflict detection** between framework outputs as a pipeline artifact (v1).
4. **Three-tier pantry** (transformers / judges / combinators).
5. **Trace ergonomics** — every run produces an inspectable artifact.

---

## 2. Conceptual model

### Cooking metaphor (user-facing, docs)

| Cooking | System |
|---|---|
| Technique | Operator |
| Ingredient | Input artifact |
| Mise en place | Context preparation; currying; binding |
| Recipe | Pipeline definition |
| Dish | Pipeline output |
| Tasting | Trace inspection |
| Pantry | Operator library |
| Kitchen | Runner / runtime |
| Mother sauce | Foundational operator |

### Geometric framing (design diagnostic)

Problems live as points in a high-dimensional idea space. Operators are
geometric operations on that space:

| Operator | Geometric operation | Axis |
|---|---|---|
| `decompose` / `synthesize` | Basis decomposition / tensor-product-with-projection | compositionality |
| `invert` | Reflection across a hyperplane | valence |
| `rotate` | Change of basis | frame |
| `analogize` | Diffeomorphism to another manifold | substrate |
| `abstract` / `concretize` | Movement along abstraction gradient | abstraction |
| `constrain` / `relax` | Movement along feasibility gradient | feasibility |

The geometric framing is **diagnostic, not literal**. It earns its keep through:

- **Orthogonality test:** does a new operator candidate move along an axis
  no existing mother covers?
- **Recipe-level metrics:**
  - `coverage(R)` = number of orthogonal axes touched
  - `depth(R)` = critical path length through the pipeline — the number
    of sequential steps, where `parallel` counts as 1 regardless of
    branch count. Measures structural complexity and latency.
  - `cost(R)` = total LLM calls — a `parallel` of two operators counts
    as 2. This is what the budget ceiling (7 calls) constrains.
  - `cost_efficiency(R)` = coverage / cost (resource-oriented: are we
    using LLM calls well?)
  - `depth_efficiency(R)` = coverage / depth (structural: are we
    getting breadth without excessive sequential depth? Substrate-
    independent — depth stays constant across runtimes while cost
    may differ.)
  - `efficacy(R)` = non-trivial contributions / upstream artifacts
    (result-oriented: did each step actually improve the output? Measured
    from traces via the `synthesize` operator's `incorporates` field.)
  - `effectiveness(R)` = did the output solve the real problem?
    (Not automatable from traces — requires operator feedback. The
    persisted larder (§14, open question 4) is where effectiveness data
    would eventually live: operators annotating past traces with outcome
    judgments.)

  The measures form a hierarchy: efficiency (both forms) asks whether
  we spent well, efficacy asks whether the pipeline helped, effectiveness
  asks whether the result mattered. Only the first three are computable
  at v0.

  These metrics are debugging instruments, not optimization targets. A
  high-coverage recipe that contributes nothing non-trivial to synthesis is
  worse than a lower-coverage recipe that changes the answer. Use coverage,
  cost, depth, cost_efficiency, depth_efficiency, and efficacy to inspect
  recipe behavior; use operator feedback and real outcomes to judge
  effectiveness.

- **Saturation insight:** ~6 orthogonal axes in v0 (compositionality,
  valence, frame, substrate, abstraction, feasibility). Evidence axis
  deferred to v1. Recipes should aim for 3–5 well-chosen steps. Past ~7,
  drift dominates.

### Code naming

Use neutral names in code (`Operator`, `Pipeline`, `Context`, `Trace`).
The cooking metaphor lives in docs and conversation, not in class hierarchies.

---

## 3. Core types

### Artifact

The unit of data flowing between operators:

```python
class Artifact:
    id: str              # unique within a pipeline run
    operator: str        # which operator produced this
    step_index: int      # position in pipeline
    data: dict[str, Any] # the operator's structured output
    status: "success" | "repair_succeeded" | "failed" | "partial"
    errors: list[ItemError] | None  # per-item errors for collections

class ItemError:
    item_id: str         # id of the failed item
    error_kind: str      # e.g. "parse_failure", "llm_error", "predicate_error"
    message: str
```

The `status` field tracks per-artifact outcome. Combinators that tolerate
partial failure (`parallel`, `map`, `filter`) set `status: "partial"` and
populate `errors` with per-item details so downstream operators (especially
`synthesize`) can see what was dropped and why. A single-item failure
(from a transformer or judge) uses a one-element `errors` list.

### RunResult

The canonical return type for every `.run()` call — operators, combinators,
and full pipelines all return this:

```python
class RunResult:
    output: Artifact | list[Artifact]  # single for operators, list for parallel/map
    trace: list[TraceEntry]
    status: "success" | "partial" | "failed" | "budget_exhausted"
    errors: list[ItemError] | None     # aggregated from artifacts
```

`status` reflects the worst outcome across all steps: if any step failed,
the overall status is at least `"partial"`. Callers inspect `output` for
the pipeline's final artifact(s) and `trace` for the full execution log.

### Operator

```python
class Operator[I, O]:
    name: str
    input_schema: Schema[I]
    output_schema: Schema[O]
    render: Callable[[I, Context], Prompt]
    parse: Callable[[LLMResponse], O]
    config: OperatorConfig  # model, temp, max_tokens, etc.

    def bind(self, **partial) -> Operator: ...
    def run(self, input: I, ctx: Context) -> RunResult: ...
```

### Context

```python
class Context:
    problem: str                    # immutable original input
    artifacts: dict[str, Artifact]  # keyed by "{operator_name}_{step_index}"
    trace: list[TraceEntry]
    budget: Budget
```

Artifact namespacing uses `"{operator_name}_{step_index}"` to handle
duplicate operator use within a pipeline (e.g. `decompose_0`, `decompose_4`).

### Dataflow contract

Each operator receives two things:

1. the current upstream value (`input`), and
2. the immutable run `Context`.

Operators may always read `Context.problem` as the original problem statement,
but their primary input is the upstream artifact or artifact collection passed
by the combinator.

Rules:

- A source operator with no upstream value receives the initial user input.
- `pipe` passes each step's output artifact to the next step.
- `parallel` passes the same upstream value to every branch and returns a
  collection of branch artifacts.
- `map` and `filter` operate on explicit collections. Recipe pseudocode may
  use selectors such as `select("assumptions")`; shorthand like
  `_.assumptions` is illustrative, not implicit runtime magic.
- Transformer operators (`invert`, `rotate`, `analogize`, etc.) should handle
  either the original problem or an upstream artifact by rendering both the
  artifact content and `Context.problem` into the prompt.
- `synthesize` accepts either a single artifact or a collection of artifacts.
  It must acknowledge every upstream artifact by id or explicitly defer it to
  `open_questions`.

### Identity and provenance invariant

Runtime-owned artifact identity is authoritative. When an LLM refers to
existing artifacts, it should emit artifact ids or derived fields, not
regenerated copies of upstream artifacts. The runtime is responsible for
resolving ids to artifacts, preserving original data, and recording
provenance in the trace.

This applies especially to selection and judgment operators such as
`rank`, `filter`, future `classify`, and future `compare`. LLMs may
transform content when transformation is the operator's purpose, but they
should not re-materialize source objects merely to refer to them.

### TraceEntry

```python
class TraceEntry:
    trace_id: str        # unique within a pipeline run (e.g. uuid or monotonic)
    event_type: "llm_call" | "combinator_start" | "combinator_end" | "selector"
    operator_name: str
    step_index: int
    timestamp: datetime
    status: "success" | "repair_succeeded" | "failed" | "partial"

    # present for llm_call events
    input: Any | None
    rendered_prompt: str | None
    raw_response: str | None
    parsed_output: Any | None
    tokens_used: int | None
    latency_ms: int | None

    # present for combinator_start/combinator_end events
    children: list[str] | None   # trace_ids of child entries

    # present for selector events
    field: str | None            # e.g. "assumptions"
    selected_count: int | None
```

Trace event types:
- **`llm_call`:** an operator that called the LLM. Has prompt, response,
  tokens, latency. The 13 LLM-bearing operators (9 transformers + 4 judges)
  produce these.
- **`combinator_start` / `combinator_end`:** structural markers emitted by
  `pipe`, `parallel`, `map`, and `filter`. Wrap their children's entries.
  `combinator_end` carries the aggregate status (`partial` if any child failed).
- **`selector`:** emitted by `select()`. Records which field was extracted
  and how many items were selected. Lightweight but useful for debugging
  data flow between steps.

`bind` and `identity` are compile-time transforms — they do not appear in
the runtime trace. A bound operator traces as its underlying operator
(e.g. `bind(evaluate, criterion="X")` traces as `evaluate`).

Trace emission is default behavior: every pipeline run returns
`{ output, trace }`. Trace persistence is separate and opt-in unless a caller
configures a persistence sink. Because trace entries can include rendered
prompts, raw responses, and user-provided problem statements, persistent sinks
must support redaction and retention controls. Do not send traces to shared
logs by default.

### Budget

```python
class Budget:
    max_llm_calls: int    # ceiling: 7
    max_tokens: int       # ~30K total per pipeline
    max_wall_time_ms: int # 60_000
    llm_calls_used: int
    tokens_used: int
    elapsed_ms: int
```

Budget is per-pipeline. Individual operators cannot override the global
budget; they can only consume from it. For `parallel`, each branch
consumes independently (tokens and wall time measured per-branch, but
wall time is max-of-branches since they run concurrently).

---

## 4. Operator schemas

All operators emit structured output validated against a schema.
Repair-once-on-failure-then-fail-loud is the default.

### `decompose`

Separate what's load-bearing from what's assumed. Not a generic outline —
a search for axioms.

**Input:**

```json
{
  "focus": str | None
}
```

`focus` is an optional steering parameter. When bound (e.g.
`bind(decompose, focus="requirements, constraints, assumptions")`), it
narrows decomposition to the specified structural aspects. When unbound
(`None`), decompose performs general structural decomposition over the full
input. The upstream value (problem text or artifact) flows through the
implicit data channel per the dataflow contract (§3). Output schema is
unchanged regardless of binding. [[THIS is_grounded_by: urn:unique_reference:dillylang::adr-007]]

**Output:**

```json
{
  "axioms": [{ "statement": str, "justification": str }],
  "derivations": [{ "claim": str, "depends_on": [str] }],
  "assumptions": [{
    "statement": str,
    "load_bearing": bool,
    "testable": str
  }]
}
```

Prompt highlights:
- Identify axioms (foundational, not derivable), derivations (follow from
  axioms, with dependency list), and assumptions (treated as true without
  justification).
- "Be ruthless. Three sharp axioms beat ten soft ones."

Design decision (2026-04-30): the original handoff included an
`irreducibles` field (minimum statements to reconstruct the claim), but v0
excludes it from `decompose`. Rationale: `decompose` should expose structure;
`irreducibles` is a compression/projection operation that can be layered as a
post-processing step or promoted to a separate operator if recipes demand it.
This keeps `decompose` narrow while preserving the future option.

### `invert`

Munger/Jacobi inversion. Stop asking "how succeed" and ask "what
guarantees failure."

```json
{
  "anti_goals": [str],
  "failure_modes": [{
    "mode": str,
    "mechanism": str,
    "likelihood": "low" | "medium" | "high",
    "severity": "recoverable" | "costly" | "fatal",
    "preventable_by": str
  }],
  "near_misses": [str]
}
```

Prompt highlights:
- Require concrete mechanism descriptions.
- Reject generic risks ("market changes") that lack a specific causal chain.

### `rotate`

Change the axis of inquiry. Each rotation must name a new axis explicitly.

**Input:**

```json
{
  "target_frame": str | None
}
```

`target_frame` is an optional steering parameter. When bound (e.g.
`bind(rotate, target_frame="strongest_form_of_position")`), it names the
frame of reference to rotate toward. When unbound (`None`), rotate performs
open-ended frame exploration with the implicit-subject probe. The upstream
value flows through the implicit data channel per the dataflow contract
(§3). Output schema is unchanged regardless of binding.
[[THIS is_grounded_by: urn:unique_reference:dillylang::adr-007]]

**Output:**

```json
{
  "original_axis": str,
  "rotations": [{
    "new_axis": str,
    "rotation_kind": "axis_change" | "viewpoint_change",
    "restated_problem": str,
    "what_becomes_visible": [str],
    "what_recedes": [str]
  }]
}
```

Prompt highlights:
- Explicitly probe for the *implicit subject* of the original framing
  (who/what is being centered) and rotate to alternatives. This is where
  rotate's leverage lives (validated by WASI stress test).
- Instruct the model to classify each rotation as `axis_change` or
  `viewpoint_change` via the `rotation_kind` field. If this field starts
  doing real work, split `rotate` into two operators in v1.

### `analogize`

Map the problem to another domain that shares structural relationships.
Importing mechanism, not metaphor.

**Input:**

```json
{
  "domains": list[str] | None
}
```

`domains` is an optional steering parameter. When bound (e.g.
`bind(analogize, domains=["bio", "industry", "digital"])`), it
constrains the analogy search to specified source domains. When unbound
(`None`), analogize searches freely across domains. The upstream value
flows through the implicit data channel per the dataflow contract (§3).
Output schema is unchanged regardless of binding.
[[THIS is_grounded_by: urn:unique_reference:dillylang::adr-007]]

**Output:**

```json
{
  "problem_signature": str,
  "analogies": [{
    "domain": str,
    "analog": str,
    "mechanism_mapping": str,
    "transferable_insight": str,
    "stowaways": [str]
  }]
}
```

The `stowaways` field is critical — it forces the operator to surface what
about the target domain *doesn't* transfer cleanly. Without this, analogy
defaults to celebrating mappings and ignoring their limits.

### `synthesize`

The rebuild step. NOT a weighted average — if synthesis "feels like
averaging," the prompt has failed.

**Input contract:** `synthesize` receives the collected outputs from
the preceding step. When preceded by `parallel(op1, op2, ...)`, it
receives a list of Artifacts. Each artifact is referenced by its `id`
(e.g. `"invert_1"`, `"rotate_2"`). The synthesis prompt enumerates all
upstream artifacts and requires each to be acknowledged.

```json
{
  "proposal": { "statement": str, "rationale": str },
  "incorporates": [{ "source_artifact_id": str, "contribution": str }],
  "tradeoffs": [{ "gained": str, "given_up": str }],
  "open_questions": [str],
  "conflicts_addressed": [{
    "conflict": str,
    "resolution": "resolved" | "deferred" | "accepted_as_tradeoff"
  }],
  "confidence": "low" | "medium" | "high"
}
```

Prompt highlights:
- Anti-instruction: "If your proposal feels like a weighted average,
  you have not synthesized — you have summarized. Try again."
- Each upstream artifact must be acknowledged with a contribution OR
  deferred to `open_questions`. Silent dropping is forbidden.
- Concrete tradeoffs only. "Balance flexibility and structure" is rejected.

This is the highest-leverage prompt in the system. Spend disproportionate
time iterating on it.

**Schema extensibility.** The six base fields above form a minimum
integration contract, not a maximum output surface. Domain-specific
recipes may extend the synthesize output schema with additional top-level
keys (e.g. `recipe_structure` for design_recipe). Three rules govern
extensibility (ADR-006): [[THIS is_grounded_by: urn:unique_reference:dillylang::adr-006]]

1. **Base fields always required.** Every synthesize invocation — standard
   or extended — must populate all six base fields. These exist to force
   the hard cognitive work of integration; skipping them means the
   synthesis hasn't happened.
2. **Extensions are additive top-level keys.** They must not modify,
   reinterpret, or shadow base field type annotations. An extended schema
   is a strict superset of the base schema.
3. **Extension semantics belong to the recipe, not the operator.** The
   base prompt logic (acknowledge all upstream artifacts, forbid silent
   dropping, anti-averaging) is invariant. Extension fields get their own
   prompt section.

### `evaluate`

Judge an artifact against an explicit criterion. Conditional operator —
requires a criterion to be bound.

`criterion` is a required steering parameter: an unbound `evaluate` has
no criterion to judge against and should fail at input validation.
Formal input schema deferred to implementation per ADR-007.
[[THIS is_grounded_by: urn:unique_reference:dillylang::adr-007]]

```json
{
  "criterion": str,
  "verdict": "pass" | "partial" | "fail",
  "evidence": [str],
  "rationale": str,
  "confidence": "low" | "medium" | "high"
}
```

When used inside a `map`, the criterion is bound per-element:
`map(bind(evaluate, criterion="X"), dimensions)`.

### `rank`

Score and order artifacts by named criteria. Optionally return only top-K.

**Input:**

```json
{
  "artifacts": [Artifact],
  "criteria": [str],
  "top_k": int | null
}
```

**Output:**

```json
{
  "ranked": [{
    "artifact_id": str,
    "scores": { "<criterion>": "high" | "medium" | "low" },
    "rationale": str
  }],
  "top_k_ids": [str]
}
```

The LLM returns IDs only — never full artifacts. The runtime resolves
`top_k_ids` to original artifacts from context. This prevents the LLM
from mutating, fabricating, or partially echoing source artifacts.

### `classify`

Assign discrete labels from provided taxonomies. The router operator —
classify labels, `branch` dispatches. [[THIS is_grounded_by: urn:unique_reference:dillylang::adr-005]]

**Input:**

```json
{
  "taxonomies": dict[str, list[str]]
}
```

`taxonomies` is a required steering parameter: a mapping from taxonomy
name to a list of valid labels. An unbound `classify` has no taxonomy to
classify against and should fail at input validation. Multiple taxonomies
may be resolved in a single LLM call — splitting into separate calls
doubles the budget cost for no quality gain when taxonomies are related.

Taxonomies that cannot guarantee exhaustive coverage must include an
explicit escape label (`"other"`, `"unknown"`, `"none"`). Without an
escape label, the LLM will force a bad fit — a silent, hard-to-detect
failure mode.

**Output:**

```json
{
  "classifications": [{
    "taxonomy": str,
    "label": str,
    "rationale": str,
    "confidence": "low" | "medium" | "high"
  }]
}
```

**Design constraints:**

- **Single-label per taxonomy.** Each taxonomy produces exactly one
  classification. The runtime validates uniqueness on the `taxonomy` key.
  Multi-label classification is a different operation.
- **Closed-set labels.** The returned label must be a member of the
  taxonomy's label list. The runtime validates labels against the
  taxonomy. Invalid labels demote the result to `partial` status.
- **Rationale and confidence required.** Every classification includes
  both, following the judge-operator precedent established by `evaluate`.

**Relationship to other operators:** `classify` is to `evaluate` as
categorization is to judgment: `evaluate` produces `pass`/`partial`/`fail`
against a criterion, `classify` produces a label from a taxonomy. Unlike
`rank`, `classify` operates on a single artifact, not a collection.
`classify` + `branch` = the router pattern.

### `compare`

Pairwise relative judgment between two artifacts on a criterion.

**Input:**

```json
{
  "criterion": str
}
```

`criterion` is a required steering parameter. Like `evaluate`, comparison
without a criterion is invalid. The data channel carries exactly two
artifacts (pairwise only — N-way comparison is `rank`'s job).

**Output:**

```json
{
  "criterion": str,
  "winner": str,
  "rationale": str,
  "comparison_points": [{
    "dimension": str,
    "artifact_a_assessment": str,
    "artifact_b_assessment": str
  }],
  "confidence": "low" | "medium" | "high"
}
```

The `winner` field must be one of the two input artifact IDs or `"tie"`.
The runtime validates the winner against the input artifact IDs; an
invalid winner triggers the repair-once-then-fail-loud pattern.

Prompt highlights:
- Artifacts are presented as A/B pairs with their IDs.
- Dimension-by-dimension comparison before declaring a winner.

### `abstract`

Move up the abstraction gradient: extract general principles from
concrete instances. Abstraction axis upward.

No input model (no steering parameters per ADR-007 — add when two
independent recipe demands justify it).

**Output:**

```json
{
  "principles": [{
    "statement": str,
    "grounding": [str],
    "abstraction_level": str
  }],
  "source_pattern": str
}
```

Prompt highlights:
- Identify structural commonalities and governing mechanisms.
- `grounding` links each principle back to the concrete instances it
  was derived from.
- `source_pattern` captures the structural pattern connecting inputs.

### `concretize`

Move down the abstraction gradient: derive concrete instances from
abstract principles. Abstraction axis downward.

No input model (no steering parameters per ADR-007).

**Output:**

```json
{
  "instances": [{
    "description": str,
    "derivation": str,
    "constraints_applied": [str]
  }],
  "target_domain": str
}
```

Prompt highlights:
- Generate actionable instances grounded in a specific domain.
- `derivation` traces how each instance follows from the abstract input.
- `constraints_applied` records domain constraints that shaped the instance.

### `constrain`

Move along the feasibility gradient: tighten constraints to narrow the
solution space. Feasibility axis narrowing.

No input model (no steering parameters per ADR-007).

**Output:**

```json
{
  "constraints_added": [{
    "constraint": str,
    "justification": str,
    "impact": str
  }],
  "impact_on_solution_space": str,
  "tradeoffs": [{ "gained": str, "given_up": str }]
}
```

Prompt highlights:
- Surface implicit constraints first, then add new ones that eliminate
  bad-solution classes.
- `tradeoffs` uses the same gained/given_up structure as `synthesize`.
- Assess constraint interactions — new constraints may conflict with
  existing ones.

### `relax`

Move along the feasibility gradient: loosen constraints to widen the
solution space. Feasibility axis widening.

No input model (no steering parameters per ADR-007).

**Output:**

```json
{
  "constraints_removed": [{
    "original_constraint": str,
    "relaxation": str,
    "justification": str
  }],
  "new_possibilities": [str],
  "risks_introduced": [str]
}
```

Prompt highlights:
- Distinguish load-bearing constraints from conventional ones.
- `new_possibilities` enumerates what becomes achievable after relaxation.
- `risks_introduced` surfaces what could go wrong — relaxation is not free.

---

## 5. Pantry architecture

Three tiers, each with a distinct purpose.

### Tier 1: Transformers

Operate on problems and artifacts. Change problem-state along an axis.

| Operator | Axis | Direction | v0? |
|---|---|---|---|
| `decompose` | compositionality | reduce | v0 |
| `synthesize` | compositionality | recombine | v0 |
| `invert` | valence | flip sign | v0 |
| `rotate` | frame | change axis | v0 |
| `analogize` | substrate | change domain | v0 |
| `abstract` | abstraction | generalize | v0 |
| `concretize` | abstraction | specialize | v0 |
| `constrain` | feasibility | tighten | v0 |
| `relax` | feasibility | loosen | v0 |
| `bayesian_update` | evidence | update | v1 |

Six axes in v0 (compositionality, valence, frame, substrate, abstraction,
feasibility). Evidence axis deferred to v1.

### Tier 2: Judges

Operate on artifacts; produce meta-information.

| Operator | Output kind | v0? |
|---|---|---|
| `evaluate` | Graded judgment against criterion | v0 |
| `rank` | Ordered subset of artifacts | v0 |
| `classify` | Discrete label from taxonomy | v0 |
| `compare` | Relative judgment between artifacts | v0 |

`classify` is the router operator that enables automatic recipe
selection. `compare` provides pairwise relative judgment, complementing
`rank`'s N-way ordering.

### Tier 3: Combinators

Operate on other operators; compose them into pipelines.

**Pipeline combinators:**

| Combinator | Purpose | v0? |
|---|---|---|
| `pipe` | Sequential composition | v0 |
| `parallel` | Fan-out on same input | v0 |
| `bind` | Partial application / currying | v0 |
| `branch` | Conditional dispatch | v0 |
| `repeat` | Iterative loop with convergence | v1 |
| `ensemble` | Run N times, aggregate | v1 |
| `meta_critique` | Critique a recipe (not its output) | v1 |

**Collection combinators:**

| Combinator | Purpose | v0? |
|---|---|---|
| `map` | Apply op to each element | v0 |
| `filter` | Keep elements passing a predicate | v0 |
| `zip` | Pair two collections elementwise | v1 |
| `flatten` / `flatMap` | Collapse nested collections | v1 |
| `groupBy` | Partition by key | v1 |
| `unique` | Dedupe (with similarity judge) | v1 |

### v0 total: 19 operators

| Tier | Operators |
|---|---|
| Transformer | `decompose`, `synthesize`, `invert`, `rotate`, `analogize`, `abstract`, `concretize`, `constrain`, `relax` |
| Judge | `evaluate`, `rank`, `classify`, `compare` |
| Pipeline combinator | `pipe`, `parallel`, `bind`, `branch` |
| Collection combinator | `map`, `filter` |

---

## 6. Combinator semantics

### `pipe(op1, op2, ..., opN)`

Sequential composition. Each operator's output is fed to the next as input.
Returns a new operator with the composed input/output type.

### `parallel(op1, ..., opN)`

Fan-out. Each operator runs on the same input; outputs collected as a list
of Artifacts. Concurrent execution. Labels default to operator names; provide
explicit labels when using the same operator twice.

### `bind(op, **partial_input)`

Currying. Returns a new operator with the partial input pre-applied. The
new operator has a smaller input requirement.

### `map(op, collection)`

Applies `op` to each element of collection. Returns collection of outputs.
Concurrent by default.

### `filter(predicate_op, collection)`

Keeps elements where `predicate_op` returns a passing verdict. The predicate
is itself an operator (often `bind(evaluate, criterion="X")`). This means
`filter` implicitly invokes a judge — each element costs an LLM call.

Verdict mapping: `pass` => keep, `partial` => keep, `fail` => drop.
The rationale: `partial` means "not fully passing but not rejected" —
dropping it silently loses potentially useful signal.

Options:
- `keep_partial=false`: only `pass` keeps; `partial` and `fail` both drop.
- `fail_on_predicate_error=true`: promote any predicate LLM/API error
  to a combinator failure instead of silently dropping the item.

### `branch(taxonomy_name, routes, default)`

Conditional dispatch based on `classify` labels. The router combinator —
`classify` labels, `branch` dispatches to the matching route.

**Parameters:**

- `taxonomy_name: str` — which taxonomy's label to extract from the
  upstream artifact's `data.classifications` array.
- `routes: dict[str, pipeline_node]` — mapping from label to pipeline.
- `default: pipeline_node` — required fallback pipeline for unmatched
  labels or missing classifications. There is no implicit default;
  omitting `default` is a construction-time error.

**Semantics:**

1. Extract the `classify` label from the upstream artifact's
   `data["classifications"]` array matching `taxonomy_name`.
2. Look up the label in `routes`. If found, dispatch to that pipeline.
3. If the label is not in `routes`, or classifications are missing/empty,
   dispatch to `default`.
4. The selected route receives the branch's input artifact (the classify
   artifact), not the pre-classify original. This preserves the classify
   metadata for downstream operators.

**Composition pattern:** `branch` is typically preceded by `classify` in
a `pipe`:

```
pipe(
  bind(classify, taxonomies={"problem_type": ["strategic", "tactical", "operational"]}),
  branch("problem_type", {
    "strategic": wide_pass,
    "tactical": refine,
  }, default=refine)
)
```

`branch` emits `combinator_start` and `combinator_end` trace entries
wrapping the selected route's execution.

---

## 7. Failure semantics

### Per-operator failure

1. Validate input against `input_schema`. Fail immediately on invalid input.
2. Call LLM with structured-output mode.
3. Parse and validate output against `output_schema`.
   On parse failure: ONE repair retry with the validation error appended to
   the prompt, then fail loud.
4. On success: append to `context.artifacts`, append trace entry with
   `status: "success"` (or `"repair_succeeded"`).
5. On failure: append trace entry with `status: "failed"`, error details
   in `raw_response`.

### Pipeline failure policy (v0)

- **`pipe`:** short-circuits on failure. Returns partial trace up to and
  including the failed step. Downstream operators do not run.
- **`parallel`:** runs all branches. If any branch fails, the parallel step
  is marked as partial. Successful branch outputs are still available to
  downstream operators. The trace records which branches succeeded and
  which failed.
- **`map`:** same as `parallel` — individual element failures don't halt
  the map. Failed elements are omitted from the output collection.
- **`filter`:** predicate failure (LLM/API/schema error) is not the same as
  the predicate returning a normal "fail" verdict. v0 defaults to fail-closed:
  the item is not kept, but the artifact's `errors` list records the item id,
  `error_kind: "predicate_error"`, and message. If downstream synthesis runs
  after predicate errors, the synthesis input includes the error summary so
  dropped items are not invisible. `fail_on_predicate_error=true` promotes
  any predicate error to a combinator failure.

### Budget exhaustion

If budget is exhausted mid-pipeline, halt and return the partial trace.
The trace's final entry indicates budget exhaustion, not operator failure.

---

## 8. Recipe book

### v0 shipped recipes

These are executable, tested, and ship with the system.

### `refine`

```
refine = pipe(
  decompose,
  parallel(invert, rotate),
  synthesize
)
```

Touches 3 axes (compositionality, valence, frame). 4 LLM calls
(decompose + invert + rotate + synthesize). Coverage = 3, cost = 4,
depth = 3 (decompose → parallel → synthesize), cost_efficiency = 0.75,
depth_efficiency = 1.0.

Use case: most decision-support and design questions.

### `wide_pass`

```
wide_pass = pipe(
  parallel(decompose, invert, rotate, analogize),
  synthesize
)
```

Touches 4 axes (adds substrate). 5 LLM calls
(decompose + invert + rotate + analogize + synthesize). Coverage = 4,
cost = 5, depth = 2 (parallel → synthesize), cost_efficiency = 0.8,
depth_efficiency = 2.0.

Use case: strategic questions where framing might be wrong; problems
worth getting right.

### Porting sketches

Approximate ports of existing skills. Not yet executable — the actual
port will discover sharp edges. Included as design targets, not
acceptance-tested recipes.

### `lateral_shift_lite`

```
lateral_shift_lite = pipe(
  decompose,
  filter(bind(evaluate, criterion="load_bearing"), select("assumptions")),
  map(invert),
  parallel(
    map(bind(analogize, domains=["bio", "industry", "digital"])),
    identity
  ),
  bind(rank, criteria=["novelty", "feasibility", "synergy"], top_k=3),
  synthesize
)
```

Approximate port of the operator's existing lateral-shift skill. The
actual port will discover sharp edges.

Note: `identity` is an implicit passthrough primitive (returns its input
unchanged). Not counted in the 12 v0 operators — it's plumbing, not a
thinking move. `select(field)` extracts a named field from an upstream
artifact's data.

### Named patterns for v1

- `premortem` = `pipe(invert, decompose)` with temporal binding
- `steelman` = `bind(rotate, target_frame="strongest_form_of_position")`
- `red_team` = `pipe(bind(rotate, adversarial=true), invert, decompose)`
- `counterfactual` = `pipe(bind(rotate, perturbed_axis="..."), decompose)`

### Meta-recipe shapes

Two canonical shapes observed from skill reverse-engineering:

- **Generative:** `diverge -> curate -> converge` (lateral-shift uses this)
- **Evaluative:** `gather -> judge -> rank -> synthesize` (phase-doc-review uses this)
- **Canonization:** `extract claims -> route destination (operator-confirmed) -> judge fitness (destination-relative) -> rank -> synthesize patch-like text` (canonize_prose uses this; Model C only)

### Documentation canonization pattern

When turning exploratory prose, reviews, or riffs into durable project
documentation, use a conservative canonization shape:

`extract claims -> route destination (operator-confirmed) -> judge fitness (destination-relative) -> rank -> synthesize patch-like text (with target document context)`

This is a **Model C recipe** — cost is K + M + 3 LLM calls for K
input claims and M survivors, which exceeds the 7-call budget for any
non-trivial input. The five-stage structure is load-bearing (each stage
has a distinct responsibility that gets conflated in fewer stages), so
collapsing stages to fit Model A's budget would recreate the single-step
editorial judgment the pipeline exists to replace.

**Routing.** `classify` routes extracted claims to destinations: spec,
ADR, agent instructions, open question, archive, or discard. Routing
precedes fitness judgment because quality is destination-dependent — what's
"operational" for the spec differs from what's "operational" for an ADR.
The `classify` prompt must frame "discard" as a legitimate peer destination,
not a failure state. Routing is a recommendation for operator
confirmation, not automatic dispatch — this is the one stage where
human judgment adds more value than it costs. Enriching the classify
prompt with structural summaries (heading outlines) of each destination
document improves routing quality.
[[THIS is_grounded_by: urn:unique_reference:dillylang::adr-010]]

**Fitness gate.** After routing, each claim is judged against its
destination's bar. Evaluate per-dimension, not as a compound criterion —
LLMs anchor on the most salient dimensions (typically "durable" and
"operational") and satisfice on the rest. Spec claims must pass all
five dimensions (durable, operational, non-obvious, scoped, low-regret);
ADR claims need primarily durable + non-obvious; open questions need
only non-obvious + scoped. Claims that are merely inspirational,
duplicative, speculative, or misrouted should not be promoted.

**Synthesis.** The `synthesize` step receives the target document's
structure as context so output is directly integrable. Without this,
synthesis produces plausible additions that use different terminology
or propose nonexistent sections. Output is patch-like text (specific
additions to named sections of named documents), not standalone prose.

**Claim extraction.** Instruct `decompose` to extract claims with
their supporting reasoning attached (using the `justification` field),
not bare assertions. Argumentative prose builds claims through
sequential reasoning; extracting without justification strips the
inferential chain that makes claims valid.

This pattern is intentionally conservative: its job is to prevent
vibe-bloat while preserving useful design insight.
[[THIS is_grounded_by: urn:unique_reference:dillylang::adr-004]]

---

## 9. Execution models

The pantry vocabulary is the durable artifact. The execution model is a
runtime choice. Runtimes may differ in call structure, tracing, cost, and
latency, but they should preserve operator semantics, artifact provenance,
and recipe intent. Runtime work should make the same vocabulary more
useful, not smuggle in a different model of cognition.

### Model A — Discrete operators (v0)

Each LLM-bearing primitive operator is a separate LLM call with its own
prompt, structured output schema, and parsing step. Combinators compose
these primitives by piping outputs to inputs. (First implementation uses
DSPy as substrate; see §11.)

**Wins:** inspectability (per-step trace), targeted prompt iteration, currying,
reusable operators across recipes, cheaper-model per-step dispatch,
programmatic pipeline construction.

**Costs:** higher latency and token spend, schema bottlenecks between steps
may lose implicit knowledge, every step runs whether it adds value or not.

### Model B — Holistic execution (future)

The recipe is described in natural language to a single LLM call. The model
executes the whole pipeline in one pass.

**Wins:** output coherence (synthesis can reach back), lower cost and latency,
the model can skip non-load-bearing steps.

**Costs:** no per-step trace, hard to iterate on individual operators, harder
to curry, gated on the weakest model running the whole thing.

### Model C — Hybrid (existing skills)

One LLM call, but the model is instructed to emit structured intermediate
artifacts as it proceeds. Most of Model B's coherence plus most of Model A's
inspectability. The cost is trusting the model to faithfully emit intermediates.

**This is what well-written skills already are.** Both lateral-shift and
phase-doc-review decompose cleanly into pantry operators executed in Model C.

### v0 rationale

Model A for v0, not because it's superior, but because it teaches the most
during build. Discrete operators force confrontation with each step's failure
modes — invaluable design feedback. Operator prompts should be written to be
*liftable* into holistic prompts later (dual-purpose).

Model A outputs should be compared against existing skill outputs on the same
inputs. Disagreements are prompt-iteration signal.

---

## 10. Runner behavior

1. Validate input against `input_schema`.
2. Render prompt; call LLM with structured-output mode.
3. Parse output; validate against `output_schema`.
   On parse failure: ONE repair retry, then fail loud.
4. Append parsed output to `context.artifacts` (keyed by
   `"{operator_name}_{step_index}"`).
5. Append trace entry.
6. Deduct budget (tokens used, wall time elapsed, LLM call count).
7. If budget exhausted, halt and return partial trace.

No agent loops at this layer. No reflection at this layer. If reflection
or critique is needed, it's a separate operator (`meta_critique`, v1)
or a separate stage in the recipe.

### Budget defaults

```
floor:        3 LLM calls (minimum viable pipeline, e.g. decompose + synthesize
              + one axis move; does NOT enforce minimum coverage)
sweet_spot:   4-5 LLM calls (3-4 axes + synthesis, near-saturation)
ceiling:      7 LLM calls (drift dominates past this)

max_tokens:       ~30K total per pipeline
max_wall_time:    60s
synthesis_calls:  1 final per pass
```

### Substrate

The vocabulary (types, schemas, composition rules) has no runtime
dependencies. Substrates implement the `OperatorProtocol` and provide
the LLM-calling machinery.

---

## 11. DSPy substrate appendix

DSPy is the first substrate for the Dillylang vocabulary.
[[THIS is_grounded_by: urn:unique_reference:dillylang::adr-001]]

- Each `Operator` is implemented as, or as a thin wrapper around, a
  `dspy.Module`.
- Each operator's input/output contract maps to a `dspy.Signature` plus local
  schema validation where DSPy's type system is not strict enough.
- `pipe`, `parallel`, `map`, and `filter` are library combinators over DSPy
  modules.
- `bind` returns a new module/operator with prefilled signature fields.
- `dspy.Predict` is the default underlying LLM call wrapper.
- DSPy's trace/inspection facilities are the first foundation for the trace
  viewer, augmented as needed to emit the project `TraceEntry` shape.

The adapter boundary between vocabulary types and DSPy types lives in
the substrate layer. Vocabulary code never imports DSPy.

> **Note:** The original 7-session implementation roadmap was extracted to
> [`.planning/future/7-session-build-guide.md`](../.planning/future/7-session-build-guide.md)
> during Phase 1 spec reorganization (D-02). See that file for build order
> and implementation provenance.

---

## 12. v1 priority list

Ranked by leverage. Items marked [DONE] were implemented in Phase 2.

1. ~~**`classify`**~~ [DONE] — router operator with closed-set taxonomy
   labels, ADR-005 runtime validation.
   [[THIS is_grounded_by: urn:unique_reference:dillylang::adr-005]]
2. ~~**`abstract` / `concretize`**~~ [DONE] — abstraction-axis moves
   with independent prompts.
3. **`repeat`** — iterative refine with convergence detection.
4. ~~**`branch`**~~ [DONE] — conditional dispatch based on classify
   labels. Together with classify they form the router pattern.
5. ~~**`constrain` / `relax`**~~ [DONE] — feasibility-axis moves with
   independent prompts.
6. **Coherence/conflict detection** as a synthesis input.
7. ~~**`compare`**~~ [DONE] — pairwise relative judgment with winner
   validation. **`zip`** — small win; cheap.
8. **`bayesian_update`, `meta_critique`, `ensemble`** — specialized; add on demand.

---

## 13. Design notes

### Three principles

1. **Operators are functions.** Small, pure-ish, individually testable.
   All interesting behavior emerges from composition. If you find yourself
   building a clever operator, it's probably two operators.
2. **Synthesis is the hardest step.** Most failures live here.
   Disproportionate prompt-engineering effort goes here.
   `Synthesize` is the pipeline's integration boundary, not a summarizer.
   Upstream operators create orthogonal pressure; synthesis must preserve
   named contributions, surface conflicts, and make explicit tradeoffs. If
   pipeline quality differences disappear at synthesis, improve the synthesis
   prompt before adding operators.
3. **Traces are the killer feature.** Everything is debuggable, every
   run is inspectable, and inspection is cheaper than re-running.

### Orthogonality test for new operators

Before adding any operator to the pantry:
- Does it move along an axis no existing mother covers? -> mother candidate.
- Is it a fixed sequence of existing operators? -> derivative; add to recipe book.
- Does it operate on operators rather than artifacts? -> combinator.

### Self-application as diagnostic

Operating an operator on itself surfaces hidden conflations:
- `rotate(rotate)` revealed the axis-change vs. viewpoint-change conflation.
- `rotate(analogize)` revealed the missing `stowaways` field.
Keep this as a recipe-design move.

### Anti-patterns

- **Don't pad operators with config flags.** If it does too many things, split it.
- **Don't synthesize without curation.** Past ~5 upstream artifacts,
  synthesis devolves into averaging. Use `rank` or `filter` first.
- **Don't add operators speculatively.** Wait for actual recipes to demand them.
- **Don't overuse the cooking metaphor in code.** It's vocabulary, not architecture.

---

## 14. Open questions

1. **Evaluation methodology.** "Is this output good?" has no clean metric.
   v0 relies on trace inspection. Consider semi-automated quality scoring
   once enough traces exist.
2. **`rotate` split.** Whether to split into `rotate_axis` and
   `rotate_viewpoint` based on `rotation_kind` field usage over time.
3. **Iteration / convergence semantics.** How to detect iterative refine
   convergence. Probably embedding-distance + LLM judgment; needs empirical
   tuning with `repeat` in v1.
4. **Persisted larder.** Saving traces and artifacts across sessions.
   This is also where effectiveness data would live — operators annotating
   past traces with outcome judgments ("this helped" / "this missed the
   point"). Connects to the effectiveness metric in §2.
   External framing: an observation from BR's portfolio (PA repo)
   positions the larder as the bridge from the *recipe-execution layer*
   (where the current vocabulary lives) to a *project-execution layer*
   above it — with GSD as the worked example of what that project layer
   contains (phase gates, atomic checkpoints, wave-based DAG execution,
   cross-AI convergence loops, persistent premise artifacts). Reading
   the larder this way shifts it from "save traces for later" to
   "substrate for cross-recipe project orchestration." Concrete
   candidate combinators surfaced: `phase_gate`, `wave_pipeline`,
   `checkpoint`, plus `repeat` (already on v1 priority list). See
   `~/devel/pa/docs/observations/2026-05-10-gsd-as-project-layer-above-dillylang-recipe-layer.md`.
   [[THIS is_inspired_by: urn:unique_reference:pa::obs-2026-05-10-gsd-dillylang-layer-stack]]
5. **Multi-model dispatch.** Different operators on different models
   (e.g. synthesis on a stronger model). Needs cost data first.
6. **User-facing recipe DSL.** v0 uses Python composition. YAML or DSL
   form for non-developers is a v2+ question.
7. **Pantry vocabulary in skill design.** Should new skills explicitly name
   their pantry recipe? What's the standard format?
8. **Additional substrates.** DSPy is the first substrate. The vocabulary
   layer is substrate-agnostic by design; additional substrates are a
   future option if recipes demand them.
9. **Input quality / question engineering.** [PARTIALLY ADDRESSED] The
   input validation gate has been implemented as a heuristic warning in
   `BaseDSPyOperator.run()`. The gate detects noun-phrase-only inputs
   (lacking verbs or question structure) and adds `input_warning` to
   `call_metadata` — it warns but never rejects. This addresses
   mitigation option (b) from the original design discussion: a
   lightweight runtime heuristic that surfaces suspect inputs without
   blocking execution. Operator prompt anchoring (option a) — designing
   prompts that work well even with bare noun phrases — remains a
   complementary per-operator concern addressed during prompt iteration.

---

## 15. Decision records

Durable design decisions with full rationale live in `docs/decisions/`:

- [001 — DSPy as v0 substrate](../docs/decisions/001-dspy-as-v0-substrate.md)
  — why DSPy, what it owns vs. what the project runner owns, reversal criteria. [[THIS is_grounded_by: urn:unique_reference:dillylang::adr-001]]
- [002 — Trace emission default, persistence optional](../docs/decisions/002-trace-emission-default.md)
  — traces always built in RunResult, persistence opt-in, privacy model. [[THIS is_grounded_by: urn:unique_reference:dillylang::adr-002]]
- [003 — Irreducibles excluded from v0 decompose](../docs/decisions/003-irreducibles-excluded-from-decompose.md)
  — why decompose is narrower than the original handoff, future options. [[THIS is_grounded_by: urn:unique_reference:dillylang::adr-003]]
- [004 — Canonization gate for durable documentation](../docs/decisions/004-canonization-gate.md)
  — conservative gate for promoting exploratory prose into canonical docs; strengthens classify as v1 priority. [[THIS is_grounded_by: urn:unique_reference:dillylang::adr-004]]
- [005 — Classify operator schema](../docs/decisions/005-classify-operator-schema.md)
  — output schema, taxonomies input contract, single-label/closed-set design constraints, judge-operator precedent. [[THIS is_grounded_by: urn:unique_reference:dillylang::adr-005]]
- [006 — Synthesize schema extensibility](../docs/decisions/006-synthesize-schema-extensibility.md)
  — base fields are minimum integration contract; extensions are additive top-level keys that must not shadow base fields. [[THIS is_grounded_by: urn:unique_reference:dillylang::adr-006]]
- [007 — Operator input schemas: steering parameters](../docs/decisions/007-operator-input-schemas-steering-parameters.md)
  — formalizes focus, target_frame, criterion, domains as declared schema fields; bind does typed currying. [[THIS is_grounded_by: urn:unique_reference:dillylang::adr-007]]
- [008 — Depth / cost metric split](../docs/decisions/008-depth-cost-metric-split.md)
  — splits conflated `depth` into `depth` (critical path) and `cost` (total LLM calls); efficiency splits into cost_efficiency (coverage/cost) and depth_efficiency (coverage/depth). [[THIS is_grounded_by: urn:unique_reference:dillylang::adr-008]]
