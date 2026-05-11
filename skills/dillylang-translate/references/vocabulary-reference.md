# Dillylang Vocabulary Reference

Injected into the `rotate` step via `bind(rotate, target_frame=...)`.
Use ONLY these names when restating skill stages as Dillylang expressions.

## Operators (thinking moves that transform artifacts)

| Operator | Purpose |
|---|---|
| `decompose` | Break into axioms, derivations, assumptions |
| `synthesize` | Integrate multiple artifacts into coherent proposal |
| `invert` | Find what guarantees failure (Munger/Jacobi inversion) |
| `rotate` | Change the axis of inquiry or viewpoint |
| `analogize` | Find structural analogies in other domains |
| `abstract` | Extract general principles from concrete instances |
| `concretize` | Produce concrete instances from abstract principles |
| `constrain` | Narrow the solution space with explicit boundaries |
| `relax` | Widen the solution space by removing constraints |
| `evaluate` | Judge an artifact against an explicit criterion |
| `rank` | Order artifacts by criteria (returns IDs only) |
| `compare` | Side-by-side comparison of two artifacts |
| `classify` | Assign labels from taxonomies |

## Combinators (compose operators into pipelines)

| Combinator | Purpose |
|---|---|
| `pipe` | Sequential — output of step N feeds step N+1 |
| `parallel` | Fan-out/fan-in — same input to multiple operators, collect results |
| `bind` | Typed currying — fix steering parameters at compose time |
| `map` | Apply an operator to each item in a collection |
| `filter` | Keep/drop items based on operator verdict (pass/partial=keep, fail=drop) |
| `branch` | Conditional dispatch — classify then route to sub-pipelines |

## Recipe notation

A recipe is expressed as nested combinator calls:

```
pipe(parallel(decompose, invert, rotate), synthesize)
```

Each operator produces a typed artifact with specific fields. Map each stage
of the input skill to the closest operator(s) and combinator structure.
