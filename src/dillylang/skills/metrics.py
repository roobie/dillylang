"""Static orthogonality metrics for recipe structure analysis.

Pure functions: no LLM calls, no budget consumption, no substrate dependency.
Computes coverage, depth, cost, cost_efficiency, depth_efficiency from a
DillylangSkillDescription's operator list and pseudocode structure.

Per D-06, D-08, D-10:
  - coverage = distinct axes touched by recipe operators
  - depth = critical path length (tree height of combinator structure)
  - cost = count of LLM-calling operators
  - cost_efficiency = coverage / cost (resource-oriented)
  - depth_efficiency = coverage / depth (structural, substrate-independent)
"""

from __future__ import annotations

import re

from dillylang.vocab.schemas import DillylangSkillDescription, RecipeMetrics
from dillylang.vocab.types import RunResult

# Operator-to-axis mapping per spec section 5.
# Only transformer operators touch thinking axes; judges and combinators don't.
_OPERATOR_AXES: dict[str, str] = {
    "decompose": "compositionality",
    "synthesize": "compositionality",
    "invert": "valence",
    "rotate": "frame",
    "analogize": "substrate",
    "abstract": "abstraction",
    "concretize": "abstraction",
    "constrain": "feasibility",
    "relax": "feasibility",
}

# Judge operators (classify, evaluate, rank, compare) do not touch a
# thinking axis -- they produce meta-information about artifacts.
# Combinators (pipe, parallel, bind, map, filter, branch) are structural,
# not axis-bearing.

_ALL_AXES = frozenset(
    {"compositionality", "valence", "frame", "substrate", "abstraction", "feasibility"}
)

# All operators that make LLM calls (transformers + judges).
# Combinators and deterministic adapters do NOT count.
_LLM_OPERATORS = frozenset(
    {
        "decompose",
        "synthesize",
        "invert",
        "rotate",
        "analogize",
        "abstract",
        "concretize",
        "constrain",
        "relax",
        "evaluate",
        "rank",
        "classify",
        "compare",
    }
)


def _compute_depth(pseudocode: str) -> int:
    """Compute critical path length (tree height) from pseudocode structure.

    Parse combinator structure:
      - pipe(a, b, c) -> depth = sum of children depths
      - parallel(a, b) -> depth = max of children depths (counts as 1 step)
      - bind(op, ...) -> depth = depth of inner op (compile-time currying)
      - map(op) -> depth = depth of inner op
      - filter(op) -> depth = depth of inner op
      - branch(classifier, {label: pipeline, ...}) -> 1 + max(branch depths)
      - bare operator name -> depth = 1

    Falls back to counting unique LLM operators if parsing fails.
    """
    stripped = pseudocode.strip()
    if not stripped:
        return 0
    try:
        return _parse_depth(stripped)
    except (ValueError, IndexError):
        # Fallback: count distinct LLM operators mentioned
        operators_found = set()
        for op in _LLM_OPERATORS:
            if op in stripped:
                operators_found.add(op)
        return len(operators_found) if operators_found else 0


def _parse_depth(expr: str) -> int:
    """Recursive descent parser for combinator depth computation."""
    expr = expr.strip()
    if not expr:
        return 0

    # Try to match combinator pattern: name(...)
    match = re.match(r"^(\w+)\s*\(", expr)
    if match:
        combinator = match.group(1)
        # Extract inner content (handle nested parens)
        inner = _extract_inner(expr, match.end() - 1)

        if combinator == "pipe":
            # pipe: sum of children depths
            children = _split_top_level(inner)
            return sum(_parse_depth(c) for c in children)

        elif combinator == "parallel":
            # parallel: max of children depths (counts as 1 sequential step)
            children = _split_top_level(inner)
            child_depths = [_parse_depth(c) for c in children]
            return max(child_depths) if child_depths else 0

        elif combinator == "bind":
            # bind: depth of the inner operator (compile-time, not runtime)
            children = _split_top_level(inner)
            if children:
                return _parse_depth(children[0])
            return 0

        elif combinator in ("map", "filter"):
            # map/filter: depth of inner op (applies to each item)
            children = _split_top_level(inner)
            if children:
                return _parse_depth(children[0])
            return 0

        elif combinator == "branch":
            # branch: 1 (classifier) + max(branch pipeline depths)
            children = _split_top_level(inner)
            if len(children) >= 2:
                # First child is classifier (depth 1), rest are branch pipelines
                branch_depths = [_parse_depth(c) for c in children[1:]]
                return 1 + (max(branch_depths) if branch_depths else 0)
            elif children:
                return _parse_depth(children[0])
            return 0

        else:
            # Unknown combinator treated as single operator
            return 1

    # Bare operator name (no parens) -> depth = 1
    if re.match(r"^\w+$", expr):
        return 1

    # Fallback for unrecognized format
    raise ValueError(f"Cannot parse depth from: {expr!r}")


def _extract_inner(expr: str, open_paren_idx: int) -> str:
    """Extract content between matching parentheses."""
    depth = 0
    for i in range(open_paren_idx, len(expr)):
        if expr[i] == "(":
            depth += 1
        elif expr[i] == ")":
            depth -= 1
            if depth == 0:
                return expr[open_paren_idx + 1 : i]
    # No matching close paren — return everything after open
    return expr[open_paren_idx + 1 :]


def _split_top_level(inner: str) -> list[str]:
    """Split comma-separated arguments respecting nested parentheses and braces."""
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for ch in inner:
        if ch in "({[":
            depth += 1
            current.append(ch)
        elif ch in ")}]":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    remainder = "".join(current).strip()
    if remainder:
        parts.append(remainder)
    return [p for p in parts if p]


def compute_metrics(description: DillylangSkillDescription) -> RecipeMetrics:
    """Compute static orthogonality metrics from recipe structure.

    Deterministic: no LLM call, no budget consumption.
    Operates on the DillylangSkillDescription from translate's output.

    Args:
        description: A translated skill description containing operators
                     and pseudocode.

    Returns:
        RecipeMetrics with coverage, depth, cost, cost_efficiency, depth_efficiency.
    """
    # Coverage: distinct axes touched by listed operators
    axes_touched = {
        _OPERATOR_AXES[op]
        for op in description.dillylang_operators
        if op in _OPERATOR_AXES
    }
    coverage = len(axes_touched)

    # Depth: critical path from pseudocode structure
    depth = _compute_depth(description.dillylang_pseudocode)

    # Cost: count of LLM-calling operators in the recipe
    cost = sum(1 for op in description.dillylang_operators if op in _LLM_OPERATORS)

    # Efficiency: dual ratios per D-06
    cost_efficiency = round(coverage / cost, 4) if cost > 0 else 0.0
    depth_efficiency = round(coverage / depth, 4) if depth > 0 else 0.0

    return RecipeMetrics(
        coverage=coverage,
        depth=depth,
        cost=cost,
        cost_efficiency=cost_efficiency,
        depth_efficiency=depth_efficiency,
        axes_touched=sorted(axes_touched),
        axes_missing=sorted(_ALL_AXES - axes_touched),
    )


def compute_efficacy(run_result: RunResult) -> float:
    """Compute efficacy: non-trivial contributions / total upstream artifacts.

    Per D-05: non-trivial = incorporates entry with non-empty contribution string.
    Per D-06: computed per single RunResult. Same grain as other metrics.
    Denominator: all artifacts in RunResult.artifacts except synthesize itself.

    Returns 0.0 if no synthesize artifact found or no upstream artifacts.
    """
    if not run_result.artifacts:
        return 0.0

    # Find the synthesize artifact (operator name starts with "synthesize")
    synth_id = None
    synth_data = None
    for aid, artifact in run_result.artifacts.items():
        if artifact.operator.startswith("synthesize"):
            synth_data = artifact.data
            synth_id = aid
            break

    if synth_data is None:
        return 0.0

    # Count non-trivial contributions (non-empty contribution strings)
    incorporates = synth_data.get("incorporates", [])
    non_trivial = sum(
        1
        for inc in incorporates
        if isinstance(inc, dict) and inc.get("contribution", "").strip()
    )

    # Denominator: all artifacts except synthesize itself
    total_upstream = len(run_result.artifacts) - (1 if synth_id else 0)
    if total_upstream <= 0:
        return 0.0

    return round(non_trivial / total_upstream, 4)
