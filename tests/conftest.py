"""Shared fixtures for dillylang test suite."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from dillylang.vocab.types import (
    Artifact,
    ArtifactStatus,
    Budget,
    Context,
    ItemError,
    RunResult,
    RunResultStatus,
    TraceEntry,
    TraceEventType,
)


@pytest.fixture
def sample_artifact() -> Artifact:
    """A minimal valid Artifact for test composition."""
    return Artifact(
        id="test_0",
        operator="test_op",
        step_index=0,
        data={"key": "value"},
        status=ArtifactStatus.SUCCESS,
    )


@pytest.fixture
def sample_budget() -> Budget:
    """Budget with all defaults (7 call ceiling, zero counters)."""
    return Budget()


@pytest.fixture
def sample_context(sample_artifact: Artifact, sample_budget: Budget) -> Context:
    """Context with a single artifact and default budget."""
    return Context(
        problem="test problem",
        artifacts={"test_op_0": sample_artifact},
        budget=sample_budget,
    )


@pytest.fixture
def sample_trace_entry() -> TraceEntry:
    """A realistic LLM_CALL trace entry."""
    return TraceEntry(
        trace_id="trace_001",
        event_type=TraceEventType.LLM_CALL,
        operator_name="decompose",
        step_index=0,
        timestamp=datetime(2026, 5, 1, tzinfo=timezone.utc),
        status=ArtifactStatus.SUCCESS,
        input={"problem": "test"},
        rendered_prompt="Decompose this problem...",
        raw_response='{"axioms": []}',
        parsed_output={"axioms": []},
        tokens_used=150,
        latency_ms=1200,
    )


class MockOperator:
    """Minimal OperatorProtocol implementation for testing."""

    def __init__(self, op_name: str = "mock_op") -> None:
        self._name = op_name

    @property
    def name(self) -> str:
        return self._name

    def run(self, input: Any, ctx: Context) -> RunResult:
        artifact = Artifact(
            id=f"{self._name}_0",
            operator=self._name,
            step_index=0,
            data={"result": "mock"},
            status=ArtifactStatus.SUCCESS,
        )
        return RunResult(output=artifact, status=RunResultStatus.SUCCESS)


@pytest.fixture
def mock_operator() -> MockOperator:
    """A mock operator implementing OperatorProtocol."""
    return MockOperator()


# --- Integration test support ---


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add --run-integration flag for tests requiring LLM access."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that require a configured LLM",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip integration tests unless --run-integration is passed."""
    if config.getoption("--run-integration"):
        return
    skip_integration = pytest.mark.skip(reason="needs --run-integration flag")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


@pytest.fixture(scope="session")
def configure_dspy_lm() -> None:
    """Configure DSPy with an LLM for integration tests.

    Priority: DILLYLANG_LM (project convention via mise/nanovault),
    then ANTHROPIC_API_KEY, then OPENAI_API_KEY.
    """
    import dspy

    if lm_model := os.environ.get("DILLYLANG_LM"):
        # Project-specific config matching cli/main.py convention
        kwargs: dict = {}
        if base := os.environ.get("DILLYLANG_LM_BASE"):
            kwargs["api_base"] = base
        lm_key = os.environ.get("DILLYLANG_LM_API_KEY", "ollama")
        kwargs["api_key"] = lm_key
        if max_tokens := os.environ.get("DILLYLANG_LM_MAX_TOKENS"):
            kwargs["max_tokens"] = int(max_tokens)
        lm = dspy.LM(lm_model, **kwargs)
        dspy.configure(lm=lm, adapter=dspy.JSONAdapter())
    elif api_key := os.environ.get("ANTHROPIC_API_KEY"):
        lm = dspy.LM("anthropic/claude-sonnet-4-20250514", api_key=api_key)
        dspy.configure(lm=lm, adapter=dspy.JSONAdapter())
    elif api_key := os.environ.get("OPENAI_API_KEY"):
        lm = dspy.LM("openai/gpt-4o-mini", api_key=api_key)
        dspy.configure(lm=lm, adapter=dspy.JSONAdapter())
    else:
        pytest.skip("No DILLYLANG_LM, ANTHROPIC_API_KEY, or OPENAI_API_KEY set")


# --- Pipeline run persistence ---

PIPELINE_RUNS_DIR = Path(__file__).parent.parent / "archive" / "pipeline-runs"


def _get_lm_metadata() -> dict[str, Any]:
    """Extract LM configuration from DSPy's active settings."""
    try:
        import dspy
        lm = dspy.settings.lm
        if lm is None:
            return {"model": "unknown"}
        meta: dict[str, Any] = {"model": lm.model}
        if api_base := lm.kwargs.get("api_base"):
            meta["api_base"] = api_base
        meta["provider"] = type(lm.provider).__name__
        return meta
    except Exception:
        return {"model": "unknown"}


@pytest.fixture
def persist_pipeline_run() -> Any:
    """Fixture that persists integration test runs via substrate's persist_run.

    Writes per-step I/O (trace), all intermediate artifacts, budget state,
    rendered outputs, and LM metadata to archive/pipeline-runs/.
    """
    from dillylang.runner.persist import persist_run
    from dillylang.vocab.types import RunResult

    def _persist(
        *,
        test_name: str,
        run_result: RunResult,
        inputs: dict[str, Any] | None = None,
        rendered: dict[str, Any] | None = None,
        extra_runs: dict[str, RunResult] | None = None,
    ) -> Path:
        metadata = {"lm": _get_lm_metadata()}

        if rendered:
            if inputs is None:
                inputs = {}
            inputs["_rendered_outputs"] = rendered

        run_dir = persist_run(
            run_result,
            base_dir=PIPELINE_RUNS_DIR,
            name=f"test-{test_name}",
            inputs=inputs,
            metadata=metadata,
        )

        # Persist additional pipeline runs (e.g. analyze after translate)
        if extra_runs:
            from dillylang.runner.persist import serialize_run
            for label, extra_result in extra_runs.items():
                extra_path = run_dir / f"run-{label}.json"
                record = serialize_run(extra_result, name=label)
                extra_path.write_text(
                    json.dumps(record, indent=2, default=str)
                )

        return run_dir

    return _persist
