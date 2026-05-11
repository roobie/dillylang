"""Tests for CLI trace viewer: tree rendering, verbose mode, run result display.

Uses sample trace data representing a refine pipeline:
  pipe -> decompose -> parallel(invert, rotate) -> synthesize
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import StringIO

from rich.console import Console

from dillylang.trace.viewer import format_trace_summary, render_run_result, render_trace
from dillylang.vocab.types import (
    Artifact,
    ArtifactStatus,
    Budget,
    ItemError,
    RunResult,
    RunResultStatus,
    TraceEntry,
    TraceEventType,
)


def _ts() -> datetime:
    """Fixed timestamp for deterministic tests."""
    return datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


def _sample_trace() -> list[TraceEntry]:
    """Build a representative refine pipeline trace.

    Structure: pipe(decompose, parallel(invert, rotate), synthesize)
    """
    return [
        # pipe start
        TraceEntry(
            trace_id="t_pipe_start",
            event_type=TraceEventType.COMBINATOR_START,
            operator_name="pipe",
            step_index=0,
            timestamp=_ts(),
            status=ArtifactStatus.SUCCESS,
        ),
        # decompose
        TraceEntry(
            trace_id="t_decompose",
            event_type=TraceEventType.LLM_CALL,
            operator_name="decompose",
            step_index=1,
            timestamp=_ts(),
            status=ArtifactStatus.SUCCESS,
            input="Should we rewrite our monolith?",
            rendered_prompt="Decompose this problem into axioms...",
            raw_response='{"axioms": [{"statement": "s1", "justification": "j1"}]}',
            parsed_output={"axioms": [{"statement": "s1"}]},
            tokens_used=150,
            latency_ms=1200,
        ),
        # parallel start
        TraceEntry(
            trace_id="t_parallel_start",
            event_type=TraceEventType.COMBINATOR_START,
            operator_name="parallel",
            step_index=2,
            timestamp=_ts(),
            status=ArtifactStatus.SUCCESS,
            children=["invert", "rotate"],
        ),
        # invert
        TraceEntry(
            trace_id="t_invert",
            event_type=TraceEventType.LLM_CALL,
            operator_name="invert",
            step_index=3,
            timestamp=_ts(),
            status=ArtifactStatus.SUCCESS,
            input="decompose output",
            rendered_prompt="Invert this: find failure modes...",
            raw_response='{"failure_modes": []}',
            parsed_output={"failure_modes": []},
            tokens_used=120,
            latency_ms=900,
        ),
        # rotate
        TraceEntry(
            trace_id="t_rotate",
            event_type=TraceEventType.LLM_CALL,
            operator_name="rotate",
            step_index=4,
            timestamp=_ts(),
            status=ArtifactStatus.SUCCESS,
            input="decompose output",
            rendered_prompt="Rotate perspective on this problem...",
            raw_response='{"rotations": []}',
            parsed_output={"rotations": []},
            tokens_used=130,
            latency_ms=950,
        ),
        # parallel end
        TraceEntry(
            trace_id="t_parallel_end",
            event_type=TraceEventType.COMBINATOR_END,
            operator_name="parallel",
            step_index=5,
            timestamp=_ts(),
            status=ArtifactStatus.SUCCESS,
        ),
        # synthesize
        TraceEntry(
            trace_id="t_synthesize",
            event_type=TraceEventType.LLM_CALL,
            operator_name="synthesize",
            step_index=6,
            timestamp=_ts(),
            status=ArtifactStatus.SUCCESS,
            input="parallel outputs",
            rendered_prompt="Synthesize these perspectives...",
            raw_response='{"proposal": {"statement": "s", "rationale": "r"}}',
            parsed_output={"proposal": {"statement": "s", "rationale": "r"}},
            tokens_used=200,
            latency_ms=1500,
        ),
        # pipe end
        TraceEntry(
            trace_id="t_pipe_end",
            event_type=TraceEventType.COMBINATOR_END,
            operator_name="pipe",
            step_index=7,
            timestamp=_ts(),
            status=ArtifactStatus.SUCCESS,
        ),
    ]


def _capture_output(func, *args, **kwargs) -> str:
    """Capture rich console output as plain text."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=False, width=120)
    func(*args, console=console, **kwargs)
    return buf.getvalue()


# --- format_trace_summary ---


def test_format_trace_summary_llm_call():
    entry = TraceEntry(
        trace_id="t1",
        event_type=TraceEventType.LLM_CALL,
        operator_name="decompose",
        step_index=0,
        timestamp=_ts(),
        status=ArtifactStatus.SUCCESS,
        tokens_used=150,
        latency_ms=1200,
    )
    summary = format_trace_summary(entry)
    assert "decompose" in summary
    assert "success" in summary
    assert "tokens=150" in summary
    assert "latency=1200ms" in summary


def test_format_trace_summary_combinator():
    entry = TraceEntry(
        trace_id="t2",
        event_type=TraceEventType.COMBINATOR_START,
        operator_name="pipe",
        step_index=0,
        timestamp=_ts(),
        status=ArtifactStatus.SUCCESS,
    )
    summary = format_trace_summary(entry)
    assert "pipe" in summary
    assert "combinator_start" in summary


# --- render_trace ---


def test_render_trace_no_error():
    """render_trace with sample trace should not raise."""
    trace = _sample_trace()
    output = _capture_output(render_trace, trace)
    assert len(output) > 0


def test_render_trace_shows_operator_names():
    """Output contains all operator names from the trace."""
    trace = _sample_trace()
    output = _capture_output(render_trace, trace)
    assert "decompose" in output
    assert "invert" in output
    assert "rotate" in output
    assert "synthesize" in output


def test_render_trace_shows_status():
    """Output contains status indicators."""
    trace = _sample_trace()
    output = _capture_output(render_trace, trace)
    assert "success" in output


def test_render_trace_verbose_shows_prompt():
    """Verbose mode includes rendered prompt content."""
    trace = _sample_trace()
    output = _capture_output(render_trace, trace, verbose=True)
    # The decompose entry has rendered_prompt="Decompose this problem into axioms..."
    assert "Decompose this problem" in output


def test_render_trace_verbose_warning():
    """Verbose mode displays sensitive data warning."""
    trace = _sample_trace()
    output = _capture_output(render_trace, trace, verbose=True)
    assert "sensitive data" in output.lower()


def test_render_trace_tree_structure():
    """Tree output shows indentation: parallel contents nested under parallel node.

    Rich tree uses guide characters for nesting. The parallel branch should
    be indented under the pipe branch, and invert/rotate under parallel.
    """
    trace = _sample_trace()
    output = _capture_output(render_trace, trace)
    # The tree structure means "parallel" appears between pipe's content.
    # Both "invert" and "rotate" should appear after "parallel" in the output.
    parallel_pos = output.index("parallel")
    invert_pos = output.index("invert")
    rotate_pos = output.index("rotate")
    # invert and rotate come after the parallel start
    assert invert_pos > parallel_pos
    assert rotate_pos > parallel_pos


def test_render_trace_empty():
    """Empty trace renders without error."""
    output = _capture_output(render_trace, [])
    assert "Pipeline Trace" in output


# --- render_run_result ---


def _sample_artifact() -> Artifact:
    return Artifact(
        id="synth_0",
        operator="synthesize",
        step_index=6,
        data={"proposal": {"statement": "use modular monolith", "rationale": "lower risk"}},
        status=ArtifactStatus.SUCCESS,
    )


def test_render_run_result_shows_status():
    result = RunResult(
        output=_sample_artifact(),
        trace=_sample_trace(),
        status=RunResultStatus.SUCCESS,
    )
    output = _capture_output(render_run_result, result)
    assert "success" in output.lower()


def test_render_run_result_shows_errors():
    result = RunResult(
        output=_sample_artifact(),
        trace=[],
        status=RunResultStatus.FAILED,
        errors=[
            ItemError(
                item_id="op_err",
                error_kind="parse_failure",
                message="Could not parse LLM output",
            )
        ],
    )
    output = _capture_output(render_run_result, result)
    assert "parse_failure" in output
    assert "Could not parse" in output


def test_render_run_result_shows_budget():
    result = RunResult(
        output=_sample_artifact(),
        trace=_sample_trace(),
        status=RunResultStatus.SUCCESS,
        budget=Budget(
            max_llm_calls=7,
            max_tokens=30000,
            llm_calls_used=4,
            tokens_used=600,
        ),
    )
    output = _capture_output(render_run_result, result)
    assert "4/7" in output
    assert "600/30000" in output


def test_render_run_result_handles_no_budget():
    """No crash and no budget line when result.budget is None."""
    result = RunResult(
        output=_sample_artifact(),
        trace=_sample_trace(),
        status=RunResultStatus.SUCCESS,
        budget=None,
    )
    output = _capture_output(render_run_result, result)
    # Should not contain "Budget:" line
    assert "Budget:" not in output
    # But should still render the trace
    assert "decompose" in output
