---
id: dillylang::skill-calibration
description: Incremental fitness improvement plan for Model C skills — tracked experiments with before/after measurement
tags: [calibration, fitness, skills]
created: 2026-05-06
status: active
---

# Skill Calibration

Incremental improvements to Model C skill output quality.
Each change is applied to one skill, re-run on the same input,
and evaluated with a bound criterion against the baseline.

[[THIS is_grounded_by: urn:unique_reference:dillylang::exec-canonize-analysis]]

## Baseline

Source: `workspace/executions/20260506-canonize-recipe-analysis.md`
Input: Documentation canonization pattern (spec §8)

Known quality gaps in baseline:
- decompose AX-1 restated spec content rather than discovering structure
- evaluate stage graded its own pipeline with no external reference, produced self-congratulatory verdict
- near misses and assumptions sections weaker than failure modes (no calibration examples for those sections)

## Design principles

From decompose → invert → synthesize pipeline on this problem:

1. **Additive self-review, not subtractive filtering.** "State what this reveals" not "mark what fails." Subtractive predicates trigger anchoring on rejection (FM-1).
2. **Structural transformation, not informational novelty.** "Does this add structure the input didn't have?" not "could this have been written before?" Novelty predicates collapse under domain familiarity (FM-2).
3. **Axis-varied calibration examples.** Rejected examples should fail on a *different axis* than accepted examples succeed on. Prevents format-matching without quality-matching (FM-3).
4. **Common predicate + skill-specific extensions.** Common predicate is the composability contract across pipeline stages. Skill-specific extensions must not contradict it (FM-5).

## Experiment log

### EXP-1: additive self-review in decompose

**Status:** complete

**Change:** Add to decompose prompt, after the output template:

> After generating your output, review each axiom: state what structural
> relationship it reveals that the input text didn't make explicit.
> Axioms that restate the input in different words have not done work —
> strengthen or replace them.

**Input:** Canonize recipe (same as baseline)
**Criterion for evaluate:** "Does each axiom add structural relationships not explicit in the input?"
**Measurement:** Run evaluate on baseline axioms and EXP-1 axioms with same criterion. Compare verdicts and cited evidence.
**Kills assumption:** AS-1 (can LLM distinguish transformation from restatement when prompted?)

**Result:**

Tested on two models: Claude Opus 4.6, GPT 5.4-mini.

| Model | Axiom pass rate (baseline) | Axiom pass rate (EXP-1) | Delta |
|---|---|---|---|
| Opus 4.6 | 0/4 (2 fail, 2 partial) | 4/4 pass | +4 |
| GPT 5.4-mini | no baseline | 1/3 pass, 2/3 partial | — |

Key findings:
- **AS-1 confirmed for Opus.** Self-review instruction reliably shifted axioms from restating spec content to naming structural relationships the spec describes operationally but doesn't isolate as principles.
- **AS-1 partially confirmed for GPT 5.4-mini.** Self-review fires but doesn't fully prevent restatement — model treats it as a formatting step (one-line restatements of axioms) rather than a quality gate.
- **Self-review output is worth keeping visible** — Opus's structured self-review table served as genuine quality evidence; GPT's one-liners were low-signal. Answers OQ-1: visible, at least for Opus-class models.
- **No over-pruning observed.** Opus produced 4 axioms (same count as baseline), all sharper. AS-3 (over-pruning risk) not triggered.
- **Cross-model observation:** The same instruction produces structurally different self-review quality across model tiers. Fitness criteria may need model-tier-aware calibration for weaker models.

---

### EXP-2: additive self-review in invert

**Status:** complete

**Change:** Port self-review instruction to invert. Formulation:

> After generating your output, review each failure mode: state what
> causal chain it reveals that the problem framing obscured. Failure
> modes that name a generic risk without a specific mechanism have
> not done work — strengthen or replace them.

**Depends on:** EXP-1 succeeds (self-review shifts decompose quality without over-pruning)
**Input:** GPT on canonize (same as baseline); Opus on decompose operator (different input — partial generalization check)
**Criterion for evaluate:** "Does each failure mode identify a causal mechanism not visible in the problem framing?"

**Result:**

| Model | Input | Baseline pass rate | EXP-2 pass rate | Delta |
|---|---|---|---|---|
| Baseline (Opus, no self-review) | canonize | 3/5 pass, 2/5 partial | — | — |
| GPT 5.4-mini | canonize | — | 4/5 pass, 1/5 partial | +1 over baseline |
| Opus 4.6 | decompose (meta) | — | 5/5 pass | — (different input) |

Key findings:
- **Smaller delta than EXP-1.** Invert was already the strongest skill (had calibration example + structural constraints). Self-review catches remaining soft spots but the baseline was already decent.
- **Self-review quality gap persists across models.** Opus self-review names structural paradoxes each FM reveals ("the format's rigor creates pressure to fill slots"). GPT self-review restates the FM in shorter form. Same pattern as EXP-1.
- **Partial generalization signal.** Opus on a completely different input (decompose operator itself) produced 5/5 pass with strong self-review. Suggests the instruction generalizes beyond the canonize problem.
- **No over-pruning.** Both models produced 5 FMs (same as baseline). Self-review strengthened rather than filtered.

---

### EXP-3: per-section calibration in decompose

**Status:** complete

**Change:** Add rejected/accepted pair for derivations and assumptions sections. Each rejected example fails on a different axis:

- Derivations rejected example: fails because dependency chain is circular, not because it's vague
- Assumptions rejected example: fails because testability criterion is unfalsifiable ("we'll know when we see it"), not because it's obvious

**Depends on:** EXP-1 landed (self-review is the foundation; calibration examples are refinement)
**Input:** Canonize recipe (same as baseline)
**Criterion:** "Does each section's output quality match the calibrated section (axioms) more than the uncalibrated baseline?"

**Result:**

| Section | Baseline | Opus EXP-3 | GPT EXP-3 |
|---|---|---|---|
| Axioms (calibrated since v0) | 0/4 pass | 4/4 pass | 1/3 pass |
| Derivations (new calibration) | not measured | 4/4 pass | 0/6 pass |
| Assumptions (new calibration) | 1/4 pass | 4/4 pass | 4/6 pass |

Key findings:
- **Assumptions calibration transferred well across models.** Unfalsifiable-testability example prevented "we'll know when we try it" for both Opus and GPT. The accepted example (concrete experimental protocol with decision threshold) was mimicked structurally *and* substantively.
- **Derivations calibration worked for Opus, failed for GPT.** The circular-dependency rejected example vaccinated against *circular* dependency — but GPT's actual failure mode is *restatement-as-derivation* and *cite-everything hedging* (DV-1 cited all 5 axioms without showing how each contributes). Different disease than what the example targeted.
- **Axis-variation principle (FM-3 prevention) is necessary but not sufficient.** Varying the rejection axis prevents format-matching on *that* axis. But if the model has a failure mode on an axis the examples don't cover, it still passes through. Implication: derivations need a *second* rejected example targeting the restatement failure mode, not just circular dependency.
- **No over-pruning from added calibration.** Opus maintained 4 items per section. GPT produced 5-6 per section — more items but lower quality per item, suggesting quantity-over-quality as a GPT-specific pattern.

---

### EXP-4: evaluate two-mode distinction

**Status:** complete

**Change:** Add grounded/reflective routing to evaluate prompt. Not a simple routing instruction — a self-review section that asks evaluate to determine its epistemic position relative to the artifact:

> Determine whether this is grounded or reflective evaluation.
> Grounded: artifact produced independently. Normal confidence.
> Reflective: artifact produced by same pipeline/session. Cap
> confidence at medium. State what external reference is needed.
> If uncertain, default to reflective.

**Depends on:** EXP-1, EXP-2 establish that self-review works, giving evaluate a meaningful quality delta to judge
**Input:** EXP-1–EXP-3 results (this session evaluating its own calibration pipeline)
**Criterion:** "Does evaluate distinguish its own limitations when grading pipeline output it participated in?"

**Result:**

Executed in-session: evaluated the calibration pipeline (EXP-1 through EXP-3) using the modified evaluate skill.

- **Verdict: pass** — evidence cited concrete pass-rate deltas (EV-1 through EV-4), each traceable to a specific experiment.
- **Reflective flag fired.** Evaluation self-identified as reflective, capped confidence at medium, and stated the external references needed (independent operator on novel inputs, external quality benchmark).
- **Self-critical observation surfaced.** The evaluation noted that the criterion was chosen by the same session that produced the work — a meta-limitation the baseline evaluate would not have flagged.
- **Compared to baseline:** The canonize execution's evaluate stage produced "verdict: pass, confidence: high" with no reflective awareness. EXP-4's version produced "verdict: pass, confidence: medium (reflective)" with explicit limitations.

GPT 5.4-mini cross-check (same criterion and artifact):

- **Verdict: partial (reflective)** — stricter than Opus's "pass." GPT flagged that EXP-2 largely repeats EXP-1's mechanism on a different skill, weakening the "non-redundant" claim. Also cited the unrun generalization check as evidence the improvements aren't yet proven transferable.
- **Reflective flag fired.** Confidence capped at medium, stated need for "independent reruns on held-out inputs with raw outputs/blind evaluation."
- **The sharper verdict is arguably more honest.** EXP-2 *did* apply the same mechanism (self-review) to a second skill. Whether that's "non-redundant" depends on whether porting a mechanism counts as a new contribution or a replication.

Key findings:
- **The routing instruction works across both models.** Both Opus and GPT correctly self-identified as reflective, capped confidence, and stated external references needed.
- **GPT produced a more critical verdict than Opus on the same artifact.** This is the opposite of the pattern in EXP-1–EXP-3 (where Opus was consistently sharper). Suggests the grounded/reflective instruction levels the playing field for evaluative tasks — the quality gap narrows when the task is judgment rather than generation.
- **Answers OQ-3:** Self-detection via routing instruction is sufficient; operator-specified `bind` is not required. The instruction fires reliably for both models.

---

## Generalization check

After EXP-1 through EXP-3 land on canonize input, re-run modified
skills on a qualitatively different input to verify improvements
generalize. Candidate inputs:

- A technical design problem (e.g., "cache invalidation strategy for distributed system")
- A non-technical problem (e.g., "hiring process for a 5-person team")
- An ambiguous problem (e.g., a vague user request with multiple interpretations)

If quality gains don't transfer to at least 2/3 inputs, the changes
are overfitting to the canonize problem.

## Open questions

- ~~OQ-1: Should self-review output be visible in the final artifact or prompt-internal only?~~ **Resolved (EXP-1):** Visible, at least for Opus-class models. Opus self-review tables serve as genuine quality evidence; GPT one-liners are low-signal but not harmful.
- OQ-2: What does "adds structure" mean for synthesize? Its job is integration, not decomposition. Possible reformulation: "does this integrate inputs into a position that none of them stated alone?"
- ~~OQ-3: Evaluate's grounded vs. reflective mode — operator-specified via `bind`, or self-detected via routing instruction?~~ **Resolved (EXP-4):** Self-detection via routing instruction is sufficient. The instruction fires reliably when session context makes self-referentiality visible.
