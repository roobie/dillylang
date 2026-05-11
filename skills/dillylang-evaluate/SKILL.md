---
name: dillylang-evaluate
description: Judges an artifact against an explicit criterion. Trigger= /dillylang-evaluate CRITERION ARTIFACT
---

# Dillylang `evaluate`

[[THIS is_grounded_by: urn:unique_reference:dillylang::spec-primer]]

Judge the given artifact against the specified criterion.

A criterion is required — evaluation without a criterion is meaningless.
The first argument is the criterion, everything after is the artifact
to evaluate.

## Prompt constraints

- Verdict must be grounded in specific evidence from the artifact, not
  general impressions.
- Evidence must be quotable or pointable — "the code looks fine" is not
  evidence, "function X validates input at line Y" is.
- Confidence reflects how much of the artifact the criterion actually
  covers. A criterion that only touches one aspect of a large artifact
  is low confidence even if the verdict is clear.

**Calibration example:**

Rejected: "Verdict: pass. Rationale: The design looks solid and well-structured."
(No evidence. What specifically satisfies the criterion?)

Accepted: "Verdict: partial. Rationale: Prompt constraints section addresses
FM-1 (generic risks) with a contrast example, but FM-4 (near-miss guidance)
has no calibration — the constraint is advisory without a quality floor.
Evidence: lines 14-18 show rejected/accepted pair for failure modes; lines
43-45 have no equivalent for near misses."

## Output template

### Criterion

Restate the criterion being evaluated against.

### Verdict

pass | partial | fail

### Evidence (EV-n)

Specific observations from the artifact supporting the verdict.

Each entry must include:

- **Observation:** what was found
- **Location:** where in the artifact (line, section, field)

### Rationale

How the evidence leads to the verdict. Connect the dots — don't just
list evidence and state a verdict separately.

### Confidence

low | medium | high — reflects how thoroughly the criterion covers the
artifact, not just certainty in the verdict.

`n` is sequential starting from 1 in each section.

## Self-review

Determine whether this is **grounded** or **reflective** evaluation:

- **Grounded:** The artifact being evaluated was produced independently
  of this evaluation step. Normal confidence rules apply.
- **Reflective:** The artifact was produced by a pipeline that includes
  this evaluation step, or by the same session/agent. Flag the verdict
  as reflective. Cap confidence at medium. State what external reference
  would be needed to make this a grounded evaluation.

If uncertain, default to reflective — the cost of under-confidence is
low, the cost of self-congratulatory grading is high.
