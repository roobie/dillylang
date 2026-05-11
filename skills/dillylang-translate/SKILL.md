---
name: dillylang-translate
description: Translate a Claude Code skill directory into a Dillylang recipe description — deterministic ingestion, 5-step recipe runner pipeline. Use when the user wants to translate, convert, express, or describe a skill in Dillylang vocabulary.
---

# Translate Skill to Dillylang

## When to use

- "translate this skill to Dillylang"
- "what's the Dillylang recipe for [skill]?"
- "express [skill] in Dillylang vocabulary"

## Execution

### Phase 1 — Ingest (deterministic, no LLM)

Read the skill directory and build a JSON source bundle:

1. Read SKILL.md. If absent, stop.
2. Follow external references — `<invoke>` tags, script paths, module imports.
   Read the implementation files where the skill's actual logic lives.
3. Read remaining files (README, prompts/, scripts/, configs). Cap at 20 files / ~50KB.
4. Detect entrypoints, tool use patterns, and control flow.
5. Format as JSON string for `skill_source_bundle`.

### Phase 2 — Recipe runner pipeline

Start the recipe runner with the ingested bundle:

```bash
python3 -m skills.scripts.recipe_runner start \
  --recipe skills/scripts/recipes/translate.py \
  --input '{"skill_source_bundle": "<ingested JSON>"}'
```

Follow the runner's emit/submit protocol for all 5 steps. The recipe file
(`skills/scripts/recipes/translate.py`) contains all prompts and operator
lineage. Each step's output is arbitrary JSON matching the schema described
in that step's prompt.

### Reflection

After the pipeline completes, the `synthesize` output IS the product. Add
2–3 sentences: which steps produced sharpest signal, where classify and
evaluate agreed vs. diverged, and whether residue suggests vocabulary gaps
worth tracking.
