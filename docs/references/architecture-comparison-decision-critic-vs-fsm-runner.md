---
id: dillylang::arch-comparison-decision-critic-vs-fsm-runner
description: Dillylang operator chain (decompose → invert → rotate → synthesize) comparing decision-critic skill architecture to FSM recipe runner
tags: [architecture, comparison, decision-critic, fsm-runner, dillylang-analysis]
created: 2026-05-05
status: active
---

# Architecture Comparison: Decision-Critic vs FSM Runner

[[THIS is_grounded_by: urn:unique_reference:dillylang::spec-index]]

**Method:** Dillylang operator chain — `decompose` → `invert` → `rotate` → `synthesize`

**Subjects:**
- Decision-critic skill (`~/devel/claude-config/skills/decision-critic/`) — 7-step structured criticism workflow, ~270 LOC Python + ~50 LOC shared library
- FSM recipe runner (`dillylang.agent_skills.fsm_runner`) — session-based recipe executor, ~710 LOC Python + Pydantic schemas + YAML recipes

**Question:** Is the decision-critic's architecture superior to the FSM runner's?

---

## 1. Decompose

Ten orthogonal structural facets where the two architectures make different choices.

| # | Facet | Decision-Critic | FSM Runner |
|---|---|---|---|
| **D1** | **Where does step state live?** | LLM context window — no filesystem persistence between steps | Filesystem sessions (`~/.local/state/...`) with `pending/` → `state/` handshake |
| **D2** | **What enforces step ordering?** | Each step's stdout emits a literal shell command for the next step; the LLM must obey the directive | `meta.json` tracks `current_step`; `submit` refuses out-of-order steps |
| **D3** | **What validates step output?** | Nothing — the LLM is trusted to produce conforming prose | Pydantic models from `dillylang.vocab.schemas`; repair-once-then-fail on `ValidationError` |
| **D4** | **How is the workflow defined?** | Hardcoded Python constants (`STATIC_STEPS`, `DYNAMIC_STEPS`) — one workflow, one shape | Declarative YAML recipes with `flow:`, `steps:`, `input:` — arbitrary operator sequences |
| **D5** | **How do steps reference prior outputs?** | Implicitly via LLM context window (all prior output is "visible") | Explicitly via `$step.field` references resolved from `state/<step>.json` files |
| **D6** | **What is the budget/resource model?** | None — 7 steps hardcoded, no enforcement | Configurable `budget_ceiling` with tracked `budget_used`; session fails on exhaustion |
| **D7** | **How much coupling to the content domain?** | Fully coupled — prompts are decision-criticism-specific, non-reusable | Domain-agnostic runner; domain lives in recipe YAML + operator schemas |
| **D8** | **What is the failure/recovery model?** | None — if the LLM hallucinates or diverges, there's no checkpoint to resume from | Repair-once retry on validation failure; sessions are resumable; GC handles abandonment |
| **D9** | **What is the shared-library contract?** | `format_step()` — a string assembler (~50 LOC) providing title/body/next-command formatting | Operator registry, Pydantic schemas, YAML recipe parser, reference resolver, session manager (~700 LOC) |
| **D10** | **Who is the "executor"?** | The in-session LLM does everything: reads the prompt, thinks, produces output, invokes next command | The in-session LLM produces structured JSON; the runner validates, persists, and advances |

---

## 2. Invert

What if the decision-critic's choices are the *correct* ones? For each facet, the case that the FSM runner is over-engineered and the decision-critic's simplicity is architecturally superior.

| # | Facet | Inverted argument |
|---|---|---|
| **D1** | State in context window vs filesystem | The LLM context window *is* the state store — and it's richer than JSON files. It retains nuance, hedging, and reasoning chains that structured serialization necessarily discards. The FSM runner forces lossy compression (prose → JSON → prose) at every step boundary. |
| **D2** | Directive-based ordering vs enforced ordering | A `format_step` directive is *exactly* as reliable as `meta.json` enforcement — both depend on the LLM obeying instructions. The FSM runner adds a guard that only fires when the LLM has *already failed to follow instructions*, meaning the guardrail catches a failure mode it can't actually recover from gracefully. |
| **D3** | No validation vs Pydantic validation | Schema validation catches *format* errors, not *reasoning* errors. A perfectly valid `DecomposeOutput` can contain garbage sub-problems. The decision-critic accepts that the LLM either reasons well or doesn't — adding structural validation creates false confidence that the output is "correct." |
| **D4** | Hardcoded workflow vs declarative recipes | A single-purpose tool with a fixed workflow is easier to audit, debug, and maintain. The YAML recipe system pays generality tax on every run: parsing, structural validation, reference resolution — all for flexibility that only matters if you build *many different recipes*. The decision-critic ships one workflow that works. |
| **D5** | Implicit context vs explicit $references | Explicit references force the workflow author to predict which fields downstream steps need — a leaky abstraction. The LLM-as-context approach lets each step access *everything* from prior steps, including unexpected signals the recipe author didn't anticipate. The FSM runner's reference system is a manually-wired information bottleneck. |
| **D6** | No budget vs budget enforcement | Budget enforcement assumes LLM calls are the scarce resource. In an in-session skill, the LLM is *already running* — the marginal cost of step 8 is near zero. Budget tracking is cargo-culted from the DSPy substrate where calls are API-billed; in the skill substrate it solves a problem that doesn't exist. |
| **D7** | Domain-coupled vs domain-agnostic | Domain coupling means the prompts are *tuned*. The decision-critic's 7 steps encode research-grounded methodology (Chain-of-Verification, Self-Consistency). The FSM runner's generality means every recipe must reinvent prompt quality from scratch in YAML — a format hostile to prompt iteration. |
| **D8** | No recovery vs repair-once retry | Repair-once retry assumes validation failures are *fixable by re-prompting* — but the LLM that produced invalid JSON once is unlikely to produce valid JSON on the second try without different instructions. The decision-critic sidesteps this by not requiring structured output at all, eliminating the failure mode rather than handling it. |
| **D9** | ~50 LOC shared library vs ~700 LOC runner | 50 LOC has fewer bugs, fewer failure modes, and is auditable in one screen. The 700 LOC runner already has a TECH-DEBT file tracking 7 failure modes. The decision-critic's `format_step` has zero known bugs because there's almost nothing to get wrong. |
| **D10** | LLM does everything vs LLM produces JSON for a validator | Making the LLM produce JSON for machine consumption *degrades its reasoning*. The LLM's strength is prose; forcing structured output activates a different (weaker) generation mode. The decision-critic lets the LLM do what it's good at. |

**Inverted core thesis:** The FSM runner builds enforcement machinery around a fundamentally cooperative executor (the LLM), paying complexity costs for guarantees that are either illusory (D3, D8) or irrelevant to the deployment context (D6). The decision-critic is honest about the trust model.

---

## 3. Rotate

Dropping both the "which is superior?" frame and its inversion. Reframing: what problem class does each architecture actually solve, and are they even competing?

### These are two points on a design spectrum, not alternatives

The spectrum is **trust in executor fidelity**.

```
Full trust                                              Zero trust
(executor is cooperative & capable)                     (executor is adversarial or brittle)
    │                                                       │
    ▼                                                       ▼
 decision-critic                    FSM runner           formal verifier
 "emit prompt,                     "emit prompt,        "prove output
  hope for the best"               validate before       satisfies spec"
                                    advancing"
```

The decision-critic is designed for **one LLM, one session, one conversation** — the executor that reads step 4's output *is the same context* that produced it. Validation is redundant because the producer and consumer are the same entity.

The FSM runner is designed for **decoupled producer/consumer** — the recipe author, the executing LLM, and the validation schema are three independent parties. The runner doesn't trust the LLM because the recipe wasn't written by the LLM and the schema wasn't either.

### Three observations

**R1: The decision-critic can't leave the session.** Its "state" is the conversation. You can't pause, hand off to another agent, resume tomorrow, or audit after the fact. This isn't a limitation — it's a *design choice*: the workflow is synchronous and ephemeral by construction. The FSM runner's filesystem state is the price of asynchrony and auditability.

**R2: The FSM runner can't tune its prompts.** The decision-critic's prompts are lovingly crafted Python strings with research citations. The FSM runner's prompts live in YAML `prompt:` fields — one flat string per step, no templating, no conditional logic, no decomposition into instructional sub-parts. The runner traded prompt quality for prompt portability.

**R3: They converge on the same interaction pattern.** Strip away the infrastructure and both architectures do this:

```
loop:
  1. emit instructions + context to stdout
  2. LLM reads, thinks, produces output
  3. (optional: validate output)
  4. advance to next step
```

The decision-critic fuses steps 1–4 into a single `print()` → LLM → `print()` chain. The FSM runner separates them with filesystem I/O and a CLI boundary. The *interaction shape* is identical; the *trust boundary placement* differs.

### The question this rotation surfaces

Neither architecture addresses the actual hard problem: **how do you know the LLM's reasoning was good?**

The decision-critic doesn't try. The FSM runner validates *structure* but not *substance*. Both punt on evaluation — which is the one operator in the Dillylang pantry (`evaluate`) that neither system invokes on its own outputs.

A genuinely superior architecture would close this loop: run the workflow, then run `evaluate` on the trace, then feed evaluation findings back. Neither does this. The FSM runner has the *infrastructure* to do it (structured outputs, session persistence, step references) but doesn't wire it up. The decision-critic *could* add an 8th self-evaluation step but has no way to act on the findings mechanically.

---

## 4. Synthesize (without averaging)

The inversion and rotation don't split evenly — they point in the same direction once you stop treating these as competing designs.

### The decision-critic is a prompt artifact. The FSM runner is a protocol.

The decision-critic's value is entirely in its prompts: Chain-of-Verification decomposition, factored verification with epistemic boundaries, steel-manned contrarian generation. Remove `format_step` and replace it with a markdown document and you lose nothing. The Python script is a delivery mechanism for 7 carefully-written prompts. Its architecture is trivial *on purpose* — the intellectual work is in the prompt text.

The FSM runner's value is entirely in its enforcement protocol: schema validation, reference resolution, session persistence, budget tracking. The prompts it delivers are whatever the recipe author wrote in YAML. Its architecture is complex *on purpose* — the intellectual work is in the handshake contract.

**These aren't two solutions to one problem. They're two layers that neither system has both of.**

### What's actually missing

The decision-critic has **prompt quality** but no **enforcement or persistence**. If the LLM drifts at step 4, there's no checkpoint, no structural validation, no way to detect it happened.

The FSM runner has **enforcement and persistence** but no **prompt quality infrastructure**. YAML `prompt:` fields are flat strings — no decomposition into instructional sub-parts, no conditional phrasing, no research-grounded methodology baked in. Every recipe author reinvents prompt craft from scratch.

The rotate operator surfaced that neither addresses **output quality evaluation**. But the deeper gap is simpler: nobody has built the thing where *good prompts run inside an enforcing protocol*.

### The FSM runner is the stronger foundation — but not for the reason it thinks

The FSM runner's advantage isn't validation (D3/D8 from the inversion showed that catching format errors while missing reasoning errors is weak assurance). Its advantage is that **it separates the workflow definition from the execution engine**. This separation is what makes it possible to:

- Audit a run after the fact (session persistence)
- Resume a failed run without replaying from scratch
- Run the same recipe across different LLMs and compare traces
- Add evaluation as a post-processing step over structured state files

The decision-critic can do none of these — not because it's badly built, but because fusing prompt delivery with LLM execution into a single context-window pass is architecturally a dead end for anything beyond single-shot use.

### The decision-critic is the stronger skill — but it's trapped in the wrong container

The 7-step methodology is genuinely good. The prompt decomposition (claims → verifiability classification → falsification questions → factored verification → contrarian → reframing → verdict) is tighter than anything the FSM runner's current recipes contain. But it's trapped in hardcoded Python strings that can't be reused, composed, or adapted.

If those prompts were a YAML recipe with proper operator mappings, they'd be the FSM runner's best recipe. They're not, because the decision-critic was written before the FSM runner existed.

### Verdict (without averaging)

**The FSM runner's architecture is superior as a *protocol*.** Separation of workflow definition from execution, filesystem-based session state, and schema-validated step transitions are the right structural choices for a system that will run many different workflows across different models.

**The decision-critic's architecture is superior as a *single skill*.** For a fixed, well-understood workflow executed once in a live session, the overhead of filesystem sessions and JSON serialization is pure cost with no benefit.

**The actual work to do:** port the decision-critic's prompts into a Dillylang recipe that runs on the FSM runner. The prompts gain enforcement and persistence; the runner gains its first research-grounded recipe. Neither system is complete alone.

---

## Provenance

- **Operator chain:** `decompose` → `invert` → `rotate` → `synthesize`
- **Session:** 2026-05-05, interactive Claude Code conversation
- **Source files examined:**
  - `~/devel/claude-config/skills/decision-critic/SKILL.md`
  - `~/devel/claude-config/skills/scripts/skills/decision_critic/decision_critic.py` (~270 LOC)
  - `~/devel/claude-config/skills/scripts/skills/lib/workflow/prompts/step.py` (~50 LOC)
  - `dillylang/src/dillylang/agent_skills/fsm_runner.py` (~710 LOC)
  - `dillylang/skills/scripts/TECH-DEBT-dillylang-run.md`
- **Constraint:** `synthesize` was applied without averaging — the verdict privileges the strongest signal from each prior operator rather than splitting the difference
