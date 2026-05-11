---
name: dillylang-invert
description: Applies Munger / Jacobi inversion on a problem statement. Trigger= /dillylang-invert PROBLEM
---

# Dillylang `invert`

[[THIS is_grounded_by: urn:unique_reference:dillylang::spec-primer]]

Apply Munger / Jacobi inversion on the given problem statement.

Stop asking "how succeed" and ask "what guarantees failure."

## Prompt constraints

- Require concrete mechanism descriptions for every failure mode.
- Reject generic risks that lack a specific causal chain.
- Each failure mode must name the mechanism by which it causes damage.

**Calibration example:**

Rejected: "FM-1. Market changes — Likelihood: high, Severity: costly."
(No mechanism. *How* do market changes cause damage? Through what chain?)

Accepted: "FM-1. Price-sensitive users churn on first renewal —
Mechanism: free tier sets anchor price at zero; switching to paid
triggers loss aversion disproportionate to the dollar amount.
Likelihood: high. Severity: costly. Preventable by: usage-gated
tiers that establish value before the price conversation."

## Output template

The problem statement from a Munger inversion point-of-view, e.g. "What would cause [desired state] to fail?"

### Anti-goals (AG-n)

Desired-state inversions: what would I aim for if I *wanted* to fail?
Not causal chains (that's FM) — these are the goals of the adversary.

### Failure modes (FM-n)

Causal chains: how does the damage happen, mechanistically?

Each entry must include:

- **Mode:** what goes wrong
- **Mechanism:** the specific causal chain — how it causes damage
- **Likelihood:** low | medium | high
- **Severity:** recoverable | costly | fatal
- **Preventable by:** what stops this

### Near misses (NM-n)

Fragile-but-surviving conditions: things that *almost* fail but currently
hold. For each, name what currently prevents it from becoming a full
failure mode — the thing that would have to change for it to tip over.

`n` is sequential starting from 1 in each section.

## Self-review

After generating your output, review each failure mode: state what
causal chain it reveals that the problem framing obscured. Failure
modes that name a generic risk without a specific mechanism have
not done work — strengthen or replace them.
