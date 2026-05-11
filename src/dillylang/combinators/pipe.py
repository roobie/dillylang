"""Pipe combinator: sequential composition with short-circuit on failure.

pipe(op_a, op_b, op_c) runs op_a -> op_b -> op_c, passing each output
as the next input. Short-circuits on FAILED or BUDGET_EXHAUSTED per
spec section 8. Preserves the worst observed status across steps
(PARTIAL is not overwritten to SUCCESS by a later successful step).
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


class PipeOperator:
    """Sequential composition operator.

    Runs each operator in order, feeding the output of step N as input
    to step N+1. Short-circuits on FAILED or BUDGET_EXHAUSTED.
    Tracks worst observed status (preserves PARTIAL from inner steps).
    """

    is_combinator = True

    def __init__(self, operators: tuple[OperatorProtocol, ...]) -> None:
        self._operators = operators

    @property
    def name(self) -> str:
        return "pipe"

    def run(self, input: Any, ctx: Context) -> RunResult:
        step_index = len(ctx.trace)
        start_entry = emit_combinator_start("pipe", step_index)
        all_trace: list[TraceEntry] = [start_entry]
        all_errors: list[ItemError] = []

        current_input = input
        worst_status = RunResultStatus.SUCCESS
        last_output: Artifact | list[Artifact] | None = None

        for op in self._operators:
            result = execute_node(op, current_input, ctx)
            all_trace.extend(result.trace)
            if result.errors:
                all_errors.extend(result.errors)

            # Short-circuit on hard failure
            if result.status == RunResultStatus.FAILED:
                end_entry = emit_combinator_end(
                    "pipe", step_index, ArtifactStatus.FAILED
                )
                all_trace.append(end_entry)
                return RunResult(
                    output=result.output,
                    trace=all_trace,
                    status=RunResultStatus.FAILED,
                    errors=all_errors or None,
                )

            # Short-circuit on budget exhaustion
            if result.status == RunResultStatus.BUDGET_EXHAUSTED:
                end_entry = emit_combinator_end(
                    "pipe", step_index, ArtifactStatus.FAILED
                )
                all_trace.append(end_entry)
                return RunResult(
                    output=result.output,
                    trace=all_trace,
                    status=RunResultStatus.BUDGET_EXHAUSTED,
                    errors=all_errors or None,
                )

            # Track worst status (PARTIAL is worse than SUCCESS)
            if result.status == RunResultStatus.PARTIAL:
                worst_status = RunResultStatus.PARTIAL

            # Feed output forward
            current_input = result.output
            last_output = result.output

        # Map RunResultStatus -> ArtifactStatus for the end trace entry
        end_artifact_status = (
            ArtifactStatus.PARTIAL
            if worst_status == RunResultStatus.PARTIAL
            else ArtifactStatus.SUCCESS
        )
        end_entry = emit_combinator_end("pipe", step_index, end_artifact_status)
        all_trace.append(end_entry)

        # last_output should always be set (pipe requires >= 1 operator)
        assert last_output is not None, "pipe requires at least one operator"

        return RunResult(
            output=last_output,
            trace=all_trace,
            status=worst_status,
            errors=all_errors or None,
        )


def pipe(*operators: OperatorProtocol) -> PipeOperator:
    """Create a sequential pipeline of operators.

    Each operator's output is fed as input to the next.
    Short-circuits on FAILED or BUDGET_EXHAUSTED.
    """
    if not operators:
        raise ValueError("pipe requires at least one operator")
    return PipeOperator(operators)
