"""Integration tests: refine recipe end-to-end composition.

Tests both mock-based (always run) and real LLM (--run-integration flag).
The refine recipe is: pipe(decompose, parallel(invert, rotate), synthesize).

Mock-based tests verify combinators + runner compose correctly with
operator-shaped mocks. Real LLM tests prove the full stack works against
an actual model.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from dillylang.combinators import parallel, pipe
from dillylang.runner.runner import PipelineRunner
from dillylang.vocab.types import (
    Artifact,
    ArtifactStatus,
    Budget,
    Context,
    RunResult,
    RunResultStatus,
    TraceEventType,
)


# --- Mock operator implementing OperatorProtocol ---


class MockLLMOperator:
    """Mock operator with configurable output for integration testing.

    Returns pre-configured structured output matching operator schemas.
    Returns trace=[] per the operator contract (runner owns trace).
    Tracks call count and inputs for assertion.
    """

    def __init__(
        self,
        op_name: str,
        output_data: dict[str, Any],
        status: RunResultStatus = RunResultStatus.SUCCESS,
    ) -> None:
        self._name = op_name
        self._output_data = output_data
        self._status = status
        self.call_count = 0
        self.inputs: list[Any] = []

    @property
    def name(self) -> str:
        return self._name

    def run(self, input: Any, ctx: Context) -> RunResult:
        self.call_count += 1
        self.inputs.append(input)
        artifact_status = (
            ArtifactStatus.FAILED
            if self._status == RunResultStatus.FAILED
            else ArtifactStatus.SUCCESS
        )
        return RunResult(
            output=Artifact(
                id=f"{self._name}_{self.call_count - 1}",
                operator=self._name,
                step_index=len(ctx.trace),
                data=self._output_data,
                status=artifact_status,
            ),
            trace=[],
            status=self._status,
        )


# --- Mock output data matching operator schemas ---

MOCK_DECOMPOSE_OUTPUT = {
    "axioms": [
        {"statement": "Monoliths have lower operational overhead", "justification": "Single deployment unit"},
        {"statement": "Microservices enable independent scaling", "justification": "Isolated service boundaries"},
    ],
    "derivations": [
        {"claim": "Team size affects architecture choice", "depends_on": ["Monoliths have lower operational overhead"]},
    ],
    "assumptions": [
        {"statement": "Team will grow beyond 5 engineers", "load_bearing": True, "testable": "Check hiring plan"},
    ],
}

MOCK_INVERT_OUTPUT = {
    "anti_goals": ["Maximize coupling between services", "Eliminate all documentation"],
    "failure_modes": [
        {
            "mode": "Distributed monolith",
            "mechanism": "Shared database across microservices without clear boundaries",
            "likelihood": "high",
            "severity": "costly",
            "preventable_by": "Enforce strict API boundaries from day one",
        },
    ],
    "near_misses": ["Event-driven architecture that almost causes data inconsistency"],
}

MOCK_ROTATE_OUTPUT = {
    "original_axis": "technical architecture choice",
    "rotations": [
        {
            "new_axis": "team organization",
            "rotation_kind": "viewpoint_change",
            "restated_problem": "How should we organize teams to deliver features independently?",
            "what_becomes_visible": ["Conway's law implications", "team autonomy"],
            "what_recedes": ["Technical debt measurement", "Performance benchmarking"],
        },
        {
            "new_axis": "business evolution",
            "rotation_kind": "axis_change",
            "restated_problem": "What architecture supports the business 2 years from now?",
            "what_becomes_visible": ["Growth trajectory", "Market responsiveness"],
            "what_recedes": ["Current technical constraints"],
        },
    ],
}

MOCK_SYNTHESIZE_OUTPUT = {
    "proposal": {
        "statement": "Start with modular monolith, extract services at team boundaries",
        "rationale": "Balances operational simplicity with future decomposition readiness",
    },
    "incorporates": [
        {"source_artifact_id": "decompose_0", "contribution": "Axiom structure revealed key tradeoffs"},
        {"source_artifact_id": "invert_0", "contribution": "Failure modes identified distributed monolith risk"},
        {"source_artifact_id": "rotate_0", "contribution": "Team organization axis reframed the decision"},
    ],
    "tradeoffs": [
        {"gained": "Operational simplicity now", "given_up": "Service-level scaling flexibility"},
    ],
    "open_questions": ["When exactly should first service extraction happen?"],
    "conflicts_addressed": [
        {
            "conflict": "Monolith simplicity vs microservice flexibility",
            "resolution": "resolved",
        },
    ],
    "confidence": "medium",
}

MOCK_ANALOGIZE_OUTPUT = {
    "problem_signature": "premature optimization of system boundaries",
    "analogies": [
        {
            "domain": "urban planning",
            "analog": "zoning before understanding traffic patterns",
            "mechanism_mapping": "Premature service boundaries are like premature zoning",
            "transferable_insight": "Observe actual usage before partitioning",
            "stowaways": ["Cities can't be redeployed"],
        },
    ],
}


# --- Mock-based integration tests (always run) ---


def test_refine_recipe_composes():
    """Refine recipe composes and runs end-to-end, producing SUCCESS with trace."""
    mock_decompose = MockLLMOperator("decompose", MOCK_DECOMPOSE_OUTPUT)
    mock_invert = MockLLMOperator("invert", MOCK_INVERT_OUTPUT)
    mock_rotate = MockLLMOperator("rotate", MOCK_ROTATE_OUTPUT)
    mock_synthesize = MockLLMOperator("synthesize", MOCK_SYNTHESIZE_OUTPUT)

    refine = pipe(
        mock_decompose,
        parallel(mock_invert, mock_rotate),
        mock_synthesize,
    )

    result = PipelineRunner().run(refine, "Should we rewrite our monolith?")

    assert result.status == RunResultStatus.SUCCESS
    assert isinstance(result.output, Artifact)
    assert result.output.data["proposal"]["statement"]  # synthesize produced a proposal

    # Trace has entries for all operators + combinator bookkeeping
    assert len(result.trace) >= 4
    op_names_in_trace = {e.operator_name for e in result.trace if e.event_type == TraceEventType.LLM_CALL}
    assert {"decompose", "invert", "rotate", "synthesize"} == op_names_in_trace

    # Every operator was called exactly once
    assert mock_decompose.call_count == 1
    assert mock_invert.call_count == 1
    assert mock_rotate.call_count == 1
    assert mock_synthesize.call_count == 1


def test_refine_recipe_budget_tracking():
    """Refine recipe consumes exactly 4 LLM calls (decompose + invert + rotate + synthesize)."""
    refine = pipe(
        MockLLMOperator("decompose", MOCK_DECOMPOSE_OUTPUT),
        parallel(
            MockLLMOperator("invert", MOCK_INVERT_OUTPUT),
            MockLLMOperator("rotate", MOCK_ROTATE_OUTPUT),
        ),
        MockLLMOperator("synthesize", MOCK_SYNTHESIZE_OUTPUT),
    )

    result = PipelineRunner(budget=Budget(max_llm_calls=7)).run(
        refine, "Architecture question"
    )

    assert result.status == RunResultStatus.SUCCESS
    assert result.budget is not None
    assert result.budget.llm_calls_used == 4


def test_refine_recipe_short_circuits_on_budget():
    """Budget(max_llm_calls=2) should exhaust mid-pipeline.

    decompose uses call 1, parallel starts: invert uses call 2 (budget hit),
    rotate cannot run -> BUDGET_EXHAUSTED.
    """
    mock_decompose = MockLLMOperator("decompose", MOCK_DECOMPOSE_OUTPUT)
    mock_invert = MockLLMOperator("invert", MOCK_INVERT_OUTPUT)
    mock_rotate = MockLLMOperator("rotate", MOCK_ROTATE_OUTPUT)
    mock_synthesize = MockLLMOperator("synthesize", MOCK_SYNTHESIZE_OUTPUT)

    refine = pipe(
        mock_decompose,
        parallel(mock_invert, mock_rotate),
        mock_synthesize,
    )

    result = PipelineRunner(budget=Budget(max_llm_calls=2)).run(
        refine, "Tight budget question"
    )

    assert result.status == RunResultStatus.BUDGET_EXHAUSTED
    # decompose and invert ran, but rotate was blocked by budget
    assert mock_decompose.call_count == 1
    assert mock_invert.call_count == 1
    assert mock_rotate.call_count == 0
    # synthesize never reached
    assert mock_synthesize.call_count == 0
    # Trace shows partial execution
    assert len(result.trace) > 0


def test_refine_recipe_handles_operator_failure():
    """Invert failing in parallel -> PARTIAL, synthesize still runs with partial results."""
    mock_decompose = MockLLMOperator("decompose", MOCK_DECOMPOSE_OUTPUT)
    mock_invert = MockLLMOperator(
        "invert", MOCK_INVERT_OUTPUT, status=RunResultStatus.FAILED
    )
    mock_rotate = MockLLMOperator("rotate", MOCK_ROTATE_OUTPUT)
    mock_synthesize = MockLLMOperator("synthesize", MOCK_SYNTHESIZE_OUTPUT)

    refine = pipe(
        mock_decompose,
        parallel(mock_invert, mock_rotate),
        mock_synthesize,
    )

    result = PipelineRunner().run(refine, "One branch fails")

    # parallel returns PARTIAL (invert failed, rotate succeeded).
    # pipe continues because PARTIAL is not a short-circuit condition.
    # synthesize runs on the partial results.
    assert result.status == RunResultStatus.PARTIAL
    assert mock_synthesize.call_count == 1

    # Trace has entries showing the failure
    failed_entries = [
        e for e in result.trace
        if e.event_type == TraceEventType.LLM_CALL and e.status == ArtifactStatus.FAILED
    ]
    assert len(failed_entries) >= 1


def test_wide_pass_recipe_composes():
    """wide_pass: pipe(parallel(decompose, invert, rotate, analogize), synthesize) with 5 mock calls."""
    refine = pipe(
        parallel(
            MockLLMOperator("decompose", MOCK_DECOMPOSE_OUTPUT),
            MockLLMOperator("invert", MOCK_INVERT_OUTPUT),
            MockLLMOperator("rotate", MOCK_ROTATE_OUTPUT),
            MockLLMOperator("analogize", MOCK_ANALOGIZE_OUTPUT),
        ),
        MockLLMOperator("synthesize", MOCK_SYNTHESIZE_OUTPUT),
    )

    result = PipelineRunner(budget=Budget(max_llm_calls=7)).run(
        refine, "Broad analysis question"
    )

    assert result.status == RunResultStatus.SUCCESS
    assert result.budget is not None
    assert result.budget.llm_calls_used == 5


# --- Real LLM integration tests (require --run-integration) ---


@pytest.mark.integration
def test_refine_real_llm(configure_dspy_lm):
    """Compose and run refine with real LLM. Verify structure, not content."""
    from dillylang.operators import (
        DecomposeOperator,
        InvertOperator,
        RotateOperator,
        SynthesizeOperator,
    )
    from dillylang.trace.viewer import render_run_result

    refine = pipe(
        DecomposeOperator(),
        parallel(InvertOperator(), RotateOperator()),
        SynthesizeOperator(),
    )

    result = PipelineRunner(budget=Budget(max_llm_calls=7)).run(
        refine,
        "Should a solo developer use microservices or a modular monolith?",
    )

    assert result.status in (RunResultStatus.SUCCESS, RunResultStatus.PARTIAL)
    assert isinstance(result.output, Artifact)
    assert "proposal" in result.output.data
    assert len(result.trace) >= 4

    # Visual inspection
    render_run_result(result)


@pytest.mark.integration
def test_refine_lateral_shift_baseline(configure_dspy_lm):
    """D-04 lateral-shift-compatible integration test.

    Uses a problem that lateral-shift is designed for: a stuck perspective
    that needs reframing. Validates that operator outputs have substantive
    content comparable to what lateral-shift would produce.
    """
    from dillylang.operators import (
        DecomposeOperator,
        InvertOperator,
        RotateOperator,
        SynthesizeOperator,
    )
    from dillylang.trace.viewer import render_run_result

    problem = (
        "A team is stuck debating whether to use a relational database or a document "
        "store for their new application. Both sides have valid points and the "
        "discussion is circular."
    )

    refine = pipe(
        DecomposeOperator(),
        parallel(InvertOperator(), RotateOperator()),
        SynthesizeOperator(),
    )

    result = PipelineRunner(budget=Budget(max_llm_calls=7)).run(refine, problem)

    assert result.status in (RunResultStatus.SUCCESS, RunResultStatus.PARTIAL)
    assert isinstance(result.output, Artifact)

    # Collect operator outputs from trace for quality checks
    op_outputs: dict[str, Any] = {}
    for entry in result.trace:
        if entry.event_type == TraceEventType.LLM_CALL and entry.parsed_output:
            op_outputs[entry.operator_name] = entry.parsed_output

    # D-04 quality: decompose should find genuine structure
    decompose_out = op_outputs.get("decompose", {})
    assert len(decompose_out.get("axioms", [])) >= 2, "Problem has at least 2 axioms to extract"
    assert len(decompose_out.get("assumptions", [])) >= 1, "Problem contains hidden assumptions"

    # D-04 quality: rotate should find multiple frames
    rotate_out = op_outputs.get("rotate", {})
    assert len(rotate_out.get("rotations", [])) >= 2, (
        "Problem has multiple frames: technical, team dynamics, product"
    )

    # D-04 quality: invert should identify failure modes
    invert_out = op_outputs.get("invert", {})
    assert len(invert_out.get("failure_modes", [])) >= 1, (
        "Circular debate has clear failure modes (analysis paralysis, premature commitment)"
    )

    # D-04 quality: synthesize should incorporate all upstream artifacts
    synth_data = result.output.data
    assert "proposal" in synth_data
    incorporates = synth_data.get("incorporates", [])
    upstream_ids = {inc.get("source_artifact_id", "") for inc in incorporates}
    # Should reference artifacts from all upstream operators
    assert len(upstream_ids) >= 2, "Synthesize should reference upstream artifact IDs"

    # Tradeoffs should be non-empty (the problem inherently involves tradeoffs)
    assert len(synth_data.get("tradeoffs", [])) >= 1, "DB choice inherently involves tradeoffs"

    # Visual output for manual comparison with lateral-shift
    render_run_result(result, verbose=True)
