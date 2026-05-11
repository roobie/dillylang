"""TraceEntry factory functions for different event types.

The runner is the sole owner of trace emission -- operators return raw
Artifact with empty trace, and the runner constructs TraceEntry instances
using call_metadata from operator results.

Each factory generates a unique trace_id and sets the timestamp.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from dillylang.vocab.types import ArtifactStatus, TraceEntry, TraceEventType


def emit_llm_call(
    operator_name: str,
    step_index: int,
    status: ArtifactStatus,
    input_data: Any = None,
    rendered_prompt: str | None = None,
    raw_response: str | None = None,
    parsed_output: Any = None,
    tokens_used: int | None = None,
    latency_ms: int | None = None,
) -> TraceEntry:
    """Create a trace entry for an LLM call event."""
    return TraceEntry(
        trace_id=f"trace_{operator_name}_{step_index}_{uuid4().hex[:8]}",
        event_type=TraceEventType.LLM_CALL,
        operator_name=operator_name,
        step_index=step_index,
        timestamp=datetime.now(timezone.utc),
        status=status,
        input=input_data,
        rendered_prompt=rendered_prompt,
        raw_response=raw_response,
        parsed_output=parsed_output,
        tokens_used=tokens_used,
        latency_ms=latency_ms,
    )


def emit_combinator_start(
    combinator_name: str,
    step_index: int,
    children_ids: list[str] | None = None,
) -> TraceEntry:
    """Create a trace entry marking the start of a combinator."""
    return TraceEntry(
        trace_id=f"trace_{combinator_name}_{step_index}_{uuid4().hex[:8]}",
        event_type=TraceEventType.COMBINATOR_START,
        operator_name=combinator_name,
        step_index=step_index,
        timestamp=datetime.now(timezone.utc),
        status=ArtifactStatus.SUCCESS,
        children=children_ids,
    )


def emit_combinator_end(
    combinator_name: str,
    step_index: int,
    status: ArtifactStatus,
    children_ids: list[str] | None = None,
) -> TraceEntry:
    """Create a trace entry marking the end of a combinator."""
    return TraceEntry(
        trace_id=f"trace_{combinator_name}_{step_index}_{uuid4().hex[:8]}",
        event_type=TraceEventType.COMBINATOR_END,
        operator_name=combinator_name,
        step_index=step_index,
        timestamp=datetime.now(timezone.utc),
        status=status,
        children=children_ids,
    )


def emit_selector(
    field_name: str,
    step_index: int,
    selected_count: int,
) -> TraceEntry:
    """Create a trace entry for a selector event."""
    return TraceEntry(
        trace_id=f"trace_select_{step_index}_{uuid4().hex[:8]}",
        event_type=TraceEventType.SELECTOR,
        operator_name="select",
        step_index=step_index,
        timestamp=datetime.now(timezone.utc),
        status=ArtifactStatus.SUCCESS,
        field=field_name,
        selected_count=selected_count,
    )
