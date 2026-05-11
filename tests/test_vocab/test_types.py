"""Tests for dillylang.vocab.types -- core vocabulary types."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone

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


def test_artifact_round_trip(sample_artifact: Artifact) -> None:
    """Artifact survives model_dump/model_validate round-trip."""
    dumped = sample_artifact.model_dump()
    restored = Artifact.model_validate(dumped)
    assert restored.id == sample_artifact.id
    assert restored.operator == sample_artifact.operator
    assert restored.step_index == sample_artifact.step_index
    assert restored.data == sample_artifact.data
    assert restored.status == sample_artifact.status
    assert restored.errors is None


def test_artifact_status_values() -> None:
    """All 4 ArtifactStatus enum members exist with correct string values."""
    assert ArtifactStatus.SUCCESS == "success"
    assert ArtifactStatus.REPAIR_SUCCEEDED == "repair_succeeded"
    assert ArtifactStatus.FAILED == "failed"
    assert ArtifactStatus.PARTIAL == "partial"
    assert len(ArtifactStatus) == 4


def test_budget_defaults() -> None:
    """Budget defaults match spec section 10 ceiling and zero counters."""
    b = Budget()
    assert b.max_llm_calls == 7
    assert b.max_tokens == 100_000
    assert b.max_wall_time_ms == 300_000
    assert b.llm_calls_used == 0
    assert b.tokens_used == 0
    assert b.elapsed_ms == 0


def test_run_result_status_values() -> None:
    """All 4 RunResultStatus enum members exist."""
    assert RunResultStatus.SUCCESS == "success"
    assert RunResultStatus.PARTIAL == "partial"
    assert RunResultStatus.FAILED == "failed"
    assert RunResultStatus.BUDGET_EXHAUSTED == "budget_exhausted"
    assert len(RunResultStatus) == 4


def test_trace_entry_round_trip(sample_trace_entry: TraceEntry) -> None:
    """TraceEntry with LLM_CALL fields survives round-trip."""
    dumped = sample_trace_entry.model_dump()
    restored = TraceEntry.model_validate(dumped)
    assert restored.trace_id == sample_trace_entry.trace_id
    assert restored.event_type == TraceEventType.LLM_CALL
    assert restored.operator_name == "decompose"
    assert restored.tokens_used == 150
    assert restored.latency_ms == 1200
    assert restored.rendered_prompt is not None


def test_trace_event_type_values() -> None:
    """All 4 TraceEventType members exist."""
    assert TraceEventType.LLM_CALL == "llm_call"
    assert TraceEventType.COMBINATOR_START == "combinator_start"
    assert TraceEventType.COMBINATOR_END == "combinator_end"
    assert TraceEventType.SELECTOR == "selector"
    assert len(TraceEventType) == 4


def test_context_mutable_defaults() -> None:
    """Two Context instances do NOT share artifacts dict or trace list."""
    ctx_a = Context(problem="a")
    ctx_b = Context(problem="b")
    # Mutate one, ensure the other is unaffected
    ctx_a.artifacts["x"] = Artifact(
        id="x", operator="op", step_index=0,
        data={}, status=ArtifactStatus.SUCCESS,
    )
    ctx_a.trace.append(
        TraceEntry(
            trace_id="t1", event_type=TraceEventType.LLM_CALL,
            operator_name="op", step_index=0,
            timestamp=datetime.now(timezone.utc),
            status=ArtifactStatus.SUCCESS,
        )
    )
    assert len(ctx_b.artifacts) == 0
    assert len(ctx_b.trace) == 0


def test_item_error_round_trip() -> None:
    """ItemError round-trips through model_dump/model_validate."""
    err = ItemError(
        item_id="item_0",
        error_kind="parse_failure",
        message="failed to parse output",
    )
    dumped = err.model_dump()
    restored = ItemError.model_validate(dumped)
    assert restored.item_id == err.item_id
    assert restored.error_kind == err.error_kind
    assert restored.message == err.message


def test_import_all_types() -> None:
    """All 9 public types are importable from dillylang.vocab.types."""
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
    # Verify they are actual classes, not None
    for cls in [
        Artifact, ArtifactStatus, Budget, Context, ItemError,
        RunResult, RunResultStatus, TraceEntry, TraceEventType,
    ]:
        assert cls is not None


def test_vocab_no_dspy_import() -> None:
    """Vocab layer imports successfully with DSPy blocked.

    This proves the vocabulary has zero DSPy dependency -- the
    architectural invariant from spec section 10.
    """
    result = subprocess.run(
        [
            sys.executable, "-c",
            "import sys; sys.modules['dspy'] = None; "
            "from dillylang.vocab.types import Artifact, Budget, RunResult; "
            "print('OK')",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, f"Import failed: {result.stderr}"
    assert "OK" in result.stdout


def test_run_result_with_artifact(sample_artifact: Artifact) -> None:
    """RunResult can hold a single artifact or a list."""
    single = RunResult(
        output=sample_artifact, status=RunResultStatus.SUCCESS,
    )
    assert single.output == sample_artifact

    multi = RunResult(
        output=[sample_artifact], status=RunResultStatus.PARTIAL,
    )
    assert isinstance(multi.output, list)
    assert len(multi.output) == 1
