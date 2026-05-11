"""Tests for RankOperator.

Unit tests run without LLM access. Integration tests (marked with
@pytest.mark.integration) require a configured LLM and are skipped
by default.
"""

from __future__ import annotations

import pytest

from dillylang.operators.rank import RankOperator
from dillylang.vocab.protocol import OperatorProtocol


def test_rank_operator_name() -> None:
    """RankOperator has the correct name."""
    op = RankOperator()
    assert op.name == "rank"


def test_rank_implements_protocol() -> None:
    """RankOperator satisfies OperatorProtocol."""
    op = RankOperator()
    assert isinstance(op, OperatorProtocol)


def test_rank_docstring_mentions_ids_only() -> None:
    """The rank docstring enforces the IDs-only provenance invariant."""
    op = RankOperator()
    doc = op._signature.__doc__
    assert "IDs only" in doc or "artifact IDs" in doc


def test_rank_has_criteria_in_signature() -> None:
    """The generated signature includes a 'criteria' steering parameter."""
    op = RankOperator()
    input_fields = list(op._signature.input_fields.keys())
    assert "criteria" in input_fields


def test_rank_has_top_k_in_signature() -> None:
    """The generated signature includes a 'top_k' steering parameter."""
    op = RankOperator()
    input_fields = list(op._signature.input_fields.keys())
    assert "top_k" in input_fields


def test_rank_has_output_fields() -> None:
    """The generated signature includes ranked and top_k_ids."""
    op = RankOperator()
    output_fields = list(op._signature.output_fields.keys())
    assert "ranked" in output_fields
    assert "top_k_ids" in output_fields


def test_rank_uses_artifacts_to_rank_data_field() -> None:
    """Rank uses 'artifacts_to_rank' as its data field, not 'problem_text'."""
    op = RankOperator()
    input_fields = list(op._signature.input_fields.keys())
    assert "artifacts_to_rank" in input_fields
    assert "problem_text" not in input_fields


def test_rank_serialize_artifacts() -> None:
    """_serialize_artifacts formats each artifact with id and data."""
    from dillylang.vocab.types import Artifact, ArtifactStatus

    op = RankOperator()
    artifacts = [
        Artifact(
            id="decompose_0",
            operator="decompose",
            step_index=0,
            data={"axioms": ["a1"]},
            status=ArtifactStatus.SUCCESS,
        ),
        Artifact(
            id="invert_1",
            operator="invert",
            step_index=1,
            data={"anti_goals": ["fail fast"]},
            status=ArtifactStatus.SUCCESS,
        ),
    ]
    text = op._serialize_artifacts(artifacts)
    assert "Artifact 'decompose_0':" in text
    assert "Artifact 'invert_1':" in text
    assert "a1" in text
    assert "fail fast" in text


def test_all_operators_importable() -> None:
    """All 7 v0 operator classes are importable from dillylang.operators."""
    from dillylang.operators import (
        AnalogizeOperator,
        DecomposeOperator,
        EvaluateOperator,
        InvertOperator,
        RankOperator,
        RotateOperator,
        SynthesizeOperator,
    )

    # Verify they're actual classes, not None or stubs
    for cls in [
        DecomposeOperator,
        SynthesizeOperator,
        InvertOperator,
        RotateOperator,
        AnalogizeOperator,
        EvaluateOperator,
        RankOperator,
    ]:
        assert callable(cls)
        op = cls()
        assert isinstance(op, OperatorProtocol)


@pytest.mark.integration
def test_rank_end_to_end(sample_context):
    """Integration: run rank on a collection of artifacts with LLM."""
    from dillylang.vocab.types import Artifact, ArtifactStatus, RunResultStatus

    artifacts = [
        Artifact(
            id="option_a",
            operator="decompose",
            step_index=0,
            data={"proposal": "Use microservices"},
            status=ArtifactStatus.SUCCESS,
        ),
        Artifact(
            id="option_b",
            operator="decompose",
            step_index=1,
            data={"proposal": "Improve the monolith"},
            status=ArtifactStatus.SUCCESS,
        ),
    ]

    op = RankOperator()
    bound = op.with_bound_params(criteria=["scalability", "team productivity"], top_k=1)
    result = bound.run(artifacts, sample_context)

    assert result.status == RunResultStatus.SUCCESS
    assert result.trace == []
    assert result.call_metadata is not None

    out = result.output
    assert out.operator == "rank"
    assert "ranked" in out.data
    assert "top_k_ids" in out.data
