"""Tests for map combinator: collection application with per-item failure tolerance."""

from __future__ import annotations

from typing import Any

from dillylang.combinators.map_op import map_op
from dillylang.vocab.types import (
    Artifact,
    ArtifactStatus,
    Budget,
    Context,
    RunResult,
    RunResultStatus,
)


class MockOperator:
    """Mock operator that succeeds or fails based on item content."""

    def __init__(
        self,
        name: str = "mock_op",
        fail_on: set[str] | None = None,
    ) -> None:
        self._name = name
        self._fail_on = fail_on or set()
        self.call_count = 0
        self.inputs: list[Any] = []

    @property
    def name(self) -> str:
        return self._name

    def run(self, input: Any, ctx: Context) -> RunResult:
        self.call_count += 1
        self.inputs.append(input)

        item_id = getattr(input, "id", str(input))
        if item_id in self._fail_on:
            return RunResult(
                output=Artifact(
                    id=f"{self._name}_failed",
                    operator=self._name,
                    step_index=0,
                    data={},
                    status=ArtifactStatus.FAILED,
                ),
                trace=[],
                status=RunResultStatus.FAILED,
            )

        return RunResult(
            output=Artifact(
                id=f"{self._name}_{item_id}",
                operator=self._name,
                step_index=0,
                data={"processed": item_id},
                status=ArtifactStatus.SUCCESS,
            ),
            trace=[],
            status=RunResultStatus.SUCCESS,
        )


class MockBudgetExhaustedOperator:
    """Mock that returns BUDGET_EXHAUSTED on the Nth call."""

    def __init__(self, exhaust_on_call: int = 2) -> None:
        self._name = "budget_op"
        self._exhaust_on = exhaust_on_call
        self.call_count = 0

    @property
    def name(self) -> str:
        return self._name

    def run(self, input: Any, ctx: Context) -> RunResult:
        self.call_count += 1
        if self.call_count >= self._exhaust_on:
            return RunResult(
                output=Artifact(
                    id="budget_exhausted", operator=self._name, step_index=0,
                    data={}, status=ArtifactStatus.FAILED,
                ),
                trace=[], status=RunResultStatus.BUDGET_EXHAUSTED,
            )
        return RunResult(
            output=Artifact(
                id=f"ok_{self.call_count}", operator=self._name, step_index=0,
                data={"ok": True}, status=ArtifactStatus.SUCCESS,
            ),
            trace=[], status=RunResultStatus.SUCCESS,
        )


def _make_ctx() -> Context:
    return Context(
        problem="test",
        budget=Budget(max_llm_calls=100, max_tokens=100_000, max_wall_time_ms=600_000),
    )


def _make_items(n: int) -> list[Artifact]:
    return [
        Artifact(
            id=f"item_{i}", operator="source", step_index=i,
            data={"value": i}, status=ArtifactStatus.SUCCESS,
        )
        for i in range(n)
    ]


def test_map_applies_to_each_item():
    """map_op(op).run([item1, item2, item3], ctx) calls op for each."""
    op = MockOperator("transform")
    items = _make_items(3)
    ctx = _make_ctx()

    map_op(op).run(items, ctx)

    assert op.call_count == 3
    for i, inp in enumerate(op.inputs):
        assert inp.id == f"item_{i}"


def test_map_collects_outputs():
    """Output is a list of 3 results."""
    op = MockOperator("transform")
    items = _make_items(3)
    ctx = _make_ctx()

    result = map_op(op).run(items, ctx)

    assert result.status == RunResultStatus.SUCCESS
    assert isinstance(result.output, list)
    assert len(result.output) == 3


def test_map_tolerates_item_failure():
    """One item fails, other two succeed, status=PARTIAL, output has 2 items."""
    op = MockOperator("transform", fail_on={"item_1"})
    items = _make_items(3)
    ctx = _make_ctx()

    result = map_op(op).run(items, ctx)

    assert result.status == RunResultStatus.PARTIAL
    assert isinstance(result.output, list)
    assert len(result.output) == 2  # item_0 and item_2


def test_map_failed_when_all_items_fail():
    """All items fail -> status=FAILED."""
    op = MockOperator("transform", fail_on={"item_0", "item_1", "item_2"})
    items = _make_items(3)
    ctx = _make_ctx()

    result = map_op(op).run(items, ctx)

    assert result.status == RunResultStatus.FAILED
    assert isinstance(result.output, list)
    assert len(result.output) == 0


def test_map_records_item_errors():
    """Failed items recorded in errors list with item_id."""
    op = MockOperator("transform", fail_on={"item_1"})
    items = _make_items(3)
    ctx = _make_ctx()

    result = map_op(op).run(items, ctx)

    assert result.errors is not None
    assert len(result.errors) >= 1
    error_ids = [e.item_id for e in result.errors]
    assert "item_1" in error_ids


def test_map_halts_on_budget_exhausted():
    """BUDGET_EXHAUSTED halts remaining items, returns partial output."""
    op = MockBudgetExhaustedOperator(exhaust_on_call=2)
    items = _make_items(4)
    ctx = _make_ctx()

    result = map_op(op).run(items, ctx)

    assert result.status == RunResultStatus.BUDGET_EXHAUSTED
    assert op.call_count == 2  # processed 1 ok, then hit budget on 2nd
    assert isinstance(result.output, list)
    assert len(result.output) == 1  # only the first successful item
