---
id: dillylang::exec-canonize-analysis
description: Full decompose -> invert -> synthesize -> apply pipeline on the canonize recipe
tags: [execution, canonize, recipe-design]
created: 2026-05-06
status: active
---

# Canonize Recipe Analysis

Pipeline: `decompose -> invert -> synthesize -> apply -> evaluate`
Target: Documentation canonization pattern (spec §8)
Outcome: Three structural changes applied to spec/INDEX.md

## Provenance

- **Operator:** BR + Claude Opus 4.6
- **Session date:** 2026-05-06
- **Commit:** applied in same session as spec/PRIMER.md creation
- **Spec section modified:** §8, Documentation canonization pattern

---

## Stage 1: decompose

### Axioms

**AX-1.** Exploratory prose and canonical documentation serve different purposes and must not be conflated.

**AX-2.** Not all claims deserve to persist. Default disposition is discard, not keep.

**AX-3.** A claim's destination is as important as its fitness. Valid claim in wrong artifact is misplaced, not preserved.

**AX-4.** Canonization is a pipeline, not a judgment call. Each stage has distinct responsibility.

### Derivations

**DV-1.** Fitness gate must apply before routing, not after. (AX-2, AX-3)

**DV-2.** Ranking after routing is necessary because fitness is binary but value is ordinal. (AX-2, AX-4)

**DV-3.** Synthesis must produce patch-like text, not standalone prose. (AX-1, AX-3)

**DV-4.** The `classify` operator is the structural bottleneck. (AX-3, AX-4)

### Assumptions

**AS-1.** Destination taxonomy is stable and exhaustive (spec, ADR, agent instructions, open question, archive, discard). Load-bearing: yes.

**AS-2.** Single compound fitness criterion ("durable, operational, non-obvious, scoped, low-regret") is sufficient. Load-bearing: yes. Testable: compare compound vs per-dimension filter decisions.

**AS-3.** Recipe can run within 7-call budget. Load-bearing: no. Cost = K + M + 3 for K claims, M survivors.

**AS-4.** Exploratory prose contains extractable discrete claims. Load-bearing: yes. Testable: run on three prose styles.

---

## Stage 2: invert

### Anti-goals

**AG-1.** Recipe promotes every claim that sounds smart, turning canonical docs into mirror of exploratory prose.

**AG-2.** Fitness gate so conservative nothing passes — correct by construction but useless.

**AG-3.** Recipe runs but nobody applies output because synthesis is harder than just editing the spec directly.

### Failure modes

**FM-1.** Compound fitness criterion collapses under LLM evaluation — anchoring on "durable"/"operational", satisficing on "non-obvious"/"low-regret". Likelihood: high. Severity: costly. Preventable by: per-dimension evaluation.

**FM-2.** Budget blowout — cost = K + M + 3, exceeds 7-call ceiling for any non-trivial input. Likelihood: high. Severity: fatal (Model A). Preventable by: accept Model C from start.

**FM-3.** Classify produces confident misplacements — routes without seeing target document content. Likelihood: medium. Severity: costly. Preventable by: operator-confirmed routing with structural summaries.

**FM-4.** Patch-like synthesis output unintegrable — synthesizer doesn't receive target document structure. Likelihood: medium. Severity: costly. Preventable by: bind target document as context.

**FM-5.** Decompose extracts claims that don't survive decontextualization. Likelihood: medium. Severity: recoverable. Preventable by: extract claims with justification attached.

### Near misses

**NM-1.** "Discard" as peer destination prevents force-fitting — holds as long as classify prompt doesn't frame discard as failure state.

**NM-2.** Auditability holds because design assumes Model A traces; migrating to Model C loses per-step guarantees.

**NM-3.** ADR-004 fitness criteria are dillylang-specific — reuse on other projects would apply wrong criteria silently.

---

## Stage 3: synthesize

### Proposal

Design canonize as Model C recipe with three structural changes:
1. Replace compound fitness criterion with per-dimension evaluation
2. Make routing operator-confirmed, not automatic dispatch
3. Feed target document structure into synthesis

### Key conflict resolved

**CA-1.** Decompose AX-4 (don't collapse stages) vs. invert FM-2 preventable_by (batch filter into rank to fit budget). Resolution: accept Model C, preserve all stages. Batching rejected because it violates AX-4.

### Open questions

**OQ-1.** Right granularity for claim extraction — argumentative prose resists atomic decomposition. Untested.

**OQ-2.** Should recipe be implemented as Model C skill now, or wait for proven `classify`?

**OQ-3.** If canonize becomes reusable, fitness dimensions need to be steering parameter via `bind`.

---

## Stage 4: apply

Changes applied to `spec/INDEX.md` §8 (Documentation canonization pattern):
- Marked as Model C recipe with budget arithmetic
- Per-dimension fitness gate replacing compound criterion
- Operator-confirmed routing with structural summaries
- Target document context in synthesis step
- Claim extraction with justification preservation
- "Discard as peer destination" prompt guidance

---

## Stage 5: evaluate

**Criterion:** Did each stage contribute non-redundant, traceable signal to the final spec edit?

**Verdict:** pass

**Key evidence:** CA-1 resolved a genuine conflict between decompose and invert (don't collapse stages vs. batch to fit budget) with explicit reasoning. Each stage had distinct leverage: decompose found structural axioms, invert found failure mechanisms, synthesize resolved conflicts. No stage was redundant.

**Confidence:** high
