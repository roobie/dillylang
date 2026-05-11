"""Tests for SynthesizeOperator.

Unit tests verify prompt content, protocol conformance, and input handling
without LLM access. Integration tests require a configured LLM.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from dillylang.operators.synthesize import SynthesizeOperator
from dillylang.vocab.protocol import OperatorProtocol
from dillylang.vocab.schemas import SynthesizeOutput
from dillylang.vocab.types import Artifact, ArtifactStatus


def test_synthesize_operator_name() -> None:
    """SynthesizeOperator has the correct name."""
    op = SynthesizeOperator()
    assert op.name == "synthesize"


def test_synthesize_implements_protocol() -> None:
    """SynthesizeOperator satisfies OperatorProtocol."""
    op = SynthesizeOperator()
    assert isinstance(op, OperatorProtocol)


def test_synthesize_docstring_contains_anti_averaging() -> None:
    """The synthesize signature's docstring contains the anti-averaging instruction."""
    op = SynthesizeOperator()
    doc = op._signature.__doc__
    assert "weighted average" in doc
    assert "Silent dropping is forbidden" in doc
    assert "summarized" in doc


def test_synthesize_uses_upstream_artifacts_data_field() -> None:
    """Synthesize uses 'upstream_artifacts' as its data field, not 'problem_text'."""
    op = SynthesizeOperator()
    input_fields = list(op._signature.input_fields.keys())
    assert "upstream_artifacts" in input_fields
    assert "problem_text" not in input_fields


def test_synthesize_has_all_six_base_output_fields() -> None:
    """Synthesize signature has all 6 base integration fields from ADR-006."""
    op = SynthesizeOperator()
    output_fields = list(op._signature.output_fields.keys())
    assert "proposal" in output_fields
    assert "incorporates" in output_fields
    assert "tradeoffs" in output_fields
    assert "open_questions" in output_fields
    assert "conflicts_addressed" in output_fields
    assert "confidence" in output_fields


def test_synthesize_serialize_artifacts() -> None:
    """_serialize_artifacts formats each artifact with id, operator, and data."""
    op = SynthesizeOperator()
    artifacts = [
        Artifact(
            id="invert_0",
            operator="invert",
            step_index=0,
            data={"anti_goals": ["rush to production"]},
            status=ArtifactStatus.SUCCESS,
        ),
        Artifact(
            id="rotate_1",
            operator="rotate",
            step_index=1,
            data={"original_axis": "engineering"},
            status=ArtifactStatus.SUCCESS,
        ),
    ]

    text = op._serialize_artifacts(artifacts)
    assert "Artifact 'invert_0' (invert):" in text
    assert "Artifact 'rotate_1' (rotate):" in text
    assert "rush to production" in text
    assert "engineering" in text


def test_synthesize_no_steering_params() -> None:
    """Synthesize has no steering parameters in v0 -- only the data field."""
    op = SynthesizeOperator()
    input_fields = list(op._signature.input_fields.keys())
    # Only the data channel, no steering params
    assert input_fields == ["upstream_artifacts"]


# --- Synthesize extensibility tests (OPS-09 / ADR-006) ---


def test_synthesize_default_output_model() -> None:
    """Default constructor uses SynthesizeOutput."""
    op = SynthesizeOperator()
    assert op._output_model is SynthesizeOutput


def test_synthesize_extended_output_model() -> None:
    """Extended model adds fields while preserving base."""

    class ExtendedSynthesizeOutput(SynthesizeOutput):
        recipe_structure: str = Field(default="", description="typed pipeline definition")

    op = SynthesizeOperator(output_model=ExtendedSynthesizeOutput)
    assert op._output_model is ExtendedSynthesizeOutput
    output_fields = list(op._signature.output_fields.keys())
    # Base fields present
    assert "proposal" in output_fields
    assert "incorporates" in output_fields
    assert "confidence" in output_fields
    # Extension field present
    assert "recipe_structure" in output_fields


def test_synthesize_rejects_non_subclass() -> None:
    """ADR-006 Rule 1: base fields always required."""

    class UnrelatedModel(BaseModel):
        foo: str = "bar"

    with pytest.raises(TypeError, match="subclass of SynthesizeOutput"):
        SynthesizeOperator(output_model=UnrelatedModel)


def test_synthesize_name_unchanged_with_extension() -> None:
    """Name stays 'synthesize' regardless of output model."""

    class ExtendedSynthesizeOutput(SynthesizeOutput):
        extra: str = Field(default="", description="extra field")

    op = SynthesizeOperator(output_model=ExtendedSynthesizeOutput)
    assert op.name == "synthesize"


def test_synthesize_rejects_base_field_shadowing() -> None:
    """M4 / ADR-006 Rule 2: extensions must not shadow base field type annotations.

    A subclass that overrides a base field's type violates the additive-only rule.
    """

    class ShadowingModel(SynthesizeOutput):
        # Override 'confidence' from NormalizedConfidence to plain str
        confidence: str = "high"  # type: ignore[assignment]

    with pytest.raises(TypeError, match="shadows"):
        SynthesizeOperator(output_model=ShadowingModel)


def test_synthesize_accepts_subclass_that_does_not_shadow() -> None:
    """A well-behaved subclass that only adds new fields passes validation."""

    class GoodExtension(SynthesizeOutput):
        skill_description: str = Field(default="", description="skill-specific payload")
        recipe_stages: list[str] = Field(default_factory=list, description="pipeline stages")

    op = SynthesizeOperator(output_model=GoodExtension)
    assert op._output_model is GoodExtension
    output_fields = list(op._signature.output_fields.keys())
    assert "skill_description" in output_fields
    assert "recipe_stages" in output_fields
    # Base fields still present
    assert "proposal" in output_fields
    assert "conflicts_addressed" in output_fields


@pytest.mark.integration
def test_synthesize_end_to_end(sample_context):
    """Integration: run synthesize on two sample artifacts with LLM.

    Requires: --run-integration flag and configured LLM.
    """
    from dillylang.vocab.types import RunResultStatus

    artifacts = [
        Artifact(
            id="invert_0",
            operator="invert",
            step_index=0,
            data={
                "anti_goals": ["ship without testing"],
                "failure_modes": [
                    {
                        "mode": "data loss",
                        "mechanism": "no backup before migration",
                        "likelihood": "medium",
                        "severity": "fatal",
                        "preventable_by": "automated backup",
                    }
                ],
                "near_misses": ["partial rollback"],
            },
            status=ArtifactStatus.SUCCESS,
        ),
        Artifact(
            id="rotate_1",
            operator="rotate",
            step_index=1,
            data={
                "original_axis": "engineering feasibility",
                "rotations": [
                    {
                        "new_axis": "user impact",
                        "rotation_kind": "viewpoint_change",
                        "restated_problem": "How does this affect users?",
                        "what_becomes_visible": ["UX degradation risk"],
                        "what_recedes": ["implementation cost"],
                    }
                ],
            },
            status=ArtifactStatus.SUCCESS,
        ),
    ]

    op = SynthesizeOperator()
    result = op.run(artifacts, sample_context)

    assert result.status == RunResultStatus.SUCCESS
    assert result.trace == []
    assert result.call_metadata is not None

    artifact = result.output
    assert artifact.operator == "synthesize"
    assert "proposal" in artifact.data
    assert "incorporates" in artifact.data
    assert "tradeoffs" in artifact.data
    assert "open_questions" in artifact.data
    assert "conflicts_addressed" in artifact.data
    assert "confidence" in artifact.data
