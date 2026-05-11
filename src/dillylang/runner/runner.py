"""PipelineRunner: orchestrates operator execution with budget/trace/retry.

The runner is the sole owner of trace emission. Operators return raw Artifact
with empty trace and populate call_metadata for the runner to build
TraceEntry from. The runner checks budget before each call, deducts after,
and applies repair-once retry on parse/validation failures.

Budget accumulates across pipeline steps via ctx.budget reassignment.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from pydantic import ValidationError

from dillylang.runner.budget import check_budget, deduct_budget
from dillylang.trace.emit import emit_llm_call
from dillylang.vocab.types import (
    Artifact,
    ArtifactStatus,
    Budget,
    Context,
    ItemError,
    RunResult,
    RunResultStatus,
)

logger = logging.getLogger(__name__)

# DSPy's parse error -- imported lazily to keep the module importable
# even without DSPy installed (tests mock operators).
_AdapterParseError: type[Exception] | None = None


def _get_adapter_parse_error() -> type[Exception]:
    """Lazy import of AdapterParseError to avoid hard DSPy dependency at import time."""
    global _AdapterParseError  # noqa: PLW0603
    if _AdapterParseError is None:
        from dspy.utils.exceptions import AdapterParseError
        _AdapterParseError = AdapterParseError
    return _AdapterParseError


def run_operator_with_retry(
    operator: Any,
    input: Any,
    ctx: Context,
) -> RunResult:
    """Execute a leaf operator with budget checking, trace emission, and repair-once retry.

    Wraps LEAF operators only (LLM-bearing). Combinators call this for their
    children; PipelineRunner.run() does NOT call this on combinators.

    Budget is checked before execution. On parse/validation failure, exactly
    one repair retry is attempted (if budget allows). Budget is deducted after
    EVERY attempt, including failed ones.

    Args:
        operator: An OperatorProtocol implementation (leaf operator).
        input: The upstream value (problem text or Artifact).
        ctx: Execution context -- ctx.budget is reassigned to accumulate costs.

    Returns:
        RunResult with output, trace, status, and budget state.
    """
    # Pre-check: budget allows another call?
    if not check_budget(ctx.budget):
        return RunResult(
            output=Artifact(
                id=f"{operator.name}_budget_exhausted",
                operator=operator.name,
                step_index=len(ctx.trace),
                data={},
                status=ArtifactStatus.FAILED,
            ),
            trace=[],
            status=RunResultStatus.BUDGET_EXHAUSTED,
            errors=[
                ItemError(
                    item_id=f"{operator.name}_budget",
                    error_kind="budget_exhausted",
                    message="Budget exhausted before operator execution",
                )
            ],
        )

    trace_entries = []
    step_index = len(ctx.trace)
    AdapterParseError = _get_adapter_parse_error()

    # --- Attempt 1 ---
    start_ms = _now_ms()
    try:
        result = operator.run(input, ctx)
    except (AdapterParseError, ValidationError) as first_error:
        # Parse/validation failure on first attempt
        elapsed = _now_ms() - start_ms
        tokens_used = 0

        # Deduct budget for the failed attempt
        ctx.budget = deduct_budget(ctx.budget, tokens=tokens_used, elapsed_ms=elapsed)

        # Record the failed attempt in trace
        trace_entries.append(
            emit_llm_call(
                operator_name=operator.name,
                step_index=step_index,
                status=ArtifactStatus.FAILED,
                input_data=input,
                latency_ms=elapsed,
            )
        )

        # Check budget before repair retry
        if not check_budget(ctx.budget):
            return RunResult(
                output=Artifact(
                    id=f"{operator.name}_budget_exhausted",
                    operator=operator.name,
                    step_index=step_index,
                    data={},
                    status=ArtifactStatus.FAILED,
                ),
                trace=trace_entries,
                status=RunResultStatus.BUDGET_EXHAUSTED,
                errors=[
                    ItemError(
                        item_id=f"{operator.name}_retry_budget",
                        error_kind="budget_exhausted",
                        message=(
                            "Repair retry skipped: budget exhausted after failed first attempt. "
                            f"Original error: {first_error}"
                        ),
                    )
                ],
            )

        # --- Attempt 2 (repair retry) ---
        return _attempt_repair(
            operator, input, ctx, first_error, step_index, trace_entries
        )
    except Exception as exc:
        # Non-parse failures (LLM errors, network errors)
        elapsed = _now_ms() - start_ms
        ctx.budget = deduct_budget(ctx.budget, tokens=0, elapsed_ms=elapsed)

        trace_entries.append(
            emit_llm_call(
                operator_name=operator.name,
                step_index=step_index,
                status=ArtifactStatus.FAILED,
                input_data=input,
                latency_ms=elapsed,
            )
        )

        return RunResult(
            output=Artifact(
                id=f"{operator.name}_error",
                operator=operator.name,
                step_index=step_index,
                data={},
                status=ArtifactStatus.FAILED,
                errors=[
                    ItemError(
                        item_id=f"{operator.name}_exc",
                        error_kind="runtime_error",
                        message=str(exc),
                    )
                ],
            ),
            trace=trace_entries,
            status=RunResultStatus.FAILED,
            errors=[
                ItemError(
                    item_id=f"{operator.name}_exc",
                    error_kind="runtime_error",
                    message=str(exc),
                )
            ],
        )

    # --- Attempt 1 succeeded ---
    meta = result.call_metadata or {}
    tokens_used = meta.get("tokens_used") or 0
    latency_ms = meta.get("latency_ms") or int(_now_ms() - start_ms)

    ctx.budget = deduct_budget(ctx.budget, tokens=tokens_used, elapsed_ms=latency_ms)

    # Store successful artifact in context for downstream resolution
    if isinstance(result.output, Artifact):
        ctx.artifacts[result.output.id] = result.output

    trace_entries.append(
        emit_llm_call(
            operator_name=operator.name,
            step_index=step_index,
            status=result.output.status if isinstance(result.output, Artifact) else ArtifactStatus.SUCCESS,
            input_data=input,
            rendered_prompt=meta.get("rendered_prompt"),
            raw_response=meta.get("raw_response"),
            parsed_output=result.output.data if isinstance(result.output, Artifact) else None,
            tokens_used=tokens_used or None,
            latency_ms=latency_ms,
        )
    )

    return RunResult(
        output=result.output,
        trace=trace_entries,
        status=result.status,
        call_metadata=result.call_metadata,
    )


def _attempt_repair(
    operator: Any,
    input: Any,
    ctx: Context,
    first_error: Exception,
    step_index: int,
    trace_entries: list,
) -> RunResult:
    """Attempt repair retry: call run_repair if available, else fall back to run."""
    AdapterParseError = _get_adapter_parse_error()
    start_ms = _now_ms()

    try:
        if hasattr(operator, "run_repair"):
            result = operator.run_repair(input, ctx, error=str(first_error))
        else:
            result = operator.run(input, ctx)
    except (AdapterParseError, ValidationError) as second_error:
        # Second failure -- fail loud
        elapsed = _now_ms() - start_ms
        ctx.budget = deduct_budget(ctx.budget, tokens=0, elapsed_ms=elapsed)

        trace_entries.append(
            emit_llm_call(
                operator_name=operator.name,
                step_index=step_index,
                status=ArtifactStatus.FAILED,
                input_data=input,
                latency_ms=elapsed,
            )
        )

        return RunResult(
            output=Artifact(
                id=f"{operator.name}_repair_failed",
                operator=operator.name,
                step_index=step_index,
                data={},
                status=ArtifactStatus.FAILED,
                errors=[
                    ItemError(
                        item_id=f"{operator.name}_parse",
                        error_kind="parse_failure",
                        message=str(second_error),
                    )
                ],
            ),
            trace=trace_entries,
            status=RunResultStatus.FAILED,
            errors=[
                ItemError(
                    item_id=f"{operator.name}_parse",
                    error_kind="parse_failure",
                    message=str(second_error),
                )
            ],
        )
    except Exception as exc:
        # Non-parse error on repair attempt
        elapsed = _now_ms() - start_ms
        ctx.budget = deduct_budget(ctx.budget, tokens=0, elapsed_ms=elapsed)

        trace_entries.append(
            emit_llm_call(
                operator_name=operator.name,
                step_index=step_index,
                status=ArtifactStatus.FAILED,
                input_data=input,
                latency_ms=elapsed,
            )
        )

        return RunResult(
            output=Artifact(
                id=f"{operator.name}_repair_error",
                operator=operator.name,
                step_index=step_index,
                data={},
                status=ArtifactStatus.FAILED,
                errors=[
                    ItemError(
                        item_id=f"{operator.name}_repair_exc",
                        error_kind="runtime_error",
                        message=str(exc),
                    )
                ],
            ),
            trace=trace_entries,
            status=RunResultStatus.FAILED,
            errors=[
                ItemError(
                    item_id=f"{operator.name}_repair_exc",
                    error_kind="runtime_error",
                    message=str(exc),
                )
            ],
        )

    # Repair succeeded
    meta = result.call_metadata or {}
    tokens_used = meta.get("tokens_used") or 0
    latency_ms = meta.get("latency_ms") or int(_now_ms() - start_ms)

    ctx.budget = deduct_budget(ctx.budget, tokens=tokens_used, elapsed_ms=latency_ms)

    # Store repaired artifact in context
    if isinstance(result.output, Artifact):
        ctx.artifacts[result.output.id] = result.output

    # Trace entry for successful repair attempt
    trace_entries.append(
        emit_llm_call(
            operator_name=operator.name,
            step_index=step_index,
            status=ArtifactStatus.REPAIR_SUCCEEDED,
            input_data=input,
            rendered_prompt=meta.get("rendered_prompt"),
            raw_response=meta.get("raw_response"),
            parsed_output=result.output.data if isinstance(result.output, Artifact) else None,
            tokens_used=tokens_used or None,
            latency_ms=latency_ms,
        )
    )

    return RunResult(
        output=result.output,
        trace=trace_entries,
        status=result.status,
        call_metadata=result.call_metadata,
    )


def _now_ms() -> int:
    """Current monotonic time in milliseconds."""
    return int(time.monotonic() * 1000)


class PipelineRunner:
    """Orchestrates pipeline execution with budget, trace, and retry.

    Routes combinators via .run() directly (they manage their own children).
    Routes leaf operators via run_operator_with_retry for budget/trace/retry.
    """

    def __init__(self, budget: Budget | None = None) -> None:
        self._budget = budget or Budget()

    def run(self, pipeline: Any, problem: str | Artifact) -> RunResult:
        """Execute a pipeline or single operator against a problem.

        Args:
            pipeline: An OperatorProtocol or combinator node.
            problem: The problem statement string, or an Artifact for
                meta-skill pipelines that receive structured input.

        Returns:
            RunResult with complete trace, budget snapshot, and artifacts.
        """
        ctx = Context(problem=problem, budget=self._budget)

        # Route by operator type: combinator vs leaf
        if getattr(pipeline, "is_combinator", False):
            # Combinators manage their own children; call .run() directly
            result = pipeline.run(problem, ctx)
        else:
            # Leaf operator: wrap with budget/trace/retry
            result = run_operator_with_retry(pipeline, problem, ctx)

        # Snapshot final budget state and collected artifacts into result
        result.budget = ctx.budget
        result.artifacts = dict(ctx.artifacts)
        return result
