---
name: dillylang-suggest-thought-move
description: Suggests exactly one next Dillylang thought move based on the current context. Use when the user asks what thinking move to make next, seems stuck, or has ambiguous reasoning state.
---

# Dillylang `suggest-thought-move`

Suggest one next thought move for the current context.

This is a meta-move: it does not solve the problem directly. It chooses the next Dillylang move that would most improve the reasoning state.

## Inputs

- Current conversation context
- Optional explicit goal, artifact, or constraint
- Optional candidate move set

Default candidate moves:

- `decompose` — when foundations, assumptions, or load-bearing claims are unclear
- `rotate` — when the frame seems stuck or the implicit subject may be wrong
- `invert` — when failure modes or avoidance criteria are more useful than direct pursuit
- `evaluate` — when there is an artifact and a criterion
- `rank` — when there are multiple candidates and selection criteria
- `synthesize` — when multiple upstream artifacts need integration
- `translate` — when mapping an existing skill/workflow into Dillylang vocabulary

## Selection rule

Return exactly one move.

Prefer the move that removes the largest current reasoning bottleneck with the least extra machinery.

Do not provide a menu unless explicitly asked.

## Output template

### Suggested move

`/dillylang-<move>`

### Why this move now

One or two sentences naming the bottleneck it addresses.

### Exact next invocation

A concrete prompt the user can run next.

### Expected artifact

What the move should produce.

### Not choosing

Briefly name one plausible alternative and why it is not first.
