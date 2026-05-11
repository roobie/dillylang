"""Shared execution routing for combinator children.

execute_node is the single dispatch point that all combinators use to
run their children. It routes:
  - Combinator nodes (is_combinator=True) -> .run() directly
  - Leaf operators -> run_operator_with_retry (budget/trace/retry)

This prevents double-wrapping when nested combinators appear as steps
in an outer combinator (e.g. pipe(decompose, parallel(invert, rotate))).
"""

from __future__ import annotations

from typing import Any

from dillylang.runner.runner import run_operator_with_retry
from dillylang.vocab.types import Context, RunResult


def execute_node(node: Any, input: Any, ctx: Context) -> RunResult:
    """Route a pipeline node to the correct execution path.

    Combinators manage their own children and budget internally,
    so they get .run() called directly. Leaf operators need the
    runner's budget/trace/retry wrapper.
    """
    if getattr(node, "is_combinator", False):
        return node.run(input, ctx)
    return run_operator_with_retry(node, input, ctx)
