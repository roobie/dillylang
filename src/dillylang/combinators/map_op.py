"""Map combinator: apply an operator to each item in a collection.

map_op(operator) returns a combinator that runs the operator on each
item in the input list. Per spec section 8: individual element failures
don't halt the map -- failed elements are omitted from the output
collection and recorded in errors.

v0: sequential execution. Concurrent optimization is future work.
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


class MapOperator:
    """Collection application operator.

    Applies an operator to each item in the input list. Tolerates
    per-item failure: failed items are omitted from output and
    recorded in errors. Halts on BUDGET_EXHAUSTED.

    v0 limitation: items processed sequentially.
    """

    is_combinator = True

    def __init__(self, operator: OperatorProtocol) -> None:
        self._operator = operator

    @property
    def name(self) -> str:
        return "map"

    def run(self, input: Any, ctx: Context) -> RunResult:
        if not isinstance(input, list):
            raise TypeError(f"map_op expects a list input, got {type(input).__name__}")

        step_index = len(ctx.trace)
        start_entry = emit_combinator_start("map", step_index)
        all_trace: list[TraceEntry] = [start_entry]
        all_errors: list[ItemError] = []
        outputs: list[Artifact] = []
        successes = 0
        failures = 0

        for i, item in enumerate(input):
            result = execute_node(self._operator, item, ctx)
            all_trace.extend(result.trace)

            # Budget exhausted: halt remaining items
            if result.status == RunResultStatus.BUDGET_EXHAUSTED:
                if result.errors:
                    all_errors.extend(result.errors)
                end_entry = emit_combinator_end(
                    "map", step_index, ArtifactStatus.FAILED
                )
                all_trace.append(end_entry)
                return RunResult(
                    output=outputs,  # partial results so far
                    trace=all_trace,
                    status=RunResultStatus.BUDGET_EXHAUSTED,
                    errors=all_errors or None,
                )

            if result.status in (RunResultStatus.SUCCESS, RunResultStatus.PARTIAL):
                successes += 1
                if isinstance(result.output, list):
                    outputs.extend(result.output)
                else:
                    outputs.append(result.output)
            else:
                # Item failed -- record error, continue to next
                failures += 1
                item_id = getattr(item, "id", f"item_{i}")
                all_errors.append(
                    ItemError(
                        item_id=str(item_id),
                        error_kind="item_failure",
                        message=f"Operator {self._operator.name} failed on item {i}",
                    )
                )
                if result.errors:
                    all_errors.extend(result.errors)

        # Aggregate status
        if successes == 0 and failures > 0:
            aggregate = RunResultStatus.FAILED
            artifact_status = ArtifactStatus.FAILED
        elif failures > 0:
            aggregate = RunResultStatus.PARTIAL
            artifact_status = ArtifactStatus.PARTIAL
        else:
            aggregate = RunResultStatus.SUCCESS
            artifact_status = ArtifactStatus.SUCCESS

        end_entry = emit_combinator_end("map", step_index, artifact_status)
        all_trace.append(end_entry)

        return RunResult(
            output=outputs,
            trace=all_trace,
            status=aggregate,
            errors=all_errors or None,
        )


def map_op(operator: OperatorProtocol) -> MapOperator:
    """Create a map combinator that applies operator to each item in a list.

    Per-item failures are tolerated: failed items omitted from output,
    recorded in errors. Budget exhaustion halts remaining items.
    """
    return MapOperator(operator)
