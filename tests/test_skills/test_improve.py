"""Tests for improve meta-skill: pipeline composition, dual-input merge, and rendering.

Mock-based tests verify the pipeline composes correctly, dual-input merge
serializes both DillylangSkillDescription and AnalysisReport, and the
renderer produces ImproveOutput with revised description and change log.
"""

from __future__ import annotations

from typing import Any

import pytest

from dillylang.runner.runner import PipelineRunner
from dillylang.skills.improve import (
    ImproveResult,
    _build_improve_pipeline,
    prepare_improve_input,
    render_improve_output,
)
from dillylang.vocab.schemas import (
    AnalysisReport,
    ChangeLogEntry,
    DillylangSkillDescription,
    ImproveOutput,
    RecipeMetrics,
    StructuralImprovement,
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


def _make_analysis_report(
    improvements: list[dict[str, str]] | None = None,
) -> AnalysisReport:
    """Create a minimal AnalysisReport for testing."""
    default_improvements = improvements or [{"cat": "test"}]
    return AnalysisReport(
        recipe_name="test-skill",
        metrics=RecipeMetrics(
            coverage=2,
            depth=2,
            cost=3,
            axes_touched=["compositionality", "frame"],
            axes_missing=["valence", "substrate", "abstraction", "feasibility"],
            cost_efficiency=0.67,
            depth_efficiency=1.0,
        ),
        structural_verdict="partial",
        improvements=[
            StructuralImprovement(
                category="axis_gap",
                description="Missing valence axis",
                rationale="No invert operator",
            )
            for _ in default_improvements
        ],
        summary="test analysis",
        confidence="medium",
    )


# --- MockLLMOperator (same pattern as test_translate.py / test_analyze.py) ---


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


# --- Mock data constants ---

MOCK_DECOMPOSE_OUTPUT = {
    "axioms": [
        {
            "statement": "Add invert for valence axis coverage",
            "justification": "AnalysisReport identifies valence gap",
        },
        {
            "statement": "Remove redundant second decompose",
            "justification": "AnalysisReport flags redundancy",
        },
    ],
    "derivations": [
        {
            "claim": "Adding invert before synthesize covers valence axis",
            "depends_on": ["Add invert for valence axis coverage"],
        },
    ],
    "assumptions": [
        {
            "statement": "invert operator is available in the pantry",
            "load_bearing": True,
            "testable": "check operator registry",
        },
    ],
}

MOCK_SYNTHESIZE_OUTPUT = {
    # SynthesizeOutput base fields (ADR-006 integration contract)
    "proposal": {
        "statement": "pipe(decompose, invert, synthesize)",
        "rationale": "adds valence axis via invert, removes redundant second decompose",
    },
    "incorporates": [
        {"source_artifact_id": "decompose_0", "contribution": "atomic change breakdown"},
    ],
    "tradeoffs": [
        {"gained": "valence axis coverage", "given_up": "slightly higher cost"},
    ],
    "open_questions": ["should rotate be added for frame axis?"],
    "conflicts_addressed": [],
    "confidence": "high",
    # ImproveSynthesizeOutput extension fields
    "revised_recipe": "pipe(decompose, invert, synthesize)",
    "revised_operators": ["decompose", "invert", "synthesize"],
    "revised_combinators": ["pipe"],
    "change_log": [
        {
            "field_changed": "dillylang_operators",
            "old_value": "decompose, synthesize",
            "new_value": "decompose, invert, synthesize",
            "rationale": "adds valence axis coverage",
            "improvement_ref": "axis_gap: Missing valence axis",
        },
        {
            "field_changed": "dillylang_pseudocode",
            "old_value": "pipe(decompose, synthesize)",
            "new_value": "pipe(decompose, invert, synthesize)",
            "rationale": "restructured pipeline to include invert before synthesize",
            "improvement_ref": "axis_gap: Missing valence axis",
        },
    ],
}


# --- Tests ---


class TestPrepareImproveInput:
    """Tests for the dual-input merge function."""

    def test_prepare_creates_artifact_with_both_inputs(self) -> None:
        """Artifact.data contains both recipe_description and analysis_report keys."""
        desc = _make_description()
        report = _make_analysis_report()

        artifact = prepare_improve_input(desc, report)

        assert "recipe_description" in artifact.data
        assert "analysis_report" in artifact.data
        # Both are dicts (serialized from Pydantic models)
        assert isinstance(artifact.data["recipe_description"], dict)
        assert isinstance(artifact.data["analysis_report"], dict)
        # Verify round-trip: data contains expected fields
        assert artifact.data["recipe_description"]["skill_name"] == "test-skill"
        assert artifact.data["analysis_report"]["recipe_name"] == "test-skill"

    def test_prepare_artifact_metadata(self) -> None:
        """Artifact has correct id, operator, and status."""
        desc = _make_description()
        report = _make_analysis_report()

        artifact = prepare_improve_input(desc, report)

        assert artifact.id == "improve_input_0"
        assert artifact.operator == "improve_input"
        assert artifact.status == ArtifactStatus.SUCCESS


class TestBuildImprovePipeline:
    """Tests for pipeline composition."""

    def test_build_pipeline_returns_pipe_node(self) -> None:
        """_build_improve_pipeline returns a combinator (pipe node with is_combinator=True)."""
        pipeline = _build_improve_pipeline()
        assert getattr(pipeline, "is_combinator", False) is True


class TestImprovePipelineWithMocks:
    """Integration tests with mock operators in the pipeline."""

    def test_pipeline_calls_decompose_and_synthesize(self) -> None:
        """Full pipeline with 2 mocks: both called exactly once, result is SUCCESS."""
        from dillylang.combinators import pipe

        mock_decompose = MockLLMOperator("decompose", MOCK_DECOMPOSE_OUTPUT)
        mock_synthesize = MockLLMOperator("synthesize", MOCK_SYNTHESIZE_OUTPUT)

        pipeline = pipe(mock_decompose, mock_synthesize)

        desc = _make_description()
        report = _make_analysis_report()
        input_artifact = prepare_improve_input(desc, report)

        runner = PipelineRunner(budget=Budget(max_llm_calls=5))
        result = runner.run(pipeline, input_artifact)

        assert result.status == RunResultStatus.SUCCESS
        assert mock_decompose.call_count == 1
        assert mock_synthesize.call_count == 1

    def test_pipeline_artifacts_contain_both_operators(self) -> None:
        """Result artifacts contain both decompose and synthesize entries."""
        from dillylang.combinators import pipe

        mock_decompose = MockLLMOperator("decompose", MOCK_DECOMPOSE_OUTPUT)
        mock_synthesize = MockLLMOperator("synthesize", MOCK_SYNTHESIZE_OUTPUT)

        pipeline = pipe(mock_decompose, mock_synthesize)

        desc = _make_description()
        report = _make_analysis_report()
        input_artifact = prepare_improve_input(desc, report)

        runner = PipelineRunner(budget=Budget(max_llm_calls=5))
        result = runner.run(pipeline, input_artifact)

        assert result.artifacts is not None
        artifact_operators = {a.operator for a in result.artifacts.values()}
        assert "decompose" in artifact_operators
        assert "synthesize" in artifact_operators


class TestRenderImproveOutput:
    """Tests for the deterministic renderer."""

    def _make_synthesize_result(
        self,
        synthesize_data: dict[str, Any] | None = None,
    ) -> tuple[RunResult, DillylangSkillDescription]:
        """Build a mock RunResult with synthesize artifact and an original description."""
        data = synthesize_data or MOCK_SYNTHESIZE_OUTPUT
        synthesize_artifact = Artifact(
            id="synthesize_0",
            operator="synthesize",
            step_index=1,
            data=data,
            status=ArtifactStatus.SUCCESS,
        )
        result = RunResult(
            output=synthesize_artifact,
            trace=[],
            status=RunResultStatus.SUCCESS,
            artifacts={"synthesize_0": synthesize_artifact},
        )
        desc = _make_description()
        return result, desc

    def test_render_produces_improve_output(self) -> None:
        """Renderer produces ImproveOutput with revised DillylangSkillDescription."""
        result, desc = self._make_synthesize_result()

        output = render_improve_output(result, desc)

        assert isinstance(output, ImproveOutput)
        assert isinstance(output.revised_description, DillylangSkillDescription)
        assert len(output.change_log) > 0

    def test_render_preserves_original_fields(self) -> None:
        """Unchanged fields carry over from original description."""
        result, desc = self._make_synthesize_result()

        output = render_improve_output(result, desc)

        # These fields should NOT be changed by improve
        assert output.revised_description.activation_contract == desc.activation_contract
        assert output.revised_description.execution_model == desc.execution_model
        assert output.revised_description.recipe_shape == desc.recipe_shape
        assert output.revised_description.skill_name == desc.skill_name
        assert output.revised_description.skill_purpose == desc.skill_purpose
        assert output.revised_description.source_contract_entrypoints == desc.source_contract_entrypoints
        assert output.revised_description.source_contract_inputs == desc.source_contract_inputs
        assert output.revised_description.source_contract_outputs == desc.source_contract_outputs
        assert output.revised_description.source_contract_control_flow == desc.source_contract_control_flow

    def test_render_updates_recipe_fields(self) -> None:
        """Revised recipe fields come from synthesize output, not original."""
        result, desc = self._make_synthesize_result()

        output = render_improve_output(result, desc)

        # These fields SHOULD be updated from synthesize
        assert output.revised_description.dillylang_pseudocode == "pipe(decompose, invert, synthesize)"
        assert "invert" in output.revised_description.dillylang_operators
        assert output.revised_description.dillylang_combinators == ["pipe"]

    def test_render_handles_missing_synthesize(self) -> None:
        """Empty artifacts -> renderer uses original description (no crash)."""
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
        desc = _make_description()

        output = render_improve_output(result, desc)

        assert isinstance(output, ImproveOutput)
        # Falls back to original description values
        assert output.revised_description.dillylang_pseudocode == desc.dillylang_pseudocode
        assert output.revised_description.dillylang_operators == desc.dillylang_operators
        assert output.change_log == []

    def test_change_log_has_improvement_refs(self) -> None:
        """Each ChangeLogEntry has a non-empty improvement_ref."""
        result, desc = self._make_synthesize_result()

        output = render_improve_output(result, desc)

        assert len(output.change_log) >= 1
        for entry in output.change_log:
            assert isinstance(entry, ChangeLogEntry)
            assert entry.improvement_ref != ""
            assert "axis_gap" in entry.improvement_ref
