"""Tests for trace emission factory functions."""

from __future__ import annotations

from datetime import datetime, timezone

from dillylang.trace.emit import (
    emit_combinator_end,
    emit_combinator_start,
    emit_llm_call,
    emit_selector,
)
from dillylang.vocab.types import ArtifactStatus, TraceEventType


def test_emit_llm_call_creates_trace_entry() -> None:
    """emit_llm_call produces an LLM_CALL entry with correct fields."""
    entry = emit_llm_call(
        operator_name="decompose",
        step_index=0,
        status=ArtifactStatus.SUCCESS,
        input_data="test input",
    )

    assert entry.event_type == TraceEventType.LLM_CALL
    assert entry.operator_name == "decompose"
    assert entry.step_index == 0
    assert entry.status == ArtifactStatus.SUCCESS
    # Timestamp should be recent (within the last second)
    assert (datetime.now(timezone.utc) - entry.timestamp).total_seconds() < 1


def test_emit_llm_call_generates_unique_trace_ids() -> None:
    """Two calls to emit_llm_call produce different trace_ids."""
    entry1 = emit_llm_call("decompose", 0, ArtifactStatus.SUCCESS)
    entry2 = emit_llm_call("decompose", 0, ArtifactStatus.SUCCESS)

    assert entry1.trace_id != entry2.trace_id


def test_emit_combinator_start_creates_entry() -> None:
    """emit_combinator_start produces a COMBINATOR_START entry."""
    entry = emit_combinator_start("pipe", step_index=0, children_ids=["c1", "c2"])

    assert entry.event_type == TraceEventType.COMBINATOR_START
    assert entry.operator_name == "pipe"
    assert entry.children == ["c1", "c2"]
    assert entry.status == ArtifactStatus.SUCCESS


def test_emit_combinator_end_carries_status() -> None:
    """emit_combinator_end propagates the given status."""
    entry = emit_combinator_end(
        "parallel", step_index=1, status=ArtifactStatus.PARTIAL
    )

    assert entry.event_type == TraceEventType.COMBINATOR_END
    assert entry.status == ArtifactStatus.PARTIAL


def test_emit_selector_carries_field_info() -> None:
    """emit_selector records field name and selected count."""
    entry = emit_selector(field_name="assumptions", step_index=2, selected_count=3)

    assert entry.event_type == TraceEventType.SELECTOR
    assert entry.operator_name == "select"
    assert entry.field == "assumptions"
    assert entry.selected_count == 3
