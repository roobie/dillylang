"""Tests for translate meta-skill: pipeline composition and rendering.

Mock-based tests verify the pipeline composes correctly and the renderer
produces typed DillylangSkillDescription from artifact collections.
"""

from __future__ import annotations

from typing import Any

import pytest

from dillylang.runner.runner import PipelineRunner
from dillylang.skills.translate import (
    _build_translate_pipeline,
    _find_artifact_data,
    render_dillylang_skill_description,
    translate,
)
from dillylang.vocab.schemas import DillylangSkillDescription
from dillylang.vocab.types import (
    Artifact,
    ArtifactStatus,
    Budget,
    Context,
    RunResult,
    RunResultStatus,
)


# --- MockLLMOperator (same pattern as test_refine_pipeline) ---


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
            "statement": "skill activates on /lateral-shift command",
            "justification": "explicit entrypoint",
        },
        {
            "statement": "reads current file context as input",
            "justification": "required for analysis",
        },
    ],
    "derivations": [
        {
            "claim": "multi-perspective analysis requires parallel execution",
            "depends_on": ["reads current file context as input"],
        },
        {
            "claim": "produces rotated perspectives as output",
            "depends_on": ["skill activates on /lateral-shift command"],
        },
    ],
    "assumptions": [
        {
            "statement": "Claude Code runtime available",
            "load_bearing": True,
            "testable": "check runtime version",
        },
    ],
}

MOCK_ROTATE_OUTPUT = {
    "original_axis": "agent skill implementation",
    "rotations": [
        {
            "new_axis": "Dillylang vocabulary",
            "rotation_kind": "axis_change",
            "restated_problem": "express lateral-shift as decompose then synthesize operators",
            "what_becomes_visible": ["operator composition", "axis coverage"],
            "what_recedes": ["tool invocations", "runtime state"],
        },
    ],
}

MOCK_CLASSIFY_OUTPUT = {
    "classifications": [
        {
            "taxonomy": "execution_model",
            "label": "Model C",
            "rationale": "in-session execution",
            "confidence": "high",
        },
        {
            "taxonomy": "recipe_shape",
            "label": "generative",
            "rationale": "diverge-curate-converge pattern",
            "confidence": "high",
        },
    ],
}

MOCK_EVALUATE_OUTPUT = {
    "verdict": "partial",
    "evidence": ["tool use not expressible", "loop pattern not in vocabulary"],
    "rationale": "core thinking moves map well, but runtime behaviors are residue",
    "confidence": "medium",
}

MOCK_SYNTHESIZE_OUTPUT = {
    "proposal": {
        "statement": "pipe(decompose, parallel(rotate, invert), synthesize)",
        "rationale": "covers compositionality and frame axes",
    },
    "incorporates": [
        {"source_artifact_id": "decompose_0", "contribution": "structural breakdown"},
        {"source_artifact_id": "rotate_0", "contribution": "vocabulary mapping"},
        {"source_artifact_id": "classify_0", "contribution": "execution model classification"},
        {"source_artifact_id": "evaluate_0", "contribution": "vocabulary fit assessment"},
    ],
    "tradeoffs": [{"gained": "explicit composition", "given_up": "runtime tool access"}],
    "open_questions": ["should analogize be added for cross-domain insights?"],
    "conflicts_addressed": [],
    "confidence": "medium",
}


# --- Tests ---


def test_build_translate_pipeline_returns_pipe_node():
    """Pipeline composes without error, returns a combinator node."""
    pipeline = _build_translate_pipeline()
    # PipeNode from pipe() has is_combinator and name
    assert hasattr(pipeline, "is_combinator")
    assert pipeline.is_combinator is True
    assert hasattr(pipeline, "name")


def test_translate_pipeline_with_mocks():
    """Full pipeline execution with mock operators verifies composition."""
    from dillylang.combinators import parallel, pipe

    mock_decompose = MockLLMOperator("decompose", MOCK_DECOMPOSE_OUTPUT)
    mock_rotate = MockLLMOperator("rotate", MOCK_ROTATE_OUTPUT)
    mock_classify = MockLLMOperator("classify", MOCK_CLASSIFY_OUTPUT)
    mock_evaluate = MockLLMOperator("evaluate", MOCK_EVALUATE_OUTPUT)
    mock_synthesize = MockLLMOperator("synthesize", MOCK_SYNTHESIZE_OUTPUT)

    pipeline = pipe(
        parallel(mock_decompose, mock_rotate, mock_classify, mock_evaluate),
        mock_synthesize,
    )

    input_artifact = Artifact(
        id="input_0",
        operator="ingest_skill_directory",
        step_index=0,
        data={"path": "/test/skill", "files": [], "ingestion_status": "success"},
        status=ArtifactStatus.SUCCESS,
    )

    runner = PipelineRunner(budget=Budget(max_llm_calls=7))
    result = runner.run(pipeline, input_artifact)

    assert result.status == RunResultStatus.SUCCESS
    # All 5 mock operators called exactly once
    assert mock_decompose.call_count == 1
    assert mock_rotate.call_count == 1
    assert mock_classify.call_count == 1
    assert mock_evaluate.call_count == 1
    assert mock_synthesize.call_count == 1
    # Artifacts populated by runner
    assert result.artifacts is not None
    # Trace has entries
    assert len(result.trace) > 0


def test_render_dillylang_skill_description():
    """Renderer projects artifact collection into typed DillylangSkillDescription."""
    # Build artifacts dict keyed by "{op_name}_{step_index}"
    artifacts = {
        "decompose_0": Artifact(
            id="decompose_0", operator="decompose", step_index=0,
            data=MOCK_DECOMPOSE_OUTPUT, status=ArtifactStatus.SUCCESS,
        ),
        "rotate_1": Artifact(
            id="rotate_1", operator="rotate", step_index=1,
            data=MOCK_ROTATE_OUTPUT, status=ArtifactStatus.SUCCESS,
        ),
        "classify_2": Artifact(
            id="classify_2", operator="classify", step_index=2,
            data=MOCK_CLASSIFY_OUTPUT, status=ArtifactStatus.SUCCESS,
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

    mock_result = RunResult(
        output=artifacts["synthesize_4"],
        trace=[],
        status=RunResultStatus.SUCCESS,
        artifacts=artifacts,
    )

    source_artifact = Artifact(
        id="ingest_0",
        operator="ingest_skill_directory",
        step_index=0,
        data={
            "path": "/test/skill",
            "entrypoints": [{"command": "/lateral-shift", "declared_in": "SKILL.md"}],
            "detected_control_flow": ["branch", "parallel"],
            "files": [],
            "ingestion_status": "success",
        },
        status=ArtifactStatus.SUCCESS,
    )

    desc = render_dillylang_skill_description(mock_result, "test-skill", source_artifact)

    assert isinstance(desc, DillylangSkillDescription)
    assert desc.skill_name == "test-skill"
    assert desc.execution_model == "Model C"
    assert desc.recipe_shape == "generative"
    assert desc.dillylang_pseudocode != ""
    assert len(desc.open_questions) > 0
    assert desc.confidence == "medium"
    # Residue populated from evaluate partial verdict
    assert len(desc.residue) > 0
    # Stage mapping from rotate
    assert len(desc.stage_mapping) > 0
    # Entrypoints from source
    assert "/lateral-shift" in desc.source_contract_entrypoints


def test_render_handles_missing_artifacts():
    """Renderer returns DillylangSkillDescription with defaults when artifacts empty."""
    mock_result = RunResult(
        output=Artifact(
            id="empty_0", operator="empty", step_index=0,
            data={}, status=ArtifactStatus.SUCCESS,
        ),
        trace=[],
        status=RunResultStatus.SUCCESS,
        artifacts={},
    )

    desc = render_dillylang_skill_description(mock_result, "empty-skill")

    assert isinstance(desc, DillylangSkillDescription)
    assert desc.skill_name == "empty-skill"
    assert desc.execution_model == "unknown"
    assert desc.recipe_shape == "unknown"
    assert desc.dillylang_pseudocode == ""
    assert desc.open_questions == []
    assert desc.residue == []
    assert desc.stage_mapping == []


def test_find_artifact_data_by_prefix():
    """_find_artifact_data locates artifacts by operator prefix."""
    artifacts = {
        "classify_2": Artifact(
            id="classify_2", operator="classify", step_index=2,
            data={"classifications": [{"taxonomy": "x", "label": "y"}]},
            status=ArtifactStatus.SUCCESS,
        ),
        "decompose_0": Artifact(
            id="decompose_0", operator="decompose", step_index=0,
            data={"axioms": []},
            status=ArtifactStatus.SUCCESS,
        ),
    }

    result = _find_artifact_data(artifacts, "classify")
    assert result == {"classifications": [{"taxonomy": "x", "label": "y"}]}

    result = _find_artifact_data(artifacts, "decompose")
    assert result == {"axioms": []}

    # Missing prefix returns empty dict
    result = _find_artifact_data(artifacts, "synthesize")
    assert result == {}


def test_translate_raises_on_failed_ingestion(tmp_path):
    """translate raises ValueError when SKILL.md is missing."""
    # tmp_path is empty -- no SKILL.md
    with pytest.raises(ValueError, match="Skill ingestion failed"):
        translate(tmp_path)
