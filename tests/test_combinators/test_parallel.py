"""Tests for parallel combinator: fan-out with partial failure tolerance."""

from __future__ import annotations

from typing import Any

from dillylang.combinators.parallel import parallel
from dillylang.vocab.types import (
    Artifact,
    ArtifactStatus,
    Budget,
    Context,
    RunResult,
    RunResultStatus,
)


class MockOperator:
    """Configurable mock implementing OperatorProtocol."""

    def __init__(
        self,
        name: str,
        status: RunResultStatus = RunResultStatus.SUCCESS,
        output_data: dict[str, Any] | None = None,
    ) -> None:
        self._name = name
        self._status = status
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
            status=self._status,
        )


def _make_ctx() -> Context:
    return Context(
        problem="test problem",
        budget=Budget(max_llm_calls=100, max_tokens=100_000, max_wall_time_ms=600_000),
    )


def test_parallel_fans_out_same_input():
    """parallel(op_a, op_b) both receive the same input."""
    op_a = MockOperator("op_a")
    op_b = MockOperator("op_b")
    ctx = _make_ctx()

    parallel(op_a, op_b).run("shared input", ctx)

    assert op_a.call_count == 1
    assert op_b.call_count == 1
    assert op_a.last_input == "shared input"
    assert op_b.last_input == "shared input"


def test_parallel_collects_results_as_list():
    """Output is a list of Artifacts from all branches."""
    op_a = MockOperator("op_a", output_data={"a": 1})
    op_b = MockOperator("op_b", output_data={"b": 2})
    ctx = _make_ctx()

    result = parallel(op_a, op_b).run("input", ctx)

    assert result.status == RunResultStatus.SUCCESS
    assert isinstance(result.output, list)
    assert len(result.output) == 2
    assert result.output[0].data == {"a": 1}
    assert result.output[1].data == {"b": 2}


def test_parallel_partial_on_branch_failure():
    """One branch fails, status is PARTIAL, other branch output present."""
    op_ok = MockOperator("op_ok")
    op_fail = MockOperator("op_fail", status=RunResultStatus.FAILED)
    ctx = _make_ctx()

    result = parallel(op_ok, op_fail).run("input", ctx)

    assert result.status == RunResultStatus.PARTIAL
    assert isinstance(result.output, list)
    assert len(result.output) == 1  # only successful branch
    assert result.output[0].operator == "op_ok"


def test_parallel_failed_when_all_fail():
    """All branches fail -> status is FAILED."""
    op_a = MockOperator("op_a", status=RunResultStatus.FAILED)
    op_b = MockOperator("op_b", status=RunResultStatus.FAILED)
    ctx = _make_ctx()

    result = parallel(op_a, op_b).run("input", ctx)

    assert result.status == RunResultStatus.FAILED
    assert isinstance(result.output, list)
    assert len(result.output) == 0


def test_parallel_budget_exhausted_halts_remaining():
    """BUDGET_EXHAUSTED halts remaining branches."""
    op_budget = MockOperator("op_budget", status=RunResultStatus.BUDGET_EXHAUSTED)
    op_skipped = MockOperator("op_skipped")
    ctx = _make_ctx()

    result = parallel(op_budget, op_skipped).run("input", ctx)

    assert result.status == RunResultStatus.BUDGET_EXHAUSTED
    assert op_budget.call_count == 1
    assert op_skipped.call_count == 0  # halted
