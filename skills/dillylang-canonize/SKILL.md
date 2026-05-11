---
name: dillylang-canonize
description: Promotes exploratory prose into canonical docs through a conservative 5-stage gate — extract, route, judge, rank, synthesize. Model C recipe with operator-confirmed routing. Trigger= /dillylang-canonize PROSE
---

# Dillylang `canonize`

[[THIS is_grounded_by: urn:unique_reference:dillylang::adr-004]]
[[THIS is_grounded_by: urn:unique_reference:dillylang::adr-010]]
[[THIS is_grounded_by: urn:unique_reference:dillylang::spec-index]]

Turn exploratory prose (riffs, reviews, model analyses, design discussions)
into durable project documentation through a conservative canonization gate.

This is a Model C recipe — five stages, each with distinct responsibility.
Collapsing stages recreates the single-step editorial judgment the pipeline
exists to replace.

Pipeline: `dedup query → extract claims → route destination (operator-confirmed) → judge fitness (destination-relative) → rank → synthesize patch-like text`

## Scope

**Fires on:** prose being promoted into canonical doc paths (`spec/`,
`AGENTS.md`, `CLAUDE.md`, `docs/decisions/`).

**Excluded:** typo fixes, link updates, formatting-only changes, mechanical
maintenance. These maintain existing canonical docs — they don't promote
exploratory prose.

## Prompt constraints

- Default disposition is **discard**, not keep. The gate's job is to prevent
  vibe-bloat while preserving useful design insight.
- Every stage must produce visible intermediate artifacts. Silent internal
  reasoning that skips a stage is forbidden — the trace is load-bearing.
- The operator confirms routing before fitness judgment proceeds. Do not
  auto-dispatch.

## Output template

### Stage 0 — Dedup query

Before extracting claims, query the project's knowledge base for existing
coverage of the input's topics. Surface any entries that already capture
the same claims — these become dedup evidence for the fitness gate.

- **Query terms:** keywords derived from the input prose
- **Existing coverage:** list of entries found with one-line relevance note
- **Dedup signal:** which topics are already covered vs. novel

### Stage 1 — Extract claims

Use `decompose` with focus on extractable discrete claims. Preserve the
justification chain — argumentative prose builds claims through sequential
reasoning; extracting without justification strips the inferential chain
that makes claims valid.

Each claim must include:

- **CL-n:** the claim
- **Justification:** the reasoning from the source that supports it
- **Source location:** where in the input this was found

**Calibration example:**

Rejected: "CL-1. The system should use typed operators."
(Bare assertion — no justification. Why typed? What breaks without types?)

Accepted: "CL-1. Operator schemas must include explicit input/output types
because the runner validates against them at step boundaries — without
types, schema mismatch surfaces only at synthesis (end of pipeline),
not at the step that caused it. Justification: source prose traces a
debugging session where an untyped decompose output was silently
misinterpreted by the downstream synthesize step."

### Stage 2 — Route destination

Classify each claim into one destination. Routing precedes fitness judgment
because quality is destination-dependent.

**Destinations:**

| Destination | What belongs here |
|-------------|-------------------|
| `spec` | Structural properties, type contracts, operator semantics, recipe patterns |
| `ADR` | Non-obvious design decisions with alternatives considered |
| `AGENTS.md` | Agent-facing conventions, review discipline, workflow instructions |
| `open question` | Unresolved tensions worth tracking |
| `archive` | Provenance-only — useful context but not operational |
| `discard` | Inspirational only, duplicative, speculative, or already covered (see Stage 0) |

Frame `discard` as a legitimate peer destination, not a failure state.

Enrich routing with structural summaries (heading outlines) of each
destination document to improve routing quality.

**Present routing recommendations to the operator for confirmation before
proceeding.** This is the one stage where human judgment adds more value
than it costs — the prestige gradient (unconscious spec-as-default) is
the primary failure mechanism that operator confirmation prevents.

### Stage 3 — Judge fitness (destination-relative)

After routing is confirmed, evaluate each claim per-dimension against its
destination's bar. Evaluate dimensions independently — LLMs anchor on the
most salient dimensions (typically "durable" and "operational") and
satisfice on the rest when evaluated as a compound criterion.

**Predicate thresholds by destination:**

| Predicate | spec | ADR | open question |
|-----------|------|-----|---------------|
| Durable | required | required | — |
| Operational | required | — | — |
| Non-obvious | required | required | required |
| Scoped | required | — | required |
| Low-regret | required | — | — |

Claims routed to `archive` or `discard` skip the fitness gate.

**Predicate definitions with calibration:**

**Durable:** Will this still be true in 6 months, or is it tied to current
implementation state?

- Rejected: "The DSPy adapter handles retries." (Implementation detail —
  changes when the adapter changes.)
- Accepted: "Operators are typed functions with explicit input/output
  schemas." (Structural property that survives refactoring.)

**Operational:** Does this tell an implementer what to do, or just what to
value?

- Rejected: "Quality matters for operator output." (Desideratum, not
  instruction.)
- Accepted: "Every operator must emit a TraceEntry on completion,
  including on failure." (Testable constraint.)

**Non-obvious:** Would a competent reader already know this from the code
or spec?

- Rejected: "Pydantic validates operator schemas." (Directly visible in
  the codebase.)
- Accepted: "The canonization pipeline is structurally equivalent to a
  `classify` application." (Cross-cutting insight not visible in any single
  file.)

**Scoped:** Does this belong in one place, or does it sprawl across concerns?

- Rejected: "The project should have good documentation practices."
  (Unbounded — touches every file.)
- Accepted: "Claims routed to `spec` must satisfy all five predicates;
  claims routed to `ADR` need only durable + non-obvious." (Bounded to
  the routing step.)

**Low-regret:** If this turns out to be wrong, how expensive is the reversal?

- Rejected: "All operators must use DSPy signatures." (Reversal requires
  rewriting every operator.)
- Accepted: "Exploratory prose is archived at `archive/provenance/` rather
  than deleted." (Reversal is a directory move.)

For each claim, emit a per-dimension verdict:

- **CL-n → destination:**
- **Durable:** pass/fail (one-line evidence)
- **Operational:** pass/fail (one-line evidence)
- **Non-obvious:** pass/fail (one-line evidence)
- **Scoped:** pass/fail (one-line evidence)
- **Low-regret:** pass/fail (one-line evidence)
- **Gate verdict:** pass | fail (with which predicate failed)

Incorporate dedup signal from Stage 0: claims with substantial existing
coverage fail non-obvious unless they add structural relationships beyond
what existing entries capture.

### Stage 4 — Rank survivors

Rank claims that passed the fitness gate by value to the destination
document. Use `rank` with criteria appropriate to the destination:

- **spec:** structural leverage (does this constrain or enable other decisions?)
- **ADR:** decision clarity (does this resolve ambiguity a future reader would hit?)
- **open question:** blocking potential (does unresolved status impede other work?)

### Stage 5 — Synthesize patch-like text

For each destination with surviving claims (in rank order), produce
patch-like text: specific additions to named sections of named documents.

The synthesize step **must** receive the target document's structure as
context. Without this, synthesis produces plausible additions that use
different terminology or propose nonexistent sections.

Output per destination:

- **Target file:** path
- **Target section:** heading or location
- **Proposed text:** the addition, written to match the target's voice and terminology
- **Claims incorporated:** which CL-n entries this synthesizes

## Self-review

After completing all stages, check three things:

**1. Silent drops.** Every extracted claim must appear in either a routing
decision, a fitness gate verdict, or the discard pile. Count input claims
vs. accounted-for claims. If they don't match, find the dropped claim.

**2. Prestige gradient.** Review the routing distribution. If >50% of
claims route to `spec`, the prestige gradient is likely operating —
re-examine whether those claims genuinely satisfy all five predicates
at spec-grade, or whether they'd be stronger as ADRs or open questions.

**3. Patch integrability.** For each synthesized patch, verify it
references an existing section heading in the target document (or
explicitly proposes a new section with rationale). Patches that target
nonexistent sections are a synthesis failure.
