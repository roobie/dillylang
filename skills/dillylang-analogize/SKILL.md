---
name: dillylang-analogize
description: Maps problem structure to other domains, importing mechanism not metaphor. Trigger= /dillylang-analogize PROBLEM
argument-hint: "[domain_0, domain_1, ...]"
---

# Dillylang `analogize`

[[THIS is_grounded_by: urn:unique_reference:dillylang::spec-primer]]
[[THIS is_grounded_by: urn:unique_reference:dillylang::adr-007]]

Map the problem to another domain that shares structural relationships.
Importing mechanism, not metaphor. If the source domain's dynamics don't
tell you something actionable about the target, the analogy is decorative.

## Arguments

**Optional:** Comma-separated list of source domains to constrain the search.

- Bound: `/dillylang-analogize 'biology, economics'` — analogies from
  those domains. Domain diversity constraint relaxed since the user chose.
- Unbound: `/dillylang-analogize` — free domain search driven by
  problem signature. The more interesting case — domain discovery is
  part of the analytical work.

## Prompt constraints

- **Signature first, analogies second.** Before searching for source
  domains, characterize the problem's abstract structure — the
  `problem_signature`. This signature must use domain-independent
  language: no vocabulary from the problem's native domain, no vocabulary
  from any source domain. The signature is the search index — its quality
  determines analogy quality more than any other field.
- **Mechanism, not metaphor.** Each analogy must map a *mechanism* — a
  dynamic process, feedback loop, or structural relationship that makes
  the source domain work. "A database is like a filing cabinet" maps
  surface features. "B-tree indices narrow search space hierarchically,
  like a library card catalog's subject→subtopic→shelf path" maps a
  mechanism. The test: does knowing how the source works tell you
  something actionable about the target?
- **Bidirectional mapping.** `mechanism_mapping` must name the mechanism
  in the source domain AND what it corresponds to in the target problem.
  "Immune systems use pattern recognition" describes the source.
  "Immune system pattern recognition → anomaly detection in network
  traffic: both identify non-self by deviation from learned baselines"
  shows the transfer. Without the target-side, the reader infers the
  transfer — which is where silent misapplication enters.
- **Stowaways are specific, not generic.** Each stowaway must name a
  concrete assumption from the source domain that might not hold in the
  target. "The analogy is imperfect" is rejected. "The immune system
  analogy assumes defenders can't coordinate centrally — does your
  network have a central orchestrator? If so, this analogy's
  decentralized-response mechanism is misleading" is accepted. Phrase
  as a testable question about the target domain.
- **Actionable insight.** `transferable_insight` must name a concrete
  action or design decision for the target domain, not restate the
  mechanism mapping. It should be actionable even if the reader skips
  the mechanism_mapping.
- **Domain diversity.** When unbound, analogies must come from distinct
  meta-domains — no two from the same broad field. Three biology
  analogies import one worldview; one each from biology, economics,
  and engineering import three. When `domains` is bound, this constraint
  is relaxed.

**Calibration examples:**

Rejected (metaphor, not mechanism): "Your deployment pipeline is like
an oil pipeline — both move things from source to destination.
mechanism_mapping: 'Flow from origin to endpoint.'
stowaways: ['Scale differences may apply.']"
(Surface vocabulary match. The mechanisms are unrelated — fluid dynamics
vs. staged transformation. Stowaway is a generic disclaimer.)

Rejected (one-directional mapping): "Assembly lines use checkpoint
inspection to catch defects early.
transferable_insight: 'Early inspection catches problems sooner.'"
(Source-only mechanism description. Insight restates the mapping.
Where specifically in the target domain should the checkpoint go?)

Accepted: "problem_signature: 'Sequential staged process where each
stage has a pass/fail gate; failure cost scales with distance from
origin; no stage can inspect work done by a prior stage.'
domain: manufacturing. analog: assembly line with QC stations.
mechanism_mapping: 'QC stations at each assembly stage catch defects
at minimum rework cost → linting at PR stage catches issues before
they propagate to integration, where fix cost includes merge conflicts
and dependent-branch rebases.'
transferable_insight: 'Add the cheapest validation at the earliest
stage — a 30-second lint check before merge prevents a 2-hour
integration debug session. The analogy predicts that the optimal
inspection frequency is at every stage boundary, not at the end.'
stowaways: ['Assembly lines assume linear flow — does your pipeline
have parallel branches that reconverge? If so, the defect-distance
cost model breaks because defects propagate sideways, not just
forward.']"

## Output template

### Problem signature

Abstract structural characterization of the problem. Must use
domain-independent language — no vocabulary from the problem's own
domain or from any source domain. This is the search index for
analogy, not a summary of the problem.

### Analogies (AN-n)

Produce 2–3 analogies from distinct meta-domains (when unbound).

Each entry must include:

- **domain:** the source domain
- **analog:** the specific thing in that domain being mapped to
- **mechanism_mapping:** the mechanism in the source AND what it
  corresponds to in the target — bidirectional, not source-only
- **transferable_insight:** a concrete action or design decision for
  the target domain, actionable without reading the mapping
- **stowaways:** assumptions from the source domain that may not hold
  in the target, each phrased as a testable question

`n` is sequential starting from 1.

## Self-review

After generating analogies, check two things:

**1. Signature independence.** Does the `problem_signature` contain
vocabulary specific to any of the source domains? If the signature
uses "adaptive," "organic," or "evolutionary" and one analogy is
biological, the signature was likely reverse-engineered from pre-chosen
analogies rather than driving the search. Rewrite the signature in
domain-neutral terms.

**2. Mechanism vs. metaphor.** For each analogy, ask: if I removed the
source domain name and just described the mechanism abstractly, would
the mapping still hold? If the analogy depends on the source domain's
*name* being evocative rather than its *dynamics* being structurally
parallel, it's a metaphor. Strengthen or replace it.
