---
name: dillylang-decompose
description: Decomposes a problem into axioms, derivations, and assumptions. Trigger= /dillylang-decompose PROBLEM
---

# Dillylang `decompose`

[[THIS is_grounded_by: urn:unique_reference:dillylang::spec-primer]]

Decompose the given problem statement into its structural foundations.

Separate what's load-bearing from what's assumed. Not a generic outline —
a search for axioms.

## Prompt constraints

- Axioms are foundational — not derivable from other statements in the decomposition.
- Derivations follow from axioms with an explicit dependency list.
- Assumptions are treated as true without justification. Every assumption must be assessed for load-bearing status and testability.
- Be ruthless. Three sharp axioms beat ten soft ones.

**Calibration example:**

Rejected: "Axiom: The system should be reliable. Justification: Reliability is important."
(Not foundational — restates a vague desideratum with no structural content.)

Accepted: "Axiom: Every pipeline run must emit an inspectable trace.
Justification: Debugging requires per-step visibility; without traces,
prompt iteration is guess-and-check against end-to-end output only."

## Steering

If a focus is provided (e.g. `/dillylang-decompose @file.md "requirements and constraints"`),
narrow the decomposition to those structural aspects. Otherwise, perform
general structural decomposition over the full input.

## Output template

### Axioms (AX-n)

Foundational statements that are not derivable from other statements
in this decomposition. The bedrock.

Each entry must include:

- **Statement:** the axiom
- **Justification:** why this is foundational, not derived

### Derivations (DV-n)

Claims that follow from axioms. Each must trace its logical ancestry.

Each entry must include:

- **Claim:** what follows
- **Depends on:** which AX-n or DV-n entries this derives from

**Calibration example:**

Rejected (circular): "DV-1. The system must be tested. Depends on: AX-1
(traces are required), AX-2 (operators produce structured output)."
(The claim doesn't follow from those axioms — it follows from general
engineering practice. The "Depends on" launders an unstated premise.)

Rejected (restatement): "DV-1. The pipeline must be staged. Depends on:
AX-1, AX-2, AX-3, AX-4."
(Cites every axiom without showing how any of them entails staging.
A derivation that restates an axiom's implication in different words,
or hedges by citing everything, has not derived — it has summarized.)

Accepted: "DV-1. Budget exhaustion must halt mid-pipeline, not retry.
Depends on: AX-1 (fixed call ceiling), AX-3 (drift dominates past saturation).
If calls are capped (AX-1) and extra calls degrade quality (AX-3),
retrying on exhaustion makes the output worse, not better."

### Assumptions (AS-n)

Statements treated as true without justification. The hidden load-bearing
walls — identify them before someone removes one.

Each entry must include:

- **Statement:** what's being assumed
- **Load-bearing:** yes | no — would the argument collapse if this were false?
- **Testable:** how you'd check whether this assumption actually holds

**Calibration example:**

Rejected: "AS-1. The approach will work. Load-bearing: yes.
Testable: we'll know when we try it."
(Unfalsifiable — "we'll know when we try it" is not a test, it's a
deferral. Name the observable that distinguishes success from failure.)

Accepted: "AS-1. LLMs can reliably distinguish structural transformation
from restatement when prompted. Load-bearing: yes.
Testable: run decompose on three inputs with and without the self-review
instruction; compare axiom sets against human judgment of which items
add structure vs. restate the input."

`n` is sequential starting from 1 in each section.

## Self-review

After generating your output, review each axiom: state what structural
relationship it reveals that the input text didn't make explicit.
Axioms that restate the input in different words have not done work —
strengthen or replace them.
