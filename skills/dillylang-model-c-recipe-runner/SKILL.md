---
name: dillylang-model-c-recipe-runner
description: Execute Dillylang recipes with visible step-by-step traces and intermediate artifacts. Use when the user wants to run, apply, or execute any named Dillylang recipe on a problem — including informal phrasing like using a recipe name as a verb.
---

Execute Dillylang recipes in-session as a Model C runtime.

A Model C execution is **not** just applying the recipe shape and giving the final answer.
It must produce visible intermediate artifacts for each operator/combinator step.
Every step must be auditable, artifacts named consistently (`{operator}_{step_index}`),
curation decisions shown, and final synthesis grounded in the intermediate artifacts.

## When to use

- Execute, run, or apply a Dillylang recipe (by name or informally as a verb)
- "execute the refine recipe on X", "run shortlist on these options", "let's reduce this", "refine this problem"

## When not to use

- Implement a recipe in Python/DSPy code
- Run the actual DSPy/Python runtime or CLI
- Inspect traces from a saved `RunResult`
- Discuss a recipe abstractly without executing it

## Before executing

1. **Read the recipe definition.** Look in `workspace/recipes/<name>.md` first, then `spec/INDEX.md` §8 for shipped recipes (`refine`, `wide_pass`). If the recipe is not found, ask the user.
2. **Read operator output fields.** Read `references/operator-output-fields.md` (bundled with this skill) for a compact listing of every operator's output field names. This is your primary schema reference during execution. For full descriptions or steering parameters, consult `spec/INDEX.md` §4.

## Output structure

Use this shape for every execution:

```
## Recipe
<recipe definition — paste the pipeline from the recipe file>

## Input artifact
artifact_id: input_0
data: ...

## Trace

### Step N — `<operator-or-combinator>` [with bound param=value if applicable]
Input: <artifact_id(s)>
Output artifact: <artifact_id>
<YAML matching the operator's schema from spec §4>

...

## Final synthesis
<grounded in the trace artifacts>

## Reflection
<2-3 sentences: which steps changed the answer, where steps converged
or conflicted, what the recipe structure surfaced that sequential
thinking would have missed>
```

## Combinator trace rules

### pipe

Show each step sequentially. Output of step N is input to step N+1.

### parallel

Show fan-out and fan-in:
- Shared input artifact
- Each branch operator and its output artifact
- Collected artifact list passed downstream

### bind

Not a runtime step. Mention bound parameters on the operator that uses them:
`Step 1 — decompose with bound focus="requirements, assumptions"`

### branch

Show: classification artifact, taxonomy used, selected label, selected route (or default).

### map

Show: collection input, per-item operator application, successes/failures, output collection.

### filter

Show: filter criterion/cutoff, kept artifact IDs, discarded artifact IDs, reason for each discard.

### rank

Show: ranking criteria, candidate IDs, ordered IDs, short rationale. Returns IDs only — never full artifacts.

## Format anchor

This is what a well-formed operator trace step looks like (using `synthesize` as example):

```yaml
artifact_id: synthesize_3
data:
  proposal:
    statement: ...
    rationale: ...
  incorporates:
    - source_artifact_id: invert_1
      contribution: ...
  tradeoffs:
    - gained: ...
      given_up: ...
  open_questions:
    - ...
  conflicts_addressed:
    - conflict: ...
      resolution: resolved|deferred|accepted_as_tradeoff
  confidence: low|medium|high
```

Every operator step should follow this pattern: `artifact_id`, `data`, then YAML fields matching the operator's schema. Read the specific schema from the spec — don't guess.
