"""Tests for bind combinator: compile-time typed currying."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, Field

from dillylang.combinators.bind import bind
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


class MockInput(BaseModel):
    """Input model with known fields for validation testing."""

    focus: str | None = Field(default=None)
    depth: int = Field(default=3)


class MockOperator:
    """Mock operator with input_model for bind-time validation."""

    def __init__(self, name: str = "mock_op") -> None:
        self._name = name
        self._input_model = MockInput
        self._bound_params: dict[str, Any] = {}
        self.last_input: Any = None
        self.call_count = 0

    @property
    def name(self) -> str:
        return self._name

    def with_bound_params(self, **params: Any) -> "MockOperator":
        copy = MockOperator(self._name)
        copy._bound_params = {**self._bound_params, **params}
        return copy

    def run(self, input: Any, ctx: Context) -> RunResult:
        self.call_count += 1
        self.last_input = input
        return RunResult(
            output=Artifact(
                id=f"{self._name}_0",
                operator=self._name,
                step_index=0,
                data={"bound": self._bound_params, "input": str(input)},
                status=ArtifactStatus.SUCCESS,
            ),
            trace=[],
            status=RunResultStatus.SUCCESS,
        )


class MockGenericOperator:
    """Mock operator WITHOUT input_model (generic OperatorProtocol)."""

    def __init__(self, name: str = "generic_op") -> None:
        self._name = name
        self.last_input: Any = None

    @property
    def name(self) -> str:
        return self._name

    def run(self, input: Any, ctx: Context) -> RunResult:
        self.last_input = input
        return RunResult(
            output=Artifact(
                id=f"{self._name}_0",
                operator=self._name,
                step_index=0,
                data={"received": str(input)},
                status=ArtifactStatus.SUCCESS,
            ),
            trace=[],
            status=RunResultStatus.SUCCESS,
        )


def _make_ctx() -> Context:
    return Context(
        problem="test problem",
        budget=Budget(max_llm_calls=100, max_tokens=100_000, max_wall_time_ms=600_000),
    )


def test_bind_name_is_underlying():
    """bind(op, focus='X').name == op.name."""
    op = MockOperator("decompose")
    bound = bind(op, focus="cost structure")
    assert bound.name == "decompose"


def test_bind_does_not_emit_trace():
    """bind itself produces no trace entry -- compile-time transform."""
    op = MockOperator("decompose")
    bound = bind(op, focus="X")
    ctx = _make_ctx()

    result = bound.run("input", ctx)

    # No combinator_start/end trace entries from bind
    combinator_events = [
        e for e in result.trace
        if e.event_type in (TraceEventType.COMBINATOR_START, TraceEventType.COMBINATOR_END)
    ]
    assert len(combinator_events) == 0


def test_bind_injects_params():
    """Bound operator receives the pre-filled parameters."""
    op = MockOperator("decompose")
    bound = bind(op, focus="cost structure")
    ctx = _make_ctx()

    result = bound.run("test input", ctx)

    # The mock with_bound_params stores params in _bound_params, visible in output
    assert isinstance(result.output, Artifact)
    assert result.output.data["bound"] == {"focus": "cost structure"}


def test_bind_validates_params_at_bind_time():
    """bind(op, nonexistent_param='X') raises ValueError immediately."""
    op = MockOperator("decompose")

    with pytest.raises(ValueError, match="Unknown parameters"):
        bind(op, nonexistent_param="X")


def test_bind_stores_params_immutably():
    """Modifying the original params dict after bind has no effect."""
    op = MockOperator("decompose")
    params = {"focus": "original"}
    bound = bind(op, **params)

    # Mutate the original dict
    params["focus"] = "mutated"

    ctx = _make_ctx()
    result = bound.run("input", ctx)

    # Bound operator should still use "original"
    assert result.output.data["bound"] == {"focus": "original"}


def test_bind_bound_params_override_input():
    """If both input and bound params provide the same field, bound wins."""
    op = MockOperator("decompose")
    bound = bind(op, focus="bound_value")
    ctx = _make_ctx()

    # The with_bound_params mechanism ensures bound params override
    result = bound.run("input with focus", ctx)
    assert result.output.data["bound"]["focus"] == "bound_value"


def test_bind_empty_raises():
    """bind(op) with no params raises ValueError."""
    op = MockOperator("mock")
    with pytest.raises(ValueError, match="at least one parameter"):
        bind(op)


def test_bind_preserves_is_combinator():
    """BoundOperator.is_combinator matches the wrapped operator's marker."""
    class CombinatorMock:
        is_combinator = True
        _name = "mock_comb"
        _input_model = None

        @property
        def name(self) -> str:
            return self._name

        def run(self, input: Any, ctx: Context) -> RunResult:
            return RunResult(
                output=Artifact(
                    id="c_0", operator="mock_comb", step_index=0,
                    data={}, status=ArtifactStatus.SUCCESS,
                ),
                trace=[], status=RunResultStatus.SUCCESS,
            )

    # Bind on a combinator preserves is_combinator=True
    comb = CombinatorMock()
    bound_comb = bind(comb, focus="X")  # no input_model -> skip validation
    assert bound_comb.is_combinator is True

    # Bind on a regular operator has is_combinator=False
    op = MockOperator("regular")
    bound_op = bind(op, focus="Y")
    assert bound_op.is_combinator is False


def test_bind_generic_operator_without_input_model():
    """bind on an operator without input_model skips validation, enriches input."""
    op = MockGenericOperator("generic")
    bound = bind(op, custom_param="value")
    ctx = _make_ctx()

    result = bound.run({"data": "test"}, ctx)

    # Generic path: merges params into dict input
    assert op.last_input == {"data": "test", "custom_param": "value"}
