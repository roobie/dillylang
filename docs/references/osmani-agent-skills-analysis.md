---
id: dillylang::ref-osmani-agent-skills
description: Canonization gate analysis of Addy Osmani's "Agent Skills" post — extracted claims routed to Dillylang vocabulary
tags: [vocabulary-design, recipe-patterns, anti-rationalization, external-reference]
created: 2026-05-05
status: active
---

# Canonization Gate: Addy Osmani — "Agent Skills"

[[THIS is_grounded_by: urn:unique_reference:dillylang::spec-index]]
[[THIS is_grounded_by: urn:unique_reference:dillylang::adr-007]]

## Provenance

| Field | Value |
|---|---|
| Source | <https://addyosmani.com/blog/agent-skills/> |
| Author | Addy Osmani (Google, Cloud/Gemini) |
| Published | 2026-05-03 |
| Fetched | 2026-05-05 |
| Method | `crwl -o markdown` → canonization gate recipe |
| Recipe applied | `decompose → classify → filter → evaluate → rank → synthesize` |
| Related repo | <https://github.com/addyosmani/agent-skills> (MIT, ~26K stars at time of writing) |

## Step 1: Decompose — discrete claims

| # | Claim |
|---|---|
| 1 | A skill is a *workflow* (steps + exit criteria), not reference documentation or essays |
| 2 | "Process over prose" — workflows are agent-actionable; essays are not |
| 3 | Anti-rationalization tables: pre-written rebuttals to plausible-sounding justifications for skipping steps |
| 4 | Verification is non-negotiable — every workflow terminates in concrete evidence |
| 5 | Progressive disclosure — load only relevant skills into context, not all at once; router selects |
| 6 | Scope discipline — touch only what you're asked to touch |
| 7 | The longer the agent run, the more scaffolding must be *enforced* rather than *suggested* |
| 8 | Skills encode the same SDLC phases every functioning org runs (define→plan→build→verify→review→ship) |
| 9 | The senior-engineer work is the *invisible* work that doesn't show up in the diff |
| 10 | A complex feature activates many skills in sequence; a small fix activates few — workflow scales to scope |
| 11 | Chesterton's Fence: don't remove things until you understand why they exist |
| 12 | Portability: same markdown+frontmatter skill works across any harness that accepts system-prompt content |

## Step 2: Classify — route by Dillylang relevance

| # | Destination | Rationale |
|---|---|---|
| 1 | **vocabulary design** | Distinguishes "workflow" from "reference" — maps to operator vs. prose distinction |
| 2 | **recipe patterns** | Design principle for recipe construction |
| 3 | **vocabulary design** | Novel structural pattern — a *negative-space* operator (preemptive rebuttal) |
| 4 | **recipe patterns** | Exit-criteria as mandatory terminal node in any recipe |
| 5 | **meta-skill design** | Router/progressive-disclosure maps to Dillylang's `classify`→`branch` pattern |
| 6 | **discard** | Already in AGENTS.md and CLAUDE.md verbatim |
| 7 | **recipe patterns** | Enforcement vs suggestion — relates to `constrain` operator semantics |
| 8 | **discard** | SDLC phasing is substrate/project-management, not vocabulary |
| 9 | **discard** | Motivational framing, not structural insight |
| 10 | **recipe patterns** | Recipes should scale depth to input scope — relates to budget/branch design |
| 11 | **discard** | Already encoded in CLAUDE.md ("don't refactor things that aren't broken") |
| 12 | **discard** | Substrate portability concern, not vocabulary |

## Step 3: Filter — survivors

| # | Claim | Category |
|---|---|---|
| 1 | Skill = workflow (steps + exit criteria), not prose | vocabulary |
| 2 | Process over prose — workflows are actionable; essays are not | recipe patterns |
| 3 | Anti-rationalization tables: preemptive rebuttals to skip-justifications | vocabulary |
| 4 | Every workflow terminates in concrete evidence (verification as hard exit) | recipe patterns |
| 5 | Progressive disclosure via router — load context proportional to task | meta-skill design |
| 7 | Longer pipelines need enforcement not suggestion — `constrain` as structural guard | recipe patterns |
| 10 | Recipe depth should scale to scope (budget adapts to input complexity) | recipe patterns |

## Step 4: Evaluate — novelty vs. existing spec/ADRs

| # | Novelty | Tension with existing design? |
|---|---|---|
| 1 | **Partially novel.** Spec defines operators as typed I/O transforms, but doesn't explicitly distinguish "workflow recipe" from "reference knowledge." The vocabulary has no term for this distinction. | No contradiction — extends the vocabulary's expressive reach |
| 3 | **Novel.** No existing operator or recipe pattern addresses *preemptive counter-argument*. This is a negative-space construct — not "generate X" but "anticipate and rebut attempts to skip X." Could be a `constrain` steering parameter, a recipe pattern, or a new operator demand signal. | No contradiction — orthogonal to existing operators |
| 4 | **Partially covered.** Spec §5 has `RunResult` with trace, but "verification as terminal node" is implicit in `evaluate`, not explicit as a recipe-construction rule. | Reinforces existing design; could become a recipe-construction constraint |
| 5 | **Partially covered.** `classify`→`branch` already exists. The insight is about *context management* — which is a runner/budget concern, not vocabulary. | Slight tension: this is a substrate/runner concern dressed as vocabulary |
| 7 | **Novel framing.** The spec's `constrain` operator narrows solution space, but "enforcement vs suggestion" is about *obligation strength* — a meta-property of how operators bind. | Opens a question: should recipes distinguish hard constraints from soft suggestions? |
| 10 | **Partially covered.** Budget ceiling (7 LLM calls) exists. Adaptive budget based on input scope is not formalized. | No contradiction — extends budget semantics |
| 2 | **Covered.** This is the workflow/prose distinction restated. Subsumes into claim #1. | — |

## Step 5: Rank — by leverage to Dillylang vocabulary

| Rank | # | Claim | Leverage |
|---|---|---|---|
| 1 | 3 | **Anti-rationalization as structural pattern** | HIGH — introduces a genuinely novel construct the vocabulary can't currently express. If validated, demands either a new operator or a formalized recipe-pattern. Uniquely addresses LLM failure modes. |
| 2 | 7 | **Enforcement vs suggestion (obligation strength)** | MEDIUM-HIGH — opens a design question about whether `constrain` has grades, or whether recipes need a "hard gate" vs "soft nudge" distinction in their step semantics. |
| 3 | 1 | **Workflow ≠ reference (actionability criterion)** | MEDIUM — sharpens what makes a recipe *runnable* vs mere documentation. Useful as a recipe-quality heuristic. |
| 4 | 4 | **Verification as mandatory terminal node** | MEDIUM — could become a recipe-construction rule: every recipe must end with an `evaluate` step that produces evidence. |
| 5 | 10 | **Adaptive budget (scope-proportional depth)** | LOW-MEDIUM — interesting extension to budget semantics but spec already handles via ceiling. |
| 6 | 5 | **Progressive disclosure via router** | LOW — mostly a substrate/runner concern; `classify`→`branch` already covers the vocabulary side. |

## Step 6: Synthesize — routed outputs

### Open Question: Anti-rationalization as a vocabulary construct

The post identifies a structural pattern with no Dillylang equivalent: preemptively anticipating and rebutting justifications for skipping a step. This is a *negative-space* operation — it doesn't transform an artifact, it *constrains the executor's reasoning about whether to execute*.

Three possible resolutions:

1. **Steering parameter on `constrain`:** `constrain(mode="anti-rationalization", rebuttals=[...])`
2. **Recipe-construction pattern:** pair each step with a guard table (not a new operator, just a convention)
3. **New operator demand signal:** wait for a second independent recipe that needs it (per ADR-007)

**Status:** Logged. The two-demand rule (ADR-007) says don't formalize yet. If the `improve` meta-skill or `design` meta-skill independently surface "the model skips steps and rationalizes why," that's the second demand.

### ADR Seed: Verification-terminal rule

Every recipe SHOULD terminate in an `evaluate` node whose output constitutes evidence of completion. This is already implicit (most recipes end with evaluation) but could be made an explicit recipe-construction constraint — analogous to how `synthesize` must not consume >5 uncurated inputs.

**Candidate location:** `docs/decisions/` if formalized.

### Design Observation: Obligation strength as meta-property

The post distinguishes "enforced" from "suggested" constraints. In Dillylang terms: when a recipe says `constrain(...)`, is that a hard gate (pipeline halts on violation) or a soft signal (downstream operators see the constraint but may proceed)?

The spec doesn't address this. Related to how `filter` has verdict mapping (`pass`/`partial`/`fail`) — could `constrain` have a similar strength spectrum?

**Status:** Observation only. No action until a concrete recipe hits this ambiguity.

## Summary verdict

| Output type | Count | Items |
|---|---|---|
| Novel (high leverage) | 1 | Anti-rationalization pattern |
| ADR seed | 1 | Verification-terminal rule |
| Design observation | 1 | Obligation strength / `constrain` grades |
| Already covered | 3 | Scope discipline, Chesterton's Fence, process-over-prose (as stated) |
| Discarded (substrate/framing) | 4 | SDLC phases, invisible work, portability, senior-engineer motivation |

The post's highest-value contribution to Dillylang is the **anti-rationalization pattern** — it names a failure mode (LLM self-justification for skipping steps) and proposes a structural countermeasure that no current operator addresses.
