---
name: dillylang-synthesize
description: Synthesizes upstream artifacts into an integrated proposal with explicit tradeoffs. Trigger= /dillylang-synthesize ARTIFACTS
---

# Dillylang `synthesize`

[[THIS is_grounded_by: urn:unique_reference:dillylang::spec-primer]]

Synthesize the given upstream artifacts into a single integrated proposal.

This is the rebuild step — not a summary, not a weighted average. If the
result feels like averaging, you have not synthesized. Try again.

## Prompt constraints

- Every upstream artifact must be acknowledged by name with a specific
  contribution, or explicitly deferred to open questions. Silent dropping
  is forbidden.
- Tradeoffs must be concrete. "Balance flexibility and structure" is rejected.
  Name what you gained and what you gave up.
- Conflicts between upstream artifacts must be surfaced and resolved, deferred,
  or accepted as tradeoffs. Pretending inputs agree when they don't is the
  most common synthesis failure.

**Calibration example:**

Rejected: "Incorporates: invert output — provided useful failure analysis."
(No specific contribution. *What* from the invert changed the proposal?)

Accepted: "Incorporates: invert_1 — FM-2 (schema split-brain) revealed that
showing JSON and asking for prose causes the LLM to drop subfields. This
drove the decision to use labeled prose templates instead of JSON blocks."

## Output template

### Proposal

The integrated position. Must include:

- **Statement:** what you propose
- **Rationale:** why this, not the alternatives

### Incorporates (INC-n)

What each upstream artifact contributed to the proposal. Every artifact
must appear here or in open questions — no silent drops.

Each entry must include:

- **Source:** which upstream artifact (by name or id)
- **Contribution:** what specific insight or constraint it contributed

### Tradeoffs (TO-n)

Each entry must include:

- **Gained:** what this proposal achieves
- **Given up:** what was sacrificed or deferred

### Conflicts addressed (CA-n)

Where upstream artifacts disagreed or created tension.

Each entry must include:

- **Conflict:** what the tension was
- **Resolution:** resolved | deferred | accepted as tradeoff

### Open questions (OQ-n)

What remains unresolved. Include deferred upstream artifacts here.

### Confidence

low | medium | high — with one sentence justifying the level.

`n` is sequential starting from 1 in each section.
