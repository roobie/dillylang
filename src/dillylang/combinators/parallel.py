"""Parallel combinator: fan-out with partial failure tolerance.

parallel(op_a, op_b, op_c) runs all operators on the same input and
collects results as a list. Per spec section 8: partial failure doesn't
halt -- successful branch outputs are still included.

v0: sequential execution. Concurrent execution is an optimization for later.
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


class ParallelOperator:
    """Fan-out composition operator.

    Runs all operators on the same input. Collects successful outputs
    as a list. Tolerates individual branch failures (returns PARTIAL).
    Halts remaining branches on BUDGET_EXHAUSTED.

    v0 limitation: branches run sequentially. Wall time accumulates.
    """

    is_combinator = True

    def __init__(self, operators: tuple[OperatorProtocol, ...]) -> None:
        self._operators = operators

    @property
    def name(self) -> str:
        return "parallel"

    def run(self, input: Any, ctx: Context) -> RunResult:
        step_index = len(ctx.trace)
        start_entry = emit_combinator_start(
            "parallel", step_index,
            children_ids=[getattr(op, "name", str(op)) for op in self._operators],
        )
        all_trace: list[TraceEntry] = [start_entry]
        all_errors: list[ItemError] = []
        outputs: list[Artifact] = []
        successes = 0
        failures = 0

        for op in self._operators:
            result = execute_node(op, input, ctx)
            all_trace.extend(result.trace)
            if result.errors:
                all_errors.extend(result.errors)

            # Budget exhausted: halt remaining branches immediately
            if result.status == RunResultStatus.BUDGET_EXHAUSTED:
                end_entry = emit_combinator_end(
                    "parallel", step_index, ArtifactStatus.FAILED
                )
                all_trace.append(end_entry)
                return RunResult(
                    output=outputs,  # partial results collected so far
                    trace=all_trace,
                    status=RunResultStatus.BUDGET_EXHAUSTED,
                    errors=all_errors or None,
                )

            # Collect successful outputs
            if result.status in (RunResultStatus.SUCCESS, RunResultStatus.PARTIAL):
                successes += 1
                if isinstance(result.output, list):
                    outputs.extend(result.output)
                else:
                    outputs.append(result.output)
            else:
                failures += 1

        # Determine aggregate status
        if successes == 0:
            aggregate = RunResultStatus.FAILED
            artifact_status = ArtifactStatus.FAILED
        elif failures > 0:
            aggregate = RunResultStatus.PARTIAL
            artifact_status = ArtifactStatus.PARTIAL
        else:
            aggregate = RunResultStatus.SUCCESS
            artifact_status = ArtifactStatus.SUCCESS

        end_entry = emit_combinator_end("parallel", step_index, artifact_status)
        all_trace.append(end_entry)

        return RunResult(
            output=outputs,
            trace=all_trace,
            status=aggregate,
            errors=all_errors or None,
        )


def parallel(*operators: OperatorProtocol) -> ParallelOperator:
    """Create a fan-out composition of operators.

    All operators receive the same input. Outputs collected as a list.
    Partial failures don't halt: successful branch outputs still included.
    """
    if not operators:
        raise ValueError("parallel requires at least one operator")
    return ParallelOperator(operators)
