"""Tests for pipe combinator: sequential composition with short-circuit."""

from __future__ import annotations

from typing import Any

import pytest

from dillylang.combinators.pipe import pipe
from dillylang.vocab.types import (
    Artifact,
    ArtifactStatus,
    Budget,
    Context,
    RunResult,
    RunResultStatus,
    TraceEntry,
    TraceEventType,
)


# --- Mock operators ---


class MockOperator:
    """Configurable mock implementing OperatorProtocol."""

    def __init__(
        self,
        name: str,
        status: RunResultStatus = RunResultStatus.SUCCESS,
        output_data: dict[str, Any] | None = None,
        trace_entries: list[TraceEntry] | None = None,
    ) -> None:
        self._name = name
        self._status = status
        self._output_data = output_data or {"result": f"{name}_output"}
        self._trace_entries = trace_entries or []
        self.call_count = 0
        self.last_input: Any = None

    @property
    def name(self) -> str:
        return self._name

    def run(self, input: Any, ctx: Context) -> RunResult:
        self.call_count += 1
        self.last_input = input
        return RunResult(
            output=Artifact(
                id=f"{self._name}_0",
                operator=self._name,
                step_index=0,
                data=self._output_data,
                status=ArtifactStatus.SUCCESS,
            ),
            trace=list(self._trace_entries),
            status=self._status,
        )


class MockCombinator:
    """Mock that has is_combinator=True for nesting tests."""

    is_combinator = True

    def __init__(self, name: str, output_data: dict[str, Any] | None = None) -> None:
        self._name = name
        self._output_data = output_data or {"result": f"{name}_output"}
        self.call_count = 0
        self.last_input: Any = None

    @property
    def name(self) -> str:
        return self._name

    def run(self, input: Any, ctx: Context) -> RunResult:
        self.call_count += 1
        self.last_input = input
        return RunResult(
            output=Artifact(
                id=f"{self._name}_0",
                operator=self._name,
                step_index=0,
                data=self._output_data,
                status=ArtifactStatus.SUCCESS,
            ),
            trace=[],
            status=RunResultStatus.SUCCESS,
        )


def _make_ctx() -> Context:
    """Create a fresh context with generous budget for testing."""
    return Context(
        problem="test problem",
        budget=Budget(max_llm_calls=100, max_tokens=100_000, max_wall_time_ms=600_000),
    )


# --- Tests ---


def test_pipe_sequential():
    """pipe(op_a, op_b) calls op_a then op_b, final output is op_b's output."""
    op_a = MockOperator("op_a")
    op_b = MockOperator("op_b")
    ctx = _make_ctx()

    result = pipe(op_a, op_b).run("initial input", ctx)

    assert result.status == RunResultStatus.SUCCESS
    assert op_a.call_count == 1
    assert op_b.call_count == 1
    assert isinstance(result.output, Artifact)
    assert result.output.operator == "op_b"


def test_pipe_passes_output_as_input():
    """op_b receives op_a's output artifact as its input."""
    op_a = MockOperator("op_a", output_data={"step": "first"})
    op_b = MockOperator("op_b")
    ctx = _make_ctx()

    pipe(op_a, op_b).run("start", ctx)

    # op_b should receive op_a's Artifact as input
    assert isinstance(op_b.last_input, Artifact)
    assert op_b.last_input.data == {"step": "first"}


def test_pipe_short_circuits_on_failure():
    """op_a returns FAILED, op_b.run() is never called."""
    op_a = MockOperator("op_a", status=RunResultStatus.FAILED)
    op_b = MockOperator("op_b")
    ctx = _make_ctx()

    result = pipe(op_a, op_b).run("input", ctx)

    assert result.status == RunResultStatus.FAILED
    assert op_a.call_count == 1
    assert op_b.call_count == 0  # short-circuited


def test_pipe_short_circuits_on_budget_exhausted():
    """Similar to failure short-circuit but for BUDGET_EXHAUSTED."""
    op_a = MockOperator("op_a", status=RunResultStatus.BUDGET_EXHAUSTED)
    op_b = MockOperator("op_b")
    ctx = _make_ctx()

    result = pipe(op_a, op_b).run("input", ctx)

    assert result.status == RunResultStatus.BUDGET_EXHAUSTED
    assert op_b.call_count == 0


def test_pipe_accumulates_trace():
    """result.trace contains entries from both operators plus combinator entries."""
    from dillylang.trace.emit import emit_llm_call

    trace_a = emit_llm_call("op_a", 0, ArtifactStatus.SUCCESS)
    trace_b = emit_llm_call("op_b", 1, ArtifactStatus.SUCCESS)
    op_a = MockOperator("op_a", trace_entries=[trace_a])
    op_b = MockOperator("op_b", trace_entries=[trace_b])
    ctx = _make_ctx()

    result = pipe(op_a, op_b).run("input", ctx)

    # Should have: combinator_start, op_a trace, op_b trace, combinator_end
    assert len(result.trace) == 4
    assert result.trace[0].event_type == TraceEventType.COMBINATOR_START
    assert result.trace[1].operator_name == "op_a"
    assert result.trace[2].operator_name == "op_b"
    assert result.trace[3].event_type == TraceEventType.COMBINATOR_END


def test_pipe_emits_combinator_trace():
    """Trace contains combinator_start and combinator_end entries."""
    op_a = MockOperator("op_a")
    ctx = _make_ctx()

    result = pipe(op_a).run("input", ctx)

    combinator_events = [
        e
        for e in result.trace
        if e.event_type in (TraceEventType.COMBINATOR_START, TraceEventType.COMBINATOR_END)
    ]
    assert len(combinator_events) == 2
    assert combinator_events[0].event_type == TraceEventType.COMBINATOR_START
    assert combinator_events[0].operator_name == "pipe"
    assert combinator_events[1].event_type == TraceEventType.COMBINATOR_END
    assert combinator_events[1].operator_name == "pipe"


def test_pipe_preserves_partial_status():
    """pipe(op_a, op_b) where op_a returns PARTIAL and op_b returns SUCCESS -> PARTIAL."""
    op_a = MockOperator("op_a", status=RunResultStatus.PARTIAL)
    op_b = MockOperator("op_b", status=RunResultStatus.SUCCESS)
    ctx = _make_ctx()

    result = pipe(op_a, op_b).run("input", ctx)

    # Worst status is preserved: PARTIAL from op_a, not overwritten by op_b's SUCCESS
    assert result.status == RunResultStatus.PARTIAL


def test_pipe_routes_nested_combinator():
    """pipe(op_a, inner_combinator) routes via .run() directly, not run_operator_with_retry."""
    op_a = MockOperator("op_a")
    inner = MockCombinator("inner_parallel", output_data={"inner": "result"})
    ctx = _make_ctx()

    result = pipe(op_a, inner).run("input", ctx)

    assert result.status == RunResultStatus.SUCCESS
    assert inner.call_count == 1
    # Inner combinator received op_a's output
    assert isinstance(inner.last_input, Artifact)
    assert inner.last_input.data == {"result": "op_a_output"}


def test_pipe_empty_raises():
    """pipe() with no operators raises ValueError."""
    with pytest.raises(ValueError, match="at least one operator"):
        pipe()
