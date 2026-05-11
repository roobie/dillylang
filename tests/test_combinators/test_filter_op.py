"""Tests for filter combinator: verdict-based item filtering."""

from __future__ import annotations

from typing import Any

from dillylang.combinators.filter_op import filter_op
from dillylang.vocab.types import (
    Artifact,
    ArtifactStatus,
    Budget,
    Context,
    RunResult,
    RunResultStatus,
)


class MockPredicate:
    """Mock predicate operator that returns configurable verdicts per item."""

    def __init__(self, verdicts: dict[str, str]) -> None:
        """verdicts: mapping of item_id -> 'pass'|'partial'|'fail'."""
        self._name = "mock_predicate"
        self._verdicts = verdicts
        self.call_count = 0

    @property
    def name(self) -> str:
        return self._name

    def run(self, input: Any, ctx: Context) -> RunResult:
        self.call_count += 1
        item_id = getattr(input, "id", str(input))
        verdict = self._verdicts.get(item_id, "pass")
        return RunResult(
            output=Artifact(
                id=f"eval_{item_id}",
                operator=self._name,
                step_index=0,
                data={"verdict": verdict},
                status=ArtifactStatus.SUCCESS,
            ),
            trace=[],
            status=RunResultStatus.SUCCESS,
        )


class MockFailingPredicate:
    """Mock predicate that fails on specific items."""

    def __init__(self, fail_on: set[str]) -> None:
        self._name = "failing_predicate"
        self._fail_on = fail_on

    @property
    def name(self) -> str:
        return self._name

    def run(self, input: Any, ctx: Context) -> RunResult:
        item_id = getattr(input, "id", str(input))
        if item_id in self._fail_on:
            return RunResult(
                output=Artifact(
                    id=f"fail_{item_id}", operator=self._name, step_index=0,
                    data={}, status=ArtifactStatus.FAILED,
                ),
                trace=[],
                status=RunResultStatus.FAILED,
            )
        return RunResult(
            output=Artifact(
                id=f"eval_{item_id}", operator=self._name, step_index=0,
                data={"verdict": "pass"}, status=ArtifactStatus.SUCCESS,
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


def test_filter_keeps_pass_items():
    """Items with 'pass' verdict are kept."""
    verdicts = {"item_0": "pass", "item_1": "pass", "item_2": "pass"}
    pred = MockPredicate(verdicts)
    items = _make_items(3)
    ctx = _make_ctx()

    result = filter_op(pred).run(items, ctx)

    assert isinstance(result.output, list)
    assert len(result.output) == 3


def test_filter_keeps_partial_by_default():
    """Items with 'partial' verdict are kept when keep_partial=True (default)."""
    verdicts = {"item_0": "pass", "item_1": "partial", "item_2": "pass"}
    pred = MockPredicate(verdicts)
    items = _make_items(3)
    ctx = _make_ctx()

    result = filter_op(pred).run(items, ctx)

    assert isinstance(result.output, list)
    assert len(result.output) == 3  # partial kept


def test_filter_drops_partial_when_configured():
    """filter_op(pred, keep_partial=False) drops 'partial' items."""
    verdicts = {"item_0": "pass", "item_1": "partial", "item_2": "pass"}
    pred = MockPredicate(verdicts)
    items = _make_items(3)
    ctx = _make_ctx()

    result = filter_op(pred, keep_partial=False).run(items, ctx)

    assert isinstance(result.output, list)
    assert len(result.output) == 2  # partial dropped
    kept_ids = [a.id for a in result.output]
    assert "item_1" not in kept_ids


def test_filter_drops_fail_items():
    """Items with 'fail' verdict are dropped."""
    verdicts = {"item_0": "pass", "item_1": "fail", "item_2": "pass"}
    pred = MockPredicate(verdicts)
    items = _make_items(3)
    ctx = _make_ctx()

    result = filter_op(pred).run(items, ctx)

    assert isinstance(result.output, list)
    assert len(result.output) == 2
    kept_ids = [a.id for a in result.output]
    assert "item_1" not in kept_ids


def test_filter_handles_predicate_error_silently():
    """Predicate fails on an item -> item dropped, no halt (default behavior)."""
    pred = MockFailingPredicate(fail_on={"item_1"})
    items = _make_items(3)
    ctx = _make_ctx()

    result = filter_op(pred).run(items, ctx)

    # item_1 dropped due to predicate error, other items kept
    assert isinstance(result.output, list)
    assert len(result.output) == 2
    # Error recorded
    assert result.errors is not None
    error_ids = [e.item_id for e in result.errors]
    assert "item_1" in error_ids
    assert any(e.error_kind == "predicate_error" for e in result.errors)


def test_filter_halts_on_predicate_error_when_configured():
    """fail_on_predicate_error=True: predicate error halts combinator."""
    pred = MockFailingPredicate(fail_on={"item_1"})
    items = _make_items(3)
    ctx = _make_ctx()

    result = filter_op(pred, fail_on_predicate_error=True).run(items, ctx)

    assert result.status == RunResultStatus.FAILED
    assert isinstance(result.output, list)
    # Only item_0 was kept before the halt on item_1
    assert len(result.output) == 1


def test_filter_records_drop_reasons():
    """Errors list contains why each item was dropped."""
    verdicts = {"item_0": "pass", "item_1": "fail", "item_2": "partial"}
    pred = MockPredicate(verdicts)
    items = _make_items(3)
    ctx = _make_ctx()

    # keep_partial=False so partial is also dropped
    result = filter_op(pred, keep_partial=False).run(items, ctx)

    assert result.errors is not None
    assert len(result.errors) == 2  # item_1 (fail) and item_2 (partial)
    reasons = {e.item_id: e.error_kind for e in result.errors}
    assert reasons["item_1"] == "verdict_drop"
    assert reasons["item_2"] == "verdict_drop"
