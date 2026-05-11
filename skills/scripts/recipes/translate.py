"""Translate a Claude Code skill directory into a Dillylang recipe description.

5-step evaluative pipeline: decompose the skill's contract, rotate each stage
into Dillylang vocabulary, classify execution model + recipe shape, evaluate
vocabulary fit, then synthesize a recipe.

Input: {"skill_source_bundle": "<ingested skill content as JSON string>"}
"""

# Vocabulary reference embedded in rotate prompt (canonical source: spec/INDEX.md §4)
_VOCABULARY = """\
OPERATORS (thinking moves that transform artifacts):
- decompose: break into axioms, derivations, assumptions
- synthesize: integrate multiple artifacts into coherent proposal
- invert: find what guarantees failure (Munger/Jacobi inversion)
- rotate: change the axis of inquiry or viewpoint
- analogize: find structural analogies in other domains
- abstract: extract general principles from concrete instances
- concretize: produce concrete instances from abstract principles
- constrain: narrow the solution space with explicit boundaries
- relax: widen the solution space by removing constraints
- evaluate: judge an artifact against an explicit criterion
- rank: order artifacts by criteria (returns IDs only)
- compare: side-by-side comparison of two artifacts
- classify: assign labels from taxonomies

COMBINATORS (compose operators into pipelines):
- pipe: sequential — output of step N feeds step N+1
- parallel: fan-out/fan-in — same input to multiple operators, collect results
- bind: typed currying — fix steering parameters at compose time
- map: apply an operator to each item in a collection
- filter: keep/drop items based on operator verdict (pass/partial=keep, fail=drop)
- branch: conditional dispatch — classify then route to sub-pipelines

A recipe is expressed as nested combinator calls, e.g.:
  pipe(parallel(decompose, invert, rotate), synthesize)"""

recipe = {
    "name": "translate",
    "version": 1,
    "description": "Translate a Claude Code skill into a Dillylang recipe description",
    "steps": {
        "decompose": {
            "operator": "decompose",
            "prompt": """\
Decompose this skill's behavioral contract. You are analyzing a Claude Code \
skill directory — not running the skill, not summarizing it.

Focus on: entrypoints (slash commands, triggers), inputs (what the skill reads \
or receives), outputs (what it produces or writes), stages (the discrete \
processing steps), assumptions (what it expects from runtime, user, or tools), \
and control flow (branching, looping, parallelism, sub-agent dispatch).

Axioms are the load-bearing behavioral commitments — things the skill MUST do \
to be itself. Derivations follow from axioms with explicit dependency chains. \
Assumptions are implicit contracts treated as true without justification.

Be ruthless. Three sharp axioms beat ten soft ones.

If a file is a script, decompose what the script does, not what the SKILL.md \
says about it. Prose descriptions lie; code doesn't.

Output schema — produce a JSON object with:
  axioms: [{statement, justification}, ...]
  derivations: [{claim, depends_on: [...]}, ...]
  assumptions: [{statement, load_bearing: bool, testable: str}, ...]""",
        },
        "rotate": {
            "operator": "rotate",
            "prompt": f"""\
Reframe this skill's workflow stages as Dillylang operators and combinators.

Target frame (the complete vocabulary):
{_VOCABULARY}

For each identifiable stage or behavior in the skill, produce a rotation that \
restates it as a Dillylang expression. Name the source stage in `new_axis`, \
the Dillylang expression in `restated_problem`.

Explicitly probe for the implicit subject: what is this skill centering, and \
what does the Dillylang reframing center instead?

`what_becomes_visible` should name vocabulary affordances gained by the \
reframing — composability, typed artifacts, explicit axes. `what_recedes` \
should name skill behavior that the vocabulary cannot capture — tool use, \
runtime state, agent loops, file I/O.

Classify each rotation as `axis_change` (the Dillylang expression captures \
the same cognitive move) or `viewpoint_change` (the reframing shifts what's \
emphasized but doesn't capture the move).

Output schema — produce a JSON object with:
  original_axis: str
  rotations: [{{new_axis, rotation_kind, restated_problem, what_becomes_visible: [...], what_recedes: [...]}}, ...]""",
        },
        "classify": {
            "operator": "classify",
            "prompt": """\
Classify this skill along two taxonomies.

execution_model — how does the skill execute?
  - Model A: fully automated pipeline, no human in loop
  - Model B: human-in-the-loop at decision points
  - Model C: in-session execution by the agent LLM, step-by-step with
    visible intermediate artifacts
  - agentic: autonomous agent with tool use, looping, self-direction
  - hybrid: combines multiple execution models

recipe_shape — what is the skill's high-level structure?
  - generative: diverge-curate-converge (fan out perspectives, then synthesize)
  - evaluative: characterize-judge-render (analyze then assess fit)
  - canonization: convert external artifact to canonical internal form
  - verification: check claims against evidence
  - orchestration: coordinate multiple sub-processes or agents
  - other: none of the above — explain in rationale

Each classification must include a rationale naming the specific evidence \
from the skill's content. "It seems like X" is not a rationale — name the \
file, pattern, or behavior that supports the label.

Output schema — produce a JSON object with:
  classifications: [{taxonomy, label, rationale, confidence}, ...]""",
        },
        "evaluate": {
            "operator": "evaluate",
            "prompt": """\
Judge whether this skill's load-bearing behavior is expressible in Dillylang \
vocabulary.

Criterion: All load-bearing behavior in this skill is expressible using \
Dillylang operators, combinators, artifacts, and execution-model vocabulary \
without changing semantics.

The question is NOT "can we roughly describe this skill using Dillylang \
words." The question is: "can every behavior that makes this skill itself — \
not decoration, not implementation detail — be captured by a composition of \
Dillylang operators and combinators without losing semantics?"

Produce a verdict:
  - pass: all load-bearing behavior maps to vocabulary
  - partial: core thinking moves map, but some structural behavior (tool use, \
    looping, agent dispatch) does not
  - fail: the skill's core value cannot be expressed in the vocabulary

Evidence must be specific. Each item should name a concrete skill behavior \
and state whether it maps or doesn't.

Most skills will be `partial` — that's informative, not a failure. The \
residue (what doesn't fit) is the most valuable output of this step.

Output schema — produce a JSON object with:
  criterion: str
  verdict: "pass"|"partial"|"fail"
  evidence: [str, ...]
  rationale: str
  confidence: "low"|"medium"|"high" """,
        },
        "synthesize": {
            "operator": "synthesize",
            "prompt": """\
Synthesize the four upstream analyses into a self-contained Dillylang \
translation. This output IS the product — it must stand alone without \
requiring the reader to consult upstream step outputs.

You have all prior step outputs as your input:
  - decompose: the skill's structural contract (axioms, derivations, assumptions)
  - rotate: each skill stage restated as Dillylang expressions
  - classify: execution model and recipe shape labels
  - evaluate: vocabulary fit verdict with evidence and residue

Produce a single JSON object containing:

  1. `dillylang_recipe` — the skill expressed as nested combinator calls \
using ONLY valid operator and combinator names (pseudocode, not Python)
  2. `recipe_operators` — list of operators used
  3. `recipe_combinators` — list of combinators used
  4. `execution_model` — from classify (Model A/B/C/agentic/hybrid)
  5. `recipe_shape` — from classify (generative/evaluative/verification/etc.)
  6. `stage_mapping` — from rotate: each skill stage mapped to a Dillylang \
expression with fit assessment. Include ALL rotations.
  7. `residue` — from evaluate: every behavior that does NOT map to \
vocabulary. Each item names the feature and why it doesn't fit. This is the \
highest-value section — it tells us where the vocabulary has gaps.
  8. Standard synthesize fields: proposal, incorporates, tradeoffs, \
open_questions, conflicts_addressed, confidence

Anti-instruction: if your proposal feels like a weighted average, you have \
not synthesized — you have summarized. Try again.

Each upstream artifact must be acknowledged with a contribution OR deferred \
to open_questions. Silent dropping is forbidden.

Concrete tradeoffs only. "Balance flexibility and structure" is rejected.

The recipe should reflect what the skill DOES, not what we wish it did. If \
the evaluate step found residue, the recipe should acknowledge the gap, not \
paper over it with approximate operators.

Output schema — produce a JSON object with:
  proposal: {statement, rationale}
  dillylang_recipe: str
  recipe_operators: [str, ...]
  recipe_combinators: [str, ...]
  execution_model: str
  recipe_shape: str
  stage_mapping: [{source_stage, dillylang_expression, fit: "direct"|"approximate"|"outside_vocabulary", notes}, ...]
  residue: [{feature, why_it_does_not_fit}, ...]
  incorporates: [{source_artifact_id, contribution}, ...]
  tradeoffs: [{gained, given_up}, ...]
  open_questions: [str, ...]
  conflicts_addressed: [{conflict, resolution}, ...]
  confidence: "low"|"medium"|"high" """,
        },
    },
    "flow": ["decompose", "rotate", "classify", "evaluate", "synthesize"],
}
