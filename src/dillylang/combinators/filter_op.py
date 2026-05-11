"""Filter combinator: verdict-based filtering over a collection.

filter_op(predicate_op) returns a combinator that evaluates each item
using the predicate operator and keeps/drops based on the verdict.

Verdict mapping per spec section 7:
  pass   -> keep
  partial -> keep (default, configurable via keep_partial)
  fail   -> drop

Each item costs an LLM call (the predicate is typically evaluate).
Budget is consumed per item.
"""

from __future__ import annotations

from typing import Any

from dillylang.combinators._routing import execute_node
from dillylang.trace.emit import emit_combinator_end, emit_combinator_start
from dillylang.vocab.protocol import OperatorProtocol
from dillylang.vocab.types import (
    Artifact,
    ArtifactStatus,
    Context,
    ItemError,
    RunResult,
    RunResultStatus,
    TraceEntry,
)


def _extract_verdict(output: Any) -> str | None:
    """Extract verdict from predicate output.

    Looks for 'verdict' in Artifact.data (the EvaluateOutput pattern).
    Returns None if not found.
    """
    if isinstance(output, Artifact) and isinstance(output.data, dict):
        return output.data.get("verdict")
    return None


class FilterOperator:
    """Verdict-based collection filter.

    Evaluates each item with a predicate operator and keeps/drops
    based on the verdict field. Configurable partial handling and
    predicate error behavior.
    """

    is_combinator = True

    def __init__(
        self,
        predicate_op: OperatorProtocol,
        keep_partial: bool = True,
        fail_on_predicate_error: bool = False,
    ) -> None:
        self._predicate_op = predicate_op
        self._keep_partial = keep_partial
        self._fail_on_predicate_error = fail_on_predicate_error

    @property
    def name(self) -> str:
        return "filter"

    def run(self, input: Any, ctx: Context) -> RunResult:
        if not isinstance(input, list):
            raise TypeError(f"filter_op expects a list input, got {type(input).__name__}")

        step_index = len(ctx.trace)
        start_entry = emit_combinator_start("filter", step_index)
        all_trace: list[TraceEntry] = [start_entry]
        all_errors: list[ItemError] = []
        kept: list[Artifact] = []

        for i, item in enumerate(input):
            item_id = str(getattr(item, "id", f"item_{i}"))

            result = execute_node(self._predicate_op, item, ctx)
            all_trace.extend(result.trace)

            # Budget exhausted: halt remaining items
            if result.status == RunResultStatus.BUDGET_EXHAUSTED:
                if result.errors:
                    all_errors.extend(result.errors)
                end_entry = emit_combinator_end(
                    "filter", step_index, ArtifactStatus.FAILED
                )
                all_trace.append(end_entry)
                return RunResult(
                    output=kept,
                    trace=all_trace,
                    status=RunResultStatus.BUDGET_EXHAUSTED,
                    errors=all_errors or None,
                )

            # Predicate error (FAILED status = LLM/API/schema failure)
            if result.status == RunResultStatus.FAILED:
                if self._fail_on_predicate_error:
                    all_errors.append(
                        ItemError(
                            item_id=item_id,
                            error_kind="predicate_error",
                            message=f"Predicate failed on item {i}, halting filter",
                        )
                    )
                    end_entry = emit_combinator_end(
                        "filter", step_index, ArtifactStatus.FAILED
                    )
                    all_trace.append(end_entry)
                    return RunResult(
                        output=kept,
                        trace=all_trace,
                        status=RunResultStatus.FAILED,
                        errors=all_errors or None,
                    )
                # Default: drop item silently, record error
                all_errors.append(
                    ItemError(
                        item_id=item_id,
                        error_kind="predicate_error",
                        message=f"Predicate failed on item {i}, item dropped",
                    )
                )
                continue

            # Extract verdict from predicate output
            verdict = _extract_verdict(result.output)
            if verdict is None:
                # No verdict field -- treat as predicate error
                all_errors.append(
                    ItemError(
                        item_id=item_id,
                        error_kind="missing_verdict",
                        message=f"Predicate output for item {i} has no 'verdict' field",
                    )
                )
                continue

            # Apply verdict mapping (spec section 7)
            if verdict == "pass":
                kept.append(item if isinstance(item, Artifact) else _wrap_item(item, i))
            elif verdict == "partial":
                if self._keep_partial:
                    kept.append(item if isinstance(item, Artifact) else _wrap_item(item, i))
                else:
                    all_errors.append(
                        ItemError(
                            item_id=item_id,
                            error_kind="verdict_drop",
                            message=f"Item {i} dropped: verdict=partial, keep_partial=False",
                        )
                    )
            elif verdict == "fail":
                all_errors.append(
                    ItemError(
                        item_id=item_id,
                        error_kind="verdict_drop",
                        message=f"Item {i} dropped: verdict=fail",
                    )
                )

        # Determine aggregate status
        total_input = len(input)
        if len(kept) == total_input:
            artifact_status = ArtifactStatus.SUCCESS
            aggregate = RunResultStatus.SUCCESS
        elif len(kept) > 0:
            artifact_status = ArtifactStatus.PARTIAL
            aggregate = RunResultStatus.PARTIAL
        else:
            # All dropped is still SUCCESS for filter -- it did its job
            artifact_status = ArtifactStatus.SUCCESS
            aggregate = RunResultStatus.SUCCESS

        end_entry = emit_combinator_end("filter", step_index, artifact_status)
        all_trace.append(end_entry)

        return RunResult(
            output=kept,
            trace=all_trace,
            status=aggregate,
            errors=all_errors or None,
        )


def _wrap_item(item: Any, index: int) -> Artifact:
    """Wrap a non-Artifact item for output consistency."""
    return Artifact(
        id=f"filter_kept_{index}",
        operator="filter",
        step_index=index,
        data={"value": item} if not isinstance(item, dict) else item,
        status=ArtifactStatus.SUCCESS,
    )


def filter_op(
    predicate_op: OperatorProtocol,
    keep_partial: bool = True,
    fail_on_predicate_error: bool = False,
) -> FilterOperator:
    """Create a verdict-based filter combinator.

    The predicate operator evaluates each item. Verdict mapping:
      pass    -> keep
      partial -> keep if keep_partial=True (default), drop otherwise
      fail    -> drop

    Each item costs an LLM call via the predicate.
    """
    return FilterOperator(predicate_op, keep_partial, fail_on_predicate_error)
