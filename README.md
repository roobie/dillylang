---
id: dillylang::readme
description: Public introduction to the Dillylang reasoning vocabulary
tags: [readme, intro, public]
created: 2026-05-11
status: active
---

# Dillylang

A formal vocabulary for reasoning about thought processes — a typed
vocabulary of orthogonal thinking moves (operators), composable into
recipes runnable by a human, a model, or a pipeline.

> **Status:** early. The vocabulary is the product; substrates
> (Python, Claude Code skills) are implementation details. Interfaces
> may shift.

## Premise

Not an agent framework — no loops, no tool use. Recipes are deliberate
compositions of pure-ish operators. Every run emits an inspectable
trace; budgets are enforced.

```python
refine = pipe(decompose, parallel(invert, rotate), synthesize)
result = refine.run({"problem": "..."})
```

The design principle:

> Maximize coverage of orthogonal axes of thought, subject to a depth budget.

## The vocabulary

Nine **transformers** across six axes:

| Axis             | Operators                |
|------------------|--------------------------|
| Compositionality | `decompose`, `synthesize`|
| Negation         | `invert`                 |
| Frame            | `rotate`                 |
| Analogy          | `analogize`              |
| Abstraction      | `abstract`, `concretize` |
| Constraint       | `constrain`, `relax`     |

Plus **judges** (`evaluate`, `classify`, `compare`, `rank`) and
**meta-skills** (`translate`, `canonize`, …).

**Combinators:** `pipe`, `parallel`, `map`, `filter`.

## Example

A worked self-application: designing the `canonize` recipe (which
decides what exploratory prose deserves to enter the canonical spec)
*using* the vocabulary itself. The pipeline `decompose → invert →
synthesize → apply → evaluate` produced three structural changes to
spec §8 that were applied in the same session.

See [`examples/canonize-recipe-analysis.md`](examples/canonize-recipe-analysis.md).

## Where to read

- [`spec/PRIMER.md`](spec/PRIMER.md) — operational reference (start here)
- [`spec/INDEX.md`](spec/INDEX.md) — full spec with rationale
- [`docs/decisions/`](docs/decisions/) — ADRs (001–010)
- [`skills/`](skills/) — operator implementations as Claude Code skills
- [`examples/`](examples/) — captured pipeline traces

## Skills

The directory [`skills/`](skills/) is the canonical source for the
markdown skill packages. Agent runtimes can install them with:

```bash
npx skills add https://github.com/roobie/dillylang
# or
bunx skills add https://github.com/roobie/dillylang
```

Don't edit installed copies — they're populated from this directory.

## Contributing

Discussions welcome; PRs not yet accepted. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Acknowledgements

The `invert` operator is named after the discipline Charlie Munger
popularized — *"Invert, always invert"* — which he in turn credited
to Carl Gustav Jacob Jacobi (*man muss immer umkehren*). The
vocabulary owes its bias toward inverting questions to both.

## Citation

```bibtex
@software{roberg_dillylang_2026,
  author  = {Roberg, Björn},
  title   = {Dillylang: a formal vocabulary for reasoning about thought processes},
  year    = {2026},
  url     = {https://github.com/roobie/dillylang},
  note    = {Pre-1.0; interfaces may change. DOI pending.}
}
```

## License

Dual-licensed. Code is **Apache-2.0**; docs and spec are **CC BY 4.0**.
See [`LICENSING.md`](LICENSING.md) for the per-path mapping, and
[`LICENSE.apache20.txt`](LICENSE.apache20.txt) /
[`LICENSE.ccby40.txt`](LICENSE.ccby40.txt) for the legal codes.

---

Copyright © 2026 Björn Roberg
