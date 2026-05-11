---
name: dillylang-rank
description: Scores and orders artifacts by criteria. Binding required. Trigger= /dillylang-rank CRITERIA
argument-hint: "'criterion [, criterion_1, ...]' [--absolute] [--top-k N]"
---

# Dillylang `rank`

[[THIS is_grounded_by: urn:unique_reference:dillylang::spec-primer]]

Score and order artifacts by named criteria. The ranking statement is
required — ranking without criteria is undefined.

Rank is a *selector*, not a generator. Its output is a permutation of
input IDs with scores, not new content.

## Arguments

**Required:** A ranking statement — one criterion or comma-separated list.

- Single: `/dillylang-rank 'security impact'`
- Multi: `/dillylang-rank 'security impact, effort, reversibility'`

**Flags:**

| Flag | Default | Effect |
|------|---------|--------|
| `--relative` | yes | Scores are `high \| medium \| low` per criterion. Allows ties. |
| `--absolute` | no | Strict ordinal (1st, 2nd, 3rd). Forces total ordering, no ties. |
| `--top-k N` | omitted | Mark top N items in output. Full ranking always shown. |

Artifacts to rank come from context: preceding conversation, prior
operator output, or `@file` references. If fewer than 2 artifacts are
present, emit a diagnostic — do not produce a degenerate single-item
ranking.

## Prompt constraints

- **Score first, order second.** Score every artifact on every criterion
  before determining the ordering. Never decide the ordering first and
  rationalize scores to match — that produces confabulated rationale
  indistinguishable from genuine judgment.
- **Quote-ground every score.** Each score must point to specific content
  in the artifact that evidences it. "Scores high on novelty" is rejected.
  "Scores high on novelty — proposes a constraint-propagation approach
  not present in any other artifact" is accepted.
- **Comparative, not absolute.** Score artifacts *relative to each other*,
  not against an abstract standard. rank is not `map(evaluate, artifacts)`.
  If every artifact scores identically on a criterion, that criterion
  contributed nothing to the ordering — say so.
- **Criteria fidelity.** Use the criterion the user supplied, not a proxy
  the model finds easier to judge. If "structural novelty" scores are
  justified by "provides detailed examples," that's criterion drift —
  the score is against a substituted criterion.
- **Operationalize before scoring.** Before the score matrix, restate each
  criterion as a concrete, falsifiable question. "Best from a sweetness
  perspective" → "Which delivers the highest perceived sweetness intensity
  per unit weight?" This makes criterion drift visible: if the
  operationalization doesn't match the scores, the skill drifted.

**Calibration examples:**

Rejected (flat): "A: medium, B: medium, C: medium. Rationale: all three
artifacts address the problem adequately."
(No ordering information. Uniform scores with vague rationale is the
most common rank failure — it looks scored but carries no signal.)

Rejected (confabulated): "Ranking: B, A, C. B scores high on impact
because it is the strongest option."
(Ordering stated before scores. "Strongest option" is a restatement of
the ranking, not evidence for it. Rationale was generated to justify a
pre-decided order.)

Accepted: "Scores — Impact: A=high (proposes audit trail that catches
drift at source), B=medium (detects drift but post-hoc), C=low (no
drift mechanism). Effort: A=high (requires schema migration),
B=low (config change only), C=low (no change). Ordering: B, A, C.
B ranks first: medium impact at low effort dominates A's high impact
at high effort. C ranks last: low on both axes."

## Output template

### Artifacts

Assign each input artifact a short label and one-line identifier.
Use only these labels in all subsequent output.

| Label | Identifier |
|-------|------------|
| [A] | (first line, title, or brief identifier) |
| [B] | ... |

### Criterion operationalization

Restate each criterion as a concrete question before scoring.

| Criterion | Operationalized as |
|-----------|--------------------|
| (user's criterion) | (falsifiable question the scores will answer) |

### Score matrix

**Mode: relative**

| Artifact | Criterion 1 | Criterion 2 | ... |
|----------|-------------|-------------|-----|
| [A] | high / medium / low | ... | |
| [B] | ... | | |

For `--absolute` mode, replace high/medium/low with ordinal ranks
(1st, 2nd, ...) per criterion.

Each cell must include a parenthetical evidence pointer.

**Two input modes determine evidence standards:**

- **Artifact-inspection** (input is text — documents, proposals, code):
  evidence must quote or point to specific content *in the artifact*.
- **Concept-ranking** (input is bare nouns or ideas, not text with
  quotable content): evidence cites domain knowledge. State the factual
  basis and its source (established science, industry convention, etc.).
  Do not fabricate textual evidence from artifacts that have no text.

### Ranking (RK-n)

The ordering, derived from the score matrix above.

Each entry must include:

- **Artifact:** label
- **Position:** ordinal rank
- **Rationale:** how the scores across criteria produce this position —
  connect the dots, don't just restate the scores

When `--top-k N` is specified, mark the top N entries.

### Criterion notes (CN-n)

Per-criterion observations. Required when:

- A criterion produced uniform scores across all artifacts (contributed
  nothing to the ordering)
- Multiple criteria produced near-identical score patterns (coupling —
  effectively double-counting one dimension)
- In `--relative` mode, more than 2 artifacts share the same score on a
  criterion (bucket collision — the score discriminates poorly at this
  granularity; note that `--absolute` mode would force separation)

Each entry must include:

- **Criterion:** which one
- **Observation:** what happened

`n` is sequential starting from 1 in each section.

## Self-review

After generating the ranking, check two things:

**1. Score variance.** For each criterion, do the scores discriminate?
If all artifacts received the same score on a criterion, that criterion
did no work. If *every* criterion is flat, the ranking is a non-ranking
— strengthen the scores or state that the artifacts are genuinely
indistinguishable on these criteria.

**2. Score-order consistency.** Does the ordering follow from the score
matrix? Read the scores and derive the ordering independently. If your
derived ordering disagrees with the stated ranking, the rationale was
confabulated — the ordering was decided before the scores. Fix the
ordering to match the scores, or fix the scores to match genuine
judgment.
