"""Tests for analyze meta-skill: pipeline composition, metrics node, and rendering.

Mock-based tests verify the pipeline composes correctly, ComputeMetricsNode
bypasses budget, and the renderer produces typed AnalysisReport from artifacts.
"""

from __future__ import annotations

from typing import Any

import pytest

from dillylang.runner.runner import PipelineRunner
from dillylang.skills.analyze import (
    ComputeMetricsNode,
    _build_analyze_pipeline,
    render_analysis_report,
)
from dillylang.vocab.schemas import (
    AnalysisReport,
    DillylangSkillDescription,
    RecipeMetrics,
)
from dillylang.vocab.types import (
    Artifact,
    ArtifactStatus,
    Budget,
    Context,
    RunResult,
    RunResultStatus,
)


# --- Test helpers ---


def _make_description(
    operators: list[str] | None = None,
    combinators: list[str] | None = None,
    pseudocode: str = "pipe(decompose, synthesize)",
) -> DillylangSkillDescription:
    """Create a minimal DillylangSkillDescription for testing."""
    return DillylangSkillDescription(
        skill_name="test-skill",
        skill_purpose="test purpose",
        activation_contract="/test",
        execution_model="Model C",
        recipe_shape="generative",
        source_contract_entrypoints=["/test"],
        source_contract_inputs=["problem"],
        source_contract_outputs=["analysis"],
        source_contract_control_flow=[],
        dillylang_pseudocode=pseudocode,
        dillylang_operators=operators or ["decompose", "synthesize"],
        dillylang_combinators=combinators or ["pipe"],
        stage_mapping=[],
        residue=[],
        open_questions=[],
        confidence="medium",
    )


# --- Mock evaluate output matching EvaluateOutput schema ---

MOCK_EVALUATE_OUTPUT = {
    "verdict": "partial",
    "evidence": [
        "recipe covers only compositionality axis",
        "no valence or frame operators present",
    ],
    "rationale": "coverage is narrow; recipe would benefit from multi-axis analysis",
    "confidence": "medium",
}


# --- MockLLMOperator (same pattern as test_translate.py) ---


class MockLLMOperator:
    """Mock operator with configurable output for testing."""

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
        artifact = Artifact(
            id=f"{self._name}_{self.call_count - 1}",
            operator=self._name,
            step_index=len(ctx.trace),
            data=self._output_data,
            status=artifact_status,
        )
        ctx.artifacts[artifact.id] = artifact
        return RunResult(
            output=artifact,
            trace=[],
            status=self._status,
        )


# --- Tests ---


class TestComputeMetricsNode:
    """Tests for ComputeMetricsNode as a pipeline step."""

    def test_compute_metrics_node_no_budget_deduction(self) -> None:
        """ComputeMetricsNode does not consume budget (is_combinator=True path)."""
        node = ComputeMetricsNode()
        desc = _make_description()
        artifact = Artifact(
            id="test_input",
            operator="test",
            step_index=0,
            data=desc.model_dump(),
            status=ArtifactStatus.SUCCESS,
        )
        ctx = Context(problem=artifact, budget=Budget(max_llm_calls=7, llm_calls_used=0))

        result = node.run(artifact, ctx)

        assert result.status == RunResultStatus.SUCCESS
        # Budget untouched -- deterministic computation
        assert ctx.budget.llm_calls_used == 0
        assert isinstance(result.output, Artifact)
        assert result.output.data["metrics"]["coverage"] == 1  # decompose+synthesize both touch compositionality
        assert result.output.operator == "compute_metrics"

    def test_compute_metrics_node_is_combinator_flag(self) -> None:
        """ComputeMetricsNode declares is_combinator=True for routing bypass."""
        assert ComputeMetricsNode.is_combinator is True


class TestBuildAnalyzePipeline:
    """Tests for pipeline composition."""

    def test_build_analyze_pipeline_returns_pipe_node(self) -> None:
        """_build_analyze_pipeline returns a combinator (pipe node with is_combinator=True)."""
        pipeline = _build_analyze_pipeline()
        assert getattr(pipeline, "is_combinator", False) is True


class TestRenderAnalysisReport:
    """Tests for the deterministic renderer."""

    def test_render_analysis_report_merges_metrics_and_evaluate(self) -> None:
        """Renderer merges metrics + evaluate evidence into AnalysisReport."""
        metrics = RecipeMetrics(
            coverage=1,
            depth=2,
            cost=2,
            cost_efficiency=0.5,
            depth_efficiency=0.5,
            axes_touched=["compositionality"],
            axes_missing=["valence", "frame", "substrate", "abstraction", "feasibility"],
        )
        # Build RunResult with evaluate artifact
        evaluate_artifact = Artifact(
            id="evaluate_0",
            operator="evaluate",
            step_index=1,
            data=MOCK_EVALUATE_OUTPUT,
            status=ArtifactStatus.SUCCESS,
        )
        result = RunResult(
            output=evaluate_artifact,
            trace=[],
            status=RunResultStatus.SUCCESS,
            artifacts={"evaluate_0": evaluate_artifact},
        )

        report = render_analysis_report(result, "test-skill", metrics)

        assert isinstance(report, AnalysisReport)
        assert report.recipe_name == "test-skill"
        assert report.metrics.coverage == 1
        assert report.structural_verdict == "partial"
        # 5 missing axes + 2 evidence items = 7 improvements
        assert len(report.improvements) >= 5
        assert "coverage=1" in report.summary
        assert report.confidence == "medium"

    def test_render_analysis_report_handles_empty_artifacts(self) -> None:
        """Renderer produces safe defaults when evaluate artifact is missing."""
        metrics = RecipeMetrics(
            coverage=2,
            depth=3,
            cost=3,
            cost_efficiency=0.67,
            depth_efficiency=0.67,
            axes_touched=["compositionality", "valence"],
            axes_missing=["frame", "substrate", "abstraction", "feasibility"],
        )
        result = RunResult(
            output=Artifact(
                id="empty",
                operator="unknown",
                step_index=0,
                data={},
                status=ArtifactStatus.SUCCESS,
            ),
            trace=[],
            status=RunResultStatus.SUCCESS,
            artifacts={},
        )

        report = render_analysis_report(result, "empty-skill", metrics)

        assert isinstance(report, AnalysisReport)
        assert report.structural_verdict == "fail"  # default when missing
        assert report.confidence == "low"  # default when missing
        # Only improvements from missing axes (no evaluate evidence)
        assert len(report.improvements) == 4  # 4 missing axes


class TestAnalyzePipelineIntegration:
    """Integration test with mock evaluate in the pipeline."""

    def test_analyze_pipeline_with_mock_evaluate(self) -> None:
        """Full pipeline runs with ComputeMetricsNode + mock evaluate."""
        from dillylang.combinators import pipe

        mock_evaluate = MockLLMOperator(
            op_name="evaluate",
            output_data=MOCK_EVALUATE_OUTPUT,
        )

        # Build pipeline: compute_metrics -> mock evaluate
        pipeline = pipe(ComputeMetricsNode(), mock_evaluate)

        desc = _make_description()
        input_artifact = Artifact(
            id="analyze_input_0",
            operator="analyze_input",
            step_index=0,
            data=desc.model_dump(),
            status=ArtifactStatus.SUCCESS,
        )

        runner = PipelineRunner(budget=Budget(max_llm_calls=7))
        result = runner.run(pipeline, input_artifact)

        assert result.status == RunResultStatus.SUCCESS
        # Mock evaluate called exactly once
        assert mock_evaluate.call_count == 1
        # Artifacts contain both compute_metrics and evaluate entries
        assert result.artifacts is not None
        artifact_operators = {a.operator for a in result.artifacts.values()}
        assert "compute_metrics" in artifact_operators
        assert "evaluate" in artifact_operators
