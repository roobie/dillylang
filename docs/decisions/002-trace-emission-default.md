---
id: dillylang::adr-002
description: Decision to emit traces by default but make persistence opt-in
tags: [architecture, traces, privacy]
created: 2026-04-30
status: active
---

# 002 — Trace emission default, persistence optional

## Status

Accepted

## Context

Traces are the system's killer feature — every pipeline run should be
inspectable. But traces contain rendered prompts, raw LLM responses,
and user-provided problem statements, which may include sensitive
content. Two concerns pull in opposite directions:

1. **Debuggability.** Traces should always be available for inspection.
   The whole point of Model A (discrete operators) over Model C (holistic
   skills) is per-step visibility. If traces are opt-in, most runs won't
   have them, and the primary value proposition is lost.
2. **Privacy.** Persisting traces to disk, logs, or shared storage
   creates a data retention surface. Prompts and responses may contain
   proprietary information, PII, or confidential problem descriptions
   that shouldn't be stored without explicit intent.

## Decision

Every pipeline run emits a trace as part of its `RunResult`:
`{ output, trace, status, errors }`. The runtime always builds the trace —
this is not configurable. Callers may discard the trace after inspection,
but cannot prevent its construction.

Emitted traces are sensitive data by default. They contain rendered
prompts, raw LLM responses, and user-provided problem statements.
Even without persistence, traces are exposed to callers, UIs, crash
reporters, notebooks, and terminal output. Non-persistence reduces
retention risk, not exposure risk.

Trace **persistence** (writing to disk, database, or logging service)
is separate and opt-in. A caller must explicitly configure a persistence
sink. Persistent sinks must support redaction and retention controls.
Traces are not sent to shared logs by default.

## Why this split

- **Emission is cheap and ephemeral.** The trace lives in memory for
  the duration of the caller's use. Lower retention risk than persistence,
  but callers must still treat emitted traces as sensitive.
- **Persistence is a deliberate act.** The caller decides what to store
  and where, with full control over redaction.
- **Preserves the debugging value.** Every run is inspectable in-session
  without requiring the user to opt in to anything.

## Consequences

- The runner always builds the trace, even if the caller ignores it.
  Minor performance cost (memory for trace entries), acceptable at v0
  pipeline sizes (ceiling: 7 LLM calls).
- Callers who want trace history must configure a sink. This is
  intentional friction — it forces a conscious decision about where
  sensitive data goes.
- The persisted larder (open question 4 in the spec) will eventually
  need a trace storage design. When built, it inherits the redaction
  and retention requirements from this decision. [[THIS grounds: urn:unique_reference:dillylang::spec-index]]
