---
id: dillylang::claude
description: Claude Code project instructions for the compositional thinking-frameworks pipeline
tags: [meta, claude-code]
created: 2026-04-30
status: active
---

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md

## Status

Planning complete. 4-phase roadmap with 33 requirements defined. No code yet.

## Build / test commands

None yet. When implementation begins:

```bash
# Expected (not yet set up):
# uv add dspy-ai pydantic
# uv run pytest
# uv run mypy src/
# uv run ruff check .
```

## Implementation sequence

Follow the 4-phase roadmap (`.planning/ROADMAP.md`):

1. **Vocabulary + Substrate** — Pure types, DSPy adapter, v0 operators, combinators, runner with budget/trace/retry
2. **Axis Completion + Router** — classify/branch, abstract/concretize, constrain/relax, compare, steering params
3. **Meta-Skills** — translate, analyze, design, improve + orthogonality metrics
4. **Multi-LLM Validation** — Cross-model recipe execution and comparison

Within Phase 1, spec §11's 7-session plan gives the build order. Day 1 defines types and builds `pipe`/`bind`/`decompose`. Day 2 adds `synthesize` — the first real pipeline test. Do not skip ahead.

After each operator prompt is written, run it on at least two qualitatively-different
inputs and inspect outputs manually. Well-formed garbage is the most common failure mode.

## Claude-specific notes

- Compare operator outputs against existing Claude Code skills
  (`/lateral-shift`, `/phase-doc-review`) on the same inputs. Disagreements are
  prompt-iteration signal.

For vocabulary schemas, combinators, and constraints see `spec/PRIMER.md`.
For full design rationale and history see `spec/INDEX.md`. [[THIS is_grounded_by: urn:unique_reference:dillylang::spec-primer]]

<!-- GSD:project-start source:PROJECT.md -->
## Project

**Dillylang**

A formal vocabulary for reasoning about thought processes — concretely, a typed vocabulary of orthogonal thinking moves (operators), composable into recipes that are runnable by a human, a model, or a pipeline. The vocabulary is the product; execution substrates (Claude Code skills, DSPy pipelines, manual reasoning) are implementation details.

**Core Value:** Any thinking process (skill, workflow, reasoning chain) can be expressed, analyzed, and improved using the Dillylang vocabulary. If the vocabulary can't express a skill, the vocabulary is incomplete — not the skill.

### Constraints

- **Vocabulary-first:** Every decision prioritizes the vocabulary's expressiveness and orthogonality over implementation convenience
- **Self-application:** The vocabulary must be able to reason about itself (design_recipe designs recipes using the vocabulary it's composed of)
- **LLM-agnostic:** Recipes must be meaningful to any sufficiently capable model, not just Claude
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Executive Framing
## Recommended Stack
### Core Substrate (Runtime)
| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| DSPy | >=2.6 (current: 2.6.x) | First-class substrate for operator execution | Already locked by ADR-001. Signature-based typed I/O maps directly to operator schemas. Auto-optimization (teleprompters) is a future lever. Lowest framework overhead (~3.5ms). Active development (23k stars, 300+ contributors). | HIGH |
### Type System / Data Validation
| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Pydantic | >=2.9 | Artifact schemas, operator I/O validation, configuration | De facto Python validation standard. DSPy signatures already use Python type hints that Pydantic validates. Rust-backed validation is fast. Discriminated unions handle the `Artifact.status` enum pattern cleanly. | HIGH |
| Python typing (stdlib) | 3.11+ | Generic operator types `Operator[I, O]`, `Literal`, `TypeVar` | The spec already uses generic syntax. Python 3.11+ has `Self`, better `TypeVar`, and `TypeVarTuple`. 3.12 adds native generic syntax (`class Foo[T]:`). | HIGH |
### Structured Output Parsing (within DSPy)
| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| DSPy TypedPredictor / TypedChainOfThought | (bundled with DSPy) | Enforce Pydantic models as output schemas | DSPy's typed predictors validate output against Pydantic models with automatic retry on parse failure. This is the repair-once-then-fail-loud pattern the spec requires. | HIGH |
### Evaluation
| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| DeepEval | >=2.4 | Evaluate reasoning quality of operator outputs | 50+ built-in metrics including G-Eval (custom LLM-as-judge). Supports custom metrics via natural language criteria -- maps directly to Dillylang's `evaluate` operator. CI-friendly (pytest plugin). Most actively maintained eval framework (4k+ stars). | MEDIUM |
| Inspect AI | >=0.3 | Heavier-duty evaluation of full pipeline reasoning | UK AISI framework. 200+ pre-built evals. Reasoning-specific evaluation support. MIT licensed. Use for pipeline-level (not operator-level) quality assessment. | LOW |
### Testing
| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| pytest | >=8.0 | Test runner | Standard. DeepEval integrates as a pytest plugin. | HIGH |
| pytest-asyncio | >=0.24 | Async test support | DSPy modules may run async (parallel combinator). | HIGH |
### Project Tooling
| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| uv | >=0.5 | Package management, virtualenv | Fast, Rust-backed, replaces pip/pip-tools/venv. Already referenced in CLAUDE.md (`uv add`, `uv run`). | HIGH |
| mise | (system) | Task runner, env management | Already in the operator's workflow. Handles secrets via nanovault. | HIGH |
| ruff | >=0.8 | Linting + formatting | Single tool replaces flake8 + black + isort. Fast (Rust). | HIGH |
| mypy | >=1.13 | Static type checking | The vocabulary is a type system. `Operator[I, O]` generics must be verified statically. pyright is an alternative but mypy has better Pydantic plugin support. | MEDIUM |
### Tracing / Observability
| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Custom TraceEntry (spec section 5) | n/a | Runtime trace emission | The spec defines `TraceEntry` with `event_type`, `operator_name`, `step_index`, etc. This is the primary tracing mechanism. Build it, don't import it. | HIGH |
| OpenTelemetry (future) | >=1.29 | Export traces to external systems | Only if persistence sinks are needed. The spec says trace persistence is opt-in. OTel is the standard export format. Defer to v1+. | LOW |
## Alternatives Considered
| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Substrate | DSPy | LangChain/LCEL | Higher overhead (~10ms vs ~3.5ms), manual prompt engineering, no auto-optimization. Abstractions are pipeline-oriented, not signature/type-oriented. |
| Substrate | DSPy | LangGraph | Agent/graph-oriented. Dillylang recipes are *not* agent loops -- they're typed function compositions. LangGraph solves the wrong problem. |
| Substrate | DSPy | LMQL | Query-language paradigm is elegant but niche. Maintenance uncertain (ETH Zurich research project). No auto-optimization. Community is 10x smaller than DSPy. |
| Substrate | DSPy | Microsoft Guidance | Constrained decoding is powerful but requires token-level model access. Doesn't work with API-only models (Claude, GPT-4). Dillylang must be model-agnostic. |
| Substrate | DSPy | PydanticAI | Agent framework (v1 stable Sept 2025). Type-safe structured output, but agent-oriented (tools, system prompts, graph support). Dillylang operators are not agents. Also, PydanticAI's graph support could model recipes, but DSPy's signature-based composition is a more natural fit for typed operator vocabularies. |
| Structured Output | DSPy Signatures | BAML | Introduces separate DSL + Rust compiler. Redundant with DSPy's built-in typed parsing. |
| Structured Output | DSPy Signatures | Instructor | Redundant when DSPy handles parsing. Useful only for raw API calls, which we don't make. |
| Evaluation | DeepEval | RAGAS | RAG-specific. Dillylang is not RAG. |
| Evaluation | DeepEval | Promptfoo | Config-driven, less programmatic. DeepEval's pytest integration fits better. |
| Type Checking | mypy | pyright | Pyright is faster but mypy's Pydantic plugin is more mature. Either works. |
## Stack Architecture (How Pieces Fit Together)
## Python Version
- `Self` type (PEP 673) -- useful for `Operator.bind() -> Self`
- `ExceptionGroup` -- relevant for parallel combinator error aggregation
- `tomllib` in stdlib -- TOML config without extra deps
- 3.12's `class Foo[T]:` syntax is cleaner but 3.11 is more conservative. Pin to `>=3.11`.
## Installation
# Core
# Evaluation
# Dev dependencies
## What NOT to Use
| Technology | Reason |
|------------|--------|
| LangChain / LangGraph | Agent/pipeline framework. Wrong abstraction level. Dillylang operators are typed functions, not chain links or graph nodes. |
| CrewAI / AutoGen | Multi-agent frameworks. Dillylang explicitly forbids agent loops (spec section 1). |
| LMQL | Niche query language. Uncertain maintenance. No auto-optimization. |
| Microsoft Guidance | Requires token-level access. Incompatible with API-only models. |
| BAML | Separate DSL + compiler. Redundant with DSPy signatures. |
| Instructor | Redundant with DSPy's typed output parsing. |
| LlamaIndex | RAG-focused. Dillylang is not RAG. |
| Haystack | Pipeline framework for search/NLP. Wrong domain. |
| Semantic Kernel | Microsoft's agent/plugin framework. Enterprise-oriented, agent-loop-based. |
## Version Verification
| Technology | Claimed Version | Verification Source | Date Checked |
|------------|----------------|---------------------|--------------|
| DSPy | 2.6.x | Context7 (dspy.ai docs), WebSearch (PyPI) | 2026-04-30 |
| Pydantic | 2.9+ | Context7 (pydantic.dev) | 2026-04-30 |
| DeepEval | 2.4+ | WebSearch (PyPI, GitHub) | 2026-04-30 |
| PydanticAI | 1.x (rejected) | WebSearch (GitHub releases) | 2026-04-30 |
| Inspect AI | 0.3.x | WebSearch (UK AISI) | 2026-04-30 |
| BAML | latest (rejected) | WebSearch (BoundaryML) | 2026-04-30 |
## Sources
- [DSPy official documentation](https://dspy.ai/) -- Context7 verified, HIGH confidence
- [DSPy GitHub](https://github.com/stanfordnlp/dspy) -- 23k stars, active development
- [Pydantic documentation](https://docs.pydantic.dev/) -- Context7 verified, HIGH confidence
- [BAML / BoundaryML](https://docs.boundaryml.com/home) -- WebSearch, evaluated and rejected
- [Instructor](https://python.useinstructor.com/) -- WebSearch, evaluated and rejected
- [DeepEval](https://github.com/confident-ai/deepeval) -- WebSearch, MEDIUM confidence
- [Inspect AI](https://inspect.aisi.org.uk/) -- WebSearch, LOW confidence
- [PydanticAI](https://ai.pydantic.dev/) -- WebSearch, evaluated and rejected
- [LMQL](https://lmql.ai/) -- WebSearch, evaluated and rejected
- [Microsoft Guidance](https://github.com/guidance-ai/guidance) -- Context7 verified, evaluated and rejected
- [LangChain vs DSPy comparison](https://qdrant.tech/blog/dspy-vs-langchain/) -- WebSearch
- [Best AI Agent Frameworks 2025](https://langwatch.ai/blog/best-ai-agent-frameworks-in-2025-comparing-langgraph-dspy-crewai-agno-and-more) -- WebSearch
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
