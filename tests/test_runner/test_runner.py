"""Tests for PipelineRunner and run_operator_with_retry.

All tests are mock-based -- no LLM access required. Mock operators implement
OperatorProtocol and return configurable results with trace=[] (per the
operator contract that the runner owns trace emission).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import dspy
from dspy.utils.exceptions import AdapterParseError

from dillylang.runner.runner import PipelineRunner, run_operator_with_retry
from dillylang.vocab.types import (
    Artifact,
    ArtifactStatus,
    Budget,
    Context,
    RunResult,
    RunResultStatus,
    TraceEventType,
)


def _make_parse_error(msg: str = "bad output format") -> AdapterParseError:
    """Create an AdapterParseError with a minimal mock signature."""
    # AdapterParseError needs adapter_name, a Signature, and lm_response
    minimal_sig = type("MinimalSig", (dspy.Signature,), {
        "__annotations__": {"output": str},
        "output": dspy.OutputField(desc="test"),
    })
    return AdapterParseError(
        adapter_name="test_adapter",
        signature=minimal_sig,
        lm_response=msg,
    )


# --- Mock operators ---


class MockOperator:
    """Succeeding operator that returns a configurable artifact."""

    def __init__(self, name: str = "mock_op") -> None:
        self._name = name
        self.call_count = 0

    @property
    def name(self) -> str:
        return self._name

    def run(self, input: Any, ctx: Context) -> RunResult:
        self.call_count += 1
        artifact = Artifact(
            id=f"{self._name}_{ctx.budget.llm_calls_used}",
            operator=self._name,
            step_index=len(ctx.trace),
            data={"result": "ok"},
            status=ArtifactStatus.SUCCESS,
        )
        return RunResult(
            output=artifact,
            trace=[],
            status=RunResultStatus.SUCCESS,
            call_metadata={
                "rendered_prompt": "test prompt",
                "raw_response": "test response",
                "tokens_used": 100,
                "latency_ms": 50,
                "input_data": str(input),
            },
        )


class ParseFailOperator:
    """Operator that raises AdapterParseError on first call, succeeds on second."""

    def __init__(self, name: str = "parse_fail_op") -> None:
        self._name = name
        self.call_count = 0

    @property
    def name(self) -> str:
        return self._name

    def run(self, input: Any, ctx: Context) -> RunResult:
        self.call_count += 1
        if self.call_count == 1:
            raise _make_parse_error("bad output format")
        artifact = Artifact(
            id=f"{self._name}_{ctx.budget.llm_calls_used}",
            operator=self._name,
            step_index=len(ctx.trace),
            data={"result": "repaired"},
            status=ArtifactStatus.REPAIR_SUCCEEDED,
        )
        return RunResult(
            output=artifact,
            trace=[],
            status=RunResultStatus.SUCCESS,
            call_metadata={
                "rendered_prompt": "repair prompt",
                "raw_response": "repaired response",
                "tokens_used": 120,
                "latency_ms": 60,
                "input_data": str(input),
            },
        )

    def run_repair(self, input: Any, ctx: Context, error: str) -> RunResult:
        """Repair attempt -- delegates to run which will succeed on second call."""
        return self.run(input, ctx)


class AlwaysFailOperator:
    """Operator that always raises AdapterParseError."""

    def __init__(self, name: str = "always_fail_op") -> None:
        self._name = name
        self.call_count = 0

    @property
    def name(self) -> str:
        return self._name

    def run(self, input: Any, ctx: Context) -> RunResult:
        self.call_count += 1
        raise _make_parse_error("always fails")

    def run_repair(self, input: Any, ctx: Context, error: str) -> RunResult:
        self.call_count += 1
        raise _make_parse_error("repair also fails")


class MockCombinator:
    """Mock combinator with is_combinator=True to test routing."""

    is_combinator = True

    def __init__(self, name: str = "mock_pipe") -> None:
        self._name = name
        self.run_called = False

    @property
    def name(self) -> str:
        return self._name

    def run(self, input: Any, ctx: Context) -> RunResult:
        self.run_called = True
        artifact = Artifact(
            id=f"{self._name}_0",
            operator=self._name,
            step_index=0,
            data={"combined": True},
            status=ArtifactStatus.SUCCESS,
        )
        return RunResult(
            output=artifact,
            trace=[],
            status=RunResultStatus.SUCCESS,
        )


# --- run_operator_with_retry tests ---


def test_run_operator_success() -> None:
    """Successful operator returns SUCCESS with artifact and runner-built trace."""
    op = MockOperator()
    ctx = Context(problem="test")

    result = run_operator_with_retry(op, "test input", ctx)

    assert result.status == RunResultStatus.SUCCESS
    assert isinstance(result.output, Artifact)
    assert result.output.data == {"result": "ok"}
    # Runner emits trace, not operator
    assert len(result.trace) == 1
    assert result.trace[0].event_type == TraceEventType.LLM_CALL


def test_run_operator_budget_exhaustion() -> None:
    """Budget-exhausted context returns BUDGET_EXHAUSTED without calling operator."""
    op = MockOperator()
    ctx = Context(problem="test", budget=Budget(max_llm_calls=0))

    result = run_operator_with_retry(op, "test input", ctx)

    assert result.status == RunResultStatus.BUDGET_EXHAUSTED
    assert op.call_count == 0  # operator never called


def test_run_operator_budget_deducted_on_ctx() -> None:
    """After successful run, ctx.budget.llm_calls_used increases by 1."""
    op = MockOperator()
    ctx = Context(problem="test")
    assert ctx.budget.llm_calls_used == 0

    run_operator_with_retry(op, "test input", ctx)

    assert ctx.budget.llm_calls_used == 1


def test_run_operator_retry_on_parse_failure() -> None:
    """Parse failure on first call triggers repair retry; result is SUCCESS."""
    op = ParseFailOperator()
    ctx = Context(problem="test")

    result = run_operator_with_retry(op, "test input", ctx)

    assert result.status == RunResultStatus.SUCCESS
    assert result.output.status == ArtifactStatus.REPAIR_SUCCEEDED


def test_run_operator_fails_after_retry() -> None:
    """Both attempts fail: result is FAILED with error details."""
    op = AlwaysFailOperator()
    ctx = Context(problem="test")

    result = run_operator_with_retry(op, "test input", ctx)

    assert result.status == RunResultStatus.FAILED
    assert result.errors is not None
    assert any(e.error_kind == "parse_failure" for e in result.errors)


def test_run_operator_budget_deducted_twice_on_retry() -> None:
    """After repair-succeeded run, ctx.budget.llm_calls_used increases by 2."""
    op = ParseFailOperator()
    ctx = Context(problem="test")

    run_operator_with_retry(op, "test input", ctx)

    # First attempt (failed) + second attempt (succeeded) = 2 deductions
    assert ctx.budget.llm_calls_used == 2


def test_run_operator_emits_trace() -> None:
    """After any run, RunResult.trace has TraceEntry with correct operator_name."""
    op = MockOperator(name="decompose")
    ctx = Context(problem="test")

    result = run_operator_with_retry(op, "test input", ctx)

    assert len(result.trace) >= 1
    assert result.trace[0].operator_name == "decompose"
    assert result.trace[0].event_type == TraceEventType.LLM_CALL


def test_run_operator_stores_artifact_in_ctx() -> None:
    """After successful run, ctx.artifacts contains the output artifact."""
    op = MockOperator()
    ctx = Context(problem="test")

    result = run_operator_with_retry(op, "test input", ctx)

    assert isinstance(result.output, Artifact)
    assert result.output.id in ctx.artifacts
    assert ctx.artifacts[result.output.id] is result.output


def test_run_operator_retry_checks_budget() -> None:
    """With budget for only 1 call, parse failure exhausts budget; retry is skipped."""
    op = ParseFailOperator()
    ctx = Context(problem="test", budget=Budget(max_llm_calls=1))

    result = run_operator_with_retry(op, "test input", ctx)

    # Budget exhausted after first failed attempt -- retry skipped
    assert result.status == RunResultStatus.BUDGET_EXHAUSTED
    assert result.errors is not None
    assert any("repair retry skipped" in e.message.lower() for e in result.errors)


def test_run_operator_trace_has_call_metadata() -> None:
    """After successful run, trace entry contains rendered_prompt and raw_response."""
    op = MockOperator()
    ctx = Context(problem="test")

    result = run_operator_with_retry(op, "test input", ctx)

    entry = result.trace[0]
    assert entry.rendered_prompt == "test prompt"
    assert entry.raw_response == "test response"


# --- PipelineRunner tests ---


def test_pipeline_runner_creates_context() -> None:
    """PipelineRunner.run() creates Context with problem and default budget."""
    op = MockOperator()
    runner = PipelineRunner()

    result = runner.run(op, "test problem")

    assert result.status == RunResultStatus.SUCCESS


def test_pipeline_runner_custom_budget() -> None:
    """PipelineRunner with custom budget passes it through."""
    op = MockOperator()
    runner = PipelineRunner(budget=Budget(max_llm_calls=3))

    result = runner.run(op, "test problem")

    # Budget should reflect the custom max and one deduction
    assert result.budget is not None
    assert result.budget.max_llm_calls == 3
    assert result.budget.llm_calls_used == 1


def test_pipeline_runner_routes_combinator_directly() -> None:
    """PipelineRunner routes is_combinator=True via .run() directly."""
    combinator = MockCombinator()
    runner = PipelineRunner()

    result = runner.run(combinator, "test problem")

    assert combinator.run_called is True
    assert result.status == RunResultStatus.SUCCESS


def test_pipeline_runner_wraps_leaf_operator() -> None:
    """PipelineRunner routes leaf operator via run_operator_with_retry."""
    op = MockOperator()
    runner = PipelineRunner()

    result = runner.run(op, "test problem")

    # Leaf operators get runner trace emission
    assert len(result.trace) == 1
    assert result.trace[0].event_type == TraceEventType.LLM_CALL


def test_pipeline_runner_populates_result_budget() -> None:
    """After run, result.budget matches the final ctx.budget snapshot."""
    op = MockOperator()
    runner = PipelineRunner(budget=Budget(max_llm_calls=5))

    result = runner.run(op, "test problem")

    assert result.budget is not None
    assert result.budget.llm_calls_used == 1
    assert result.budget.max_llm_calls == 5


def test_run_accepts_artifact_input() -> None:
    """PipelineRunner.run() accepts Artifact as problem for meta-skill pipelines."""
    op = MockOperator()
    runner = PipelineRunner()
    artifact = Artifact(
        id="source_skill_0",
        operator="ingest",
        step_index=0,
        data={"skill_name": "lateral-shift"},
        status=ArtifactStatus.SUCCESS,
    )

    result = runner.run(op, artifact)

    assert result.status == RunResultStatus.SUCCESS
    assert isinstance(result.output, Artifact)


def test_run_populates_artifacts_field() -> None:
    """PipelineRunner.run() populates result.artifacts from ctx.artifacts."""
    op = MockOperator()
    runner = PipelineRunner()

    result = runner.run(op, "test problem")

    # After run, artifacts should be a dict (populated from ctx.artifacts)
    assert result.artifacts is not None
    assert isinstance(result.artifacts, dict)
    # The mock operator produces one artifact stored in ctx
    assert len(result.artifacts) >= 1
