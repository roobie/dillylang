"""Tests for design meta-skill: pipeline composition and rendering.

Mock-based tests verify the pipeline composes correctly and the renderer
produces typed RecipeDefinition from artifact collections. Follows the
same pattern as test_translate.py.
"""

from __future__ import annotations

from typing import Any

import pytest

from dillylang.runner.runner import PipelineRunner
from dillylang.skills.design import (
    DesignResult,
    _build_design_pipeline,
    _find_artifact_data,
    render_recipe_definition,
)
from dillylang.vocab.schemas import (
    DesignSynthesizeOutput,
    RecipeDefinition,
    RecipeStage,
)
from dillylang.vocab.types import (
    Artifact,
    ArtifactStatus,
    Budget,
    Context,
    RunResult,
    RunResultStatus,
)


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
        {
            "statement": "The decision must account for migration cost",
            "justification": "switching auth systems has non-zero cost",
        },
        {
            "statement": "The strategy must address three user segments",
            "justification": "different segments have different auth requirements",
        },
    ],
    "derivations": [
        {
            "claim": "migration cost implies inversion to surface failure modes",
            "depends_on": ["The decision must account for migration cost"],
        },
    ],
    "assumptions": [
        {
            "statement": "current auth system is functional but outdated",
            "load_bearing": True,
            "testable": "check system age and vulnerability reports",
        },
    ],
}

MOCK_CLASSIFY_OUTPUT = {
    "classifications": [
        {
            "taxonomy": "problem_type",
            "label": "decision",
            "rationale": "choosing between rewrite vs patch is a decision problem",
            "confidence": "high",
        },
        {
            "taxonomy": "recipe_shape",
            "label": "evaluative",
            "rationale": "gather evidence then judge, not diverge-curate-converge",
            "confidence": "medium",
        },
    ],
}

MOCK_ROTATE_OUTPUT = {
    "original_axis": "goal requirements",
    "rotations": [
        {
            "new_axis": "decompose",
            "rotation_kind": "axis_change",
            "restated_problem": "break the auth decision into load-bearing components",
            "what_becomes_visible": ["structural dependencies", "migration boundaries"],
            "what_recedes": ["user experience concerns"],
        },
        {
            "new_axis": "invert",
            "rotation_kind": "axis_change",
            "restated_problem": "what guarantees the rewrite fails?",
            "what_becomes_visible": ["failure modes", "hidden assumptions"],
            "what_recedes": ["success scenarios"],
        },
    ],
}

MOCK_EVALUATE_OUTPUT = {
    "verdict": "fail",
    "evidence": ["No existing recipe covers decision + multi-segment analysis"],
    "rationale": "refine lacks the multi-segment dimension; wide_pass adds analogize which is not needed here",
    "confidence": "high",
}

MOCK_SYNTHESIZE_OUTPUT = {
    "proposal": {
        "statement": "pipe(decompose, parallel(invert, rotate), synthesize)",
        "rationale": "decision problem benefits from inversion and reframing",
    },
    "incorporates": [
        {"source_artifact_id": "decompose_0", "contribution": "requirements structure"},
        {"source_artifact_id": "classify_0", "contribution": "problem type classification"},
        {"source_artifact_id": "rotate_0", "contribution": "operator mapping"},
        {"source_artifact_id": "evaluate_0", "contribution": "existing recipe assessment"},
    ],
    "tradeoffs": [
        {"gained": "focused decision analysis", "given_up": "cross-domain analogies"},
    ],
    "open_questions": ["should analogize be added for cross-industry comparison?"],
    "conflicts_addressed": [],
    "confidence": "high",
    "recipe_structure": {
        "name": "auth_rewrite_decision",
        "purpose": "Evaluate rewrite-vs-patch tradeoff for authentication system",
        "definition": "pipe(decompose, parallel(invert, rotate), synthesize)",
        "existing_recipe": None,
        "stages": [
            {
                "operator": "decompose",
                "role": "Extract requirements, constraints, risk factors",
                "bindings": {},
                "axis": "compositionality",
            },
            {
                "operator": "invert",
                "role": "Surface failure modes for both paths",
                "bindings": {"question": "What guarantees each path fails?"},
                "axis": "valence",
            },
            {
                "operator": "rotate",
                "role": "Reframe from engineering to business/ops perspective",
                "bindings": {"target_frame": "organizational risk"},
                "axis": "frame",
            },
        ],
        "cost": 4,
        "depth": 3,
        "axes": ["compositionality", "valence", "frame"],
    },
}


# --- TestBuildDesignPipeline ---


class TestBuildDesignPipeline:
    """Tests for pipeline composition."""

    def test_build_design_pipeline_returns_pipe_node(self):
        """Pipeline composes without error, returns a combinator node."""
        pipeline = _build_design_pipeline()
        assert hasattr(pipeline, "is_combinator")
        assert pipeline.is_combinator is True
        assert hasattr(pipeline, "name")

    def test_design_pipeline_uses_design_synthesize_output(self):
        """The pipeline's synthesize operator uses DesignSynthesizeOutput."""
        pipeline = _build_design_pipeline()
        # Walk the pipeline tree to find the SynthesizeOperator
        # PipeOperator stores children in _operators
        operators = getattr(pipeline, "_operators", ())
        assert len(operators) > 0, "Pipeline should have operators"
        # The last operator should be the synthesize operator
        last_op = operators[-1]
        # SynthesizeOperator stores its output model in _output_model
        if hasattr(last_op, "_output_model"):
            assert issubclass(last_op._output_model, DesignSynthesizeOutput)


# --- TestDesignPipelineWithMocks ---


class TestDesignPipelineWithMocks:
    """Tests for full pipeline execution with mock operators."""

    def test_design_pipeline_calls_all_five_operators(self):
        """Create 5 mocks, compose into design topology, verify each called once."""
        from dillylang.combinators import parallel, pipe

        mock_decompose = MockLLMOperator("decompose", MOCK_DECOMPOSE_OUTPUT)
        mock_classify = MockLLMOperator("classify", MOCK_CLASSIFY_OUTPUT)
        mock_rotate = MockLLMOperator("rotate", MOCK_ROTATE_OUTPUT)
        mock_evaluate = MockLLMOperator("evaluate", MOCK_EVALUATE_OUTPUT)
        mock_synthesize = MockLLMOperator("synthesize", MOCK_SYNTHESIZE_OUTPUT)

        # Design topology: decompose -> parallel(classify, rotate, evaluate) -> synthesize
        pipeline = pipe(
            mock_decompose,
            parallel(mock_classify, mock_rotate, mock_evaluate),
            mock_synthesize,
        )

        input_artifact = Artifact(
            id="design_input_0",
            operator="design_input",
            step_index=0,
            data={"goal": "Should we rewrite our auth system?"},
            status=ArtifactStatus.SUCCESS,
        )

        runner = PipelineRunner(budget=Budget(max_llm_calls=7))
        result = runner.run(pipeline, input_artifact)

        assert result.status == RunResultStatus.SUCCESS
        # All 5 operators called exactly once
        assert mock_decompose.call_count == 1
        assert mock_classify.call_count == 1
        assert mock_rotate.call_count == 1
        assert mock_evaluate.call_count == 1
        assert mock_synthesize.call_count == 1

    def test_design_pipeline_artifacts_contain_all_operators(self):
        """Result artifacts should contain keys for all 5 operators."""
        from dillylang.combinators import parallel, pipe

        mock_decompose = MockLLMOperator("decompose", MOCK_DECOMPOSE_OUTPUT)
        mock_classify = MockLLMOperator("classify", MOCK_CLASSIFY_OUTPUT)
        mock_rotate = MockLLMOperator("rotate", MOCK_ROTATE_OUTPUT)
        mock_evaluate = MockLLMOperator("evaluate", MOCK_EVALUATE_OUTPUT)
        mock_synthesize = MockLLMOperator("synthesize", MOCK_SYNTHESIZE_OUTPUT)

        pipeline = pipe(
            mock_decompose,
            parallel(mock_classify, mock_rotate, mock_evaluate),
            mock_synthesize,
        )

        input_artifact = Artifact(
            id="design_input_0",
            operator="design_input",
            step_index=0,
            data={"goal": "Test goal"},
            status=ArtifactStatus.SUCCESS,
        )

        runner = PipelineRunner(budget=Budget(max_llm_calls=7))
        result = runner.run(pipeline, input_artifact)

        assert result.artifacts is not None
        operator_names = {a.operator for a in result.artifacts.values()}
        assert "decompose" in operator_names
        assert "classify" in operator_names
        assert "rotate" in operator_names
        assert "evaluate" in operator_names
        assert "synthesize" in operator_names


# --- TestRenderRecipeDefinition ---


class TestRenderRecipeDefinition:
    """Tests for the deterministic renderer."""

    def _build_mock_run_result(self) -> RunResult:
        """Build a RunResult with all 5 operator artifacts populated."""
        artifacts = {
            "decompose_0": Artifact(
                id="decompose_0", operator="decompose", step_index=0,
                data=MOCK_DECOMPOSE_OUTPUT, status=ArtifactStatus.SUCCESS,
            ),
            "classify_1": Artifact(
                id="classify_1", operator="classify", step_index=1,
                data=MOCK_CLASSIFY_OUTPUT, status=ArtifactStatus.SUCCESS,
            ),
            "rotate_2": Artifact(
                id="rotate_2", operator="rotate", step_index=2,
                data=MOCK_ROTATE_OUTPUT, status=ArtifactStatus.SUCCESS,
            ),
            "evaluate_3": Artifact(
                id="evaluate_3", operator="evaluate", step_index=3,
                data=MOCK_EVALUATE_OUTPUT, status=ArtifactStatus.SUCCESS,
            ),
            "synthesize_4": Artifact(
                id="synthesize_4", operator="synthesize", step_index=4,
                data=MOCK_SYNTHESIZE_OUTPUT, status=ArtifactStatus.SUCCESS,
            ),
        }
        return RunResult(
            output=artifacts["synthesize_4"],
            trace=[],
            status=RunResultStatus.SUCCESS,
            artifacts=artifacts,
        )

    def test_render_produces_recipe_definition(self):
        """Renderer produces RecipeDefinition with correct field values."""
        result = self._build_mock_run_result()
        definition = render_recipe_definition(result)

        assert isinstance(definition, RecipeDefinition)
        assert definition.recipe_name == "auth_rewrite_decision"
        assert definition.recipe_purpose == "Evaluate rewrite-vs-patch tradeoff for authentication system"
        assert definition.recipe_shape == "evaluative"
        assert definition.pipeline_definition == "pipe(decompose, parallel(invert, rotate), synthesize)"
        assert len(definition.pipeline_stages) == 3
        assert definition.metrics_cost == 4
        assert definition.metrics_depth == 3
        assert definition.confidence == "high"

    def test_render_handles_empty_artifacts(self):
        """Renderer returns RecipeDefinition with safe defaults when artifacts empty."""
        result = RunResult(
            output=Artifact(
                id="empty_0", operator="empty", step_index=0,
                data={}, status=ArtifactStatus.SUCCESS,
            ),
            trace=[],
            status=RunResultStatus.SUCCESS,
            artifacts={},
        )

        definition = render_recipe_definition(result)

        assert isinstance(definition, RecipeDefinition)
        assert definition.recipe_name == "unnamed"
        assert definition.recipe_shape == "unknown"
        assert definition.pipeline_stages == []
        assert definition.metrics_cost == 0
        assert definition.metrics_efficiency == 0.0
        assert definition.metrics_axes == []
        assert definition.existing_recipe_fit_verdict == "fail"

    def test_render_extracts_classify_labels(self):
        """Renderer extracts recipe_shape from classify taxonomy and shape_choice rationale."""
        result = self._build_mock_run_result()
        definition = render_recipe_definition(result)

        # recipe_shape comes from classify "recipe_shape" taxonomy
        assert definition.recipe_shape == "evaluative"
        # design_rationale_shape_choice comes from classify "problem_type" rationale
        assert definition.design_rationale_shape_choice == (
            "choosing between rewrite vs patch is a decision problem"
        )

    def test_render_maps_rotate_to_operator_selection(self):
        """Renderer maps each rotate rotation to an operator_selection entry."""
        result = self._build_mock_run_result()
        definition = render_recipe_definition(result)

        # Two rotations -> two operator_selection entries
        assert len(definition.design_rationale_operator_selection) == 2
        ops = definition.design_rationale_operator_selection
        assert ops[0]["operator"] == "decompose"
        assert ops[0]["included"] is True
        assert ops[1]["operator"] == "invert"
        assert ops[1]["included"] is True

    def test_render_reads_existing_recipe_fit(self):
        """Renderer reads existing_recipe_fit from evaluate artifact."""
        result = self._build_mock_run_result()
        definition = render_recipe_definition(result)

        assert definition.existing_recipe_fit_verdict == "fail"
        # When verdict is fail, closest may still be populated from evidence
        assert definition.existing_recipe_fit_delta is not None

    def test_render_computes_coverage_and_efficiency(self):
        """coverage = len(axes), efficiency = coverage/cost."""
        result = self._build_mock_run_result()
        definition = render_recipe_definition(result)

        assert definition.metrics_coverage == 3  # compositionality, valence, frame
        assert definition.metrics_axes == ["compositionality", "valence", "frame"]
        # efficiency = 3 / 4 = 0.75
        assert definition.metrics_efficiency == pytest.approx(0.75)

    def test_render_extracts_caveats_from_open_questions(self):
        """Renderer maps synthesize open_questions to caveats."""
        result = self._build_mock_run_result()
        definition = render_recipe_definition(result)

        assert len(definition.caveats) == 1
        assert "analogize" in definition.caveats[0]
