---
id: dillylang::agents
description: Agent instructions for the compositional thinking-frameworks pipeline
tags: [meta, agents]
created: 2026-04-30
status: active
---

[[THIS is_grounded_by: urn:unique_reference:dillylang::spec-index]]
[[THIS is_grounded_by: urn:unique_reference:dillylang::handoff-v0]]

# AGENTS.md

Instructions for AI agents working in this repository.

[[THIS grounds: urn:unique_reference:dillylang::claude]]

## Recipes

When the user asks to execute/run/apply a Dillylang recipe in-session,
invoke the `dillylang-model-c-recipe-runner` skill.

## Project

See @.planning/ for roadmap, requirements, and research.

## Key documents

- `spec/PRIMER.md` — lean operational reference. Read this first. [[THIS is_grounded_by: urn:unique_reference:dillylang::spec-primer]]
- `spec/INDEX.md` — full spec with design rationale, history, and open questions.
- `.planning/ROADMAP.md` — 4-phase implementation roadmap (33 requirements).
- `.planning/REQUIREMENTS.md` — v1 requirements with REQ-IDs and traceability.
- `docs/decisions/` — ADRs for non-obvious design choices (001–008).
- `archive/HANDOFF-v0.md` — original design conversation handoff (provenance only).

## Conventions

- **Markdown frontmatter** is required on all `.md` files, except for files in `.planning/`. Required fields: `id` (repo-prefixed slug, e.g. `dillylang::my-doc`), `description` (one line), `tags` (string[], may be empty), `created` (ISO date), `status` (`draft`|`active`|`superseded`|`archived`). [[THIS is_grounded_by: urn:unique_reference:pa::adr-005]]
- **Decision records** go in `docs/decisions/NNN-short-title.md` when the "why" isn't obvious from the diff.
- **Canonization gate:** exploratory prose (riffs, reviews, model analyses) is not promoted directly into canonical docs. Extract claims, judge fitness, route to destination (`spec`/`ADR`/`AGENTS.md`/`open question`/`archive`/`discard`), rank, then synthesize patch-like text. [[THIS is_grounded_by: urn:unique_reference:dillylang::adr-004]]
- **Links:** Add typed links between documents using wiki-link syntax: `[[THIS rel: target]]`, where `rel` is one of `grounds`/`is_grounded_by`, `supersedes`/`is_superseded_by`, `contradicts`/`is_contradicted_by`, `inspires`/`is_inspired_by`, `analogous_to`. Target is a relative path or URN (`urn:unique_reference:<id>`). [[THIS is_grounded_by: urn:unique_reference:knowmux::adr-0002]]
- **Vocabulary constraints and schema rules** are in `spec/PRIMER.md`. Do not restate them here.

## Review discipline

- Do not edit files during review tasks unless the operator explicitly asks for changes.
- Reviews are read-only: report findings, don't fix them.
- `spec/INDEX.md` is the source of truth for type contracts, operator schemas, and combinator semantics. When in doubt, read the spec. [[THIS is_grounded_by: urn:unique_reference:dillylang::spec-index]]

**When reviewing output against a schema, read the schema.**

