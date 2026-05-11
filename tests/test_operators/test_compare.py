"""Unit tests for CompareOperator (no LLM calls).

Tests cover name, protocol compliance, required criterion,
custom data field, output fields, serialize_pair, bound params,
and input validation (D-03: strictly pairwise).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dillylang.operators.compare import CompareOperator
from dillylang.vocab.protocol import OperatorProtocol
from dillylang.vocab.schemas import CompareInput
from dillylang.vocab.types import Artifact, ArtifactStatus


def test_compare_operator_name() -> None:
    """CompareOperator has the correct name."""
    op = CompareOperator()
    assert op.name == "compare"


def test_compare_implements_protocol() -> None:
    """CompareOperator satisfies OperatorProtocol."""
    op = CompareOperator()
    assert isinstance(op, OperatorProtocol)


def test_compare_requires_criterion() -> None:
    """CompareInput without criterion raises ValidationError."""
    with pytest.raises(ValidationError):
        CompareInput()  # type: ignore[call-arg]


def test_compare_accepts_criterion() -> None:
    """CompareInput accepts a criterion string."""
    inp = CompareInput(criterion="scalability")
    assert inp.criterion == "scalability"


def test_compare_uses_artifacts_to_compare_data_field() -> None:
    """Compare uses 'artifacts_to_compare' as its data field, not 'problem_text'."""
    op = CompareOperator()
    input_fields = list(op._signature.input_fields.keys())
    assert "artifacts_to_compare" in input_fields
    assert "problem_text" not in input_fields


def test_compare_has_criterion_in_signature() -> None:
    """The generated signature includes a 'criterion' steering parameter."""
    op = CompareOperator()
    input_fields = list(op._signature.input_fields.keys())
    assert "criterion" in input_fields


def test_compare_has_output_fields() -> None:
    """The generated signature includes winner, rationale, comparison_points, confidence."""
    op = CompareOperator()
    output_fields = list(op._signature.output_fields.keys())
    assert "winner" in output_fields
    assert "rationale" in output_fields
    assert "comparison_points" in output_fields
    assert "confidence" in output_fields


def test_compare_serialize_pair() -> None:
    """_serialize_pair formats two artifacts with A/B labeling."""
    op = CompareOperator()
    art_a = Artifact(
        id="decompose_0",
        operator="decompose",
        step_index=0,
        data={"axioms": ["a1"]},
        status=ArtifactStatus.SUCCESS,
    )
    art_b = Artifact(
        id="invert_1",
        operator="invert",
        step_index=1,
        data={"anti_goals": ["fail"]},
        status=ArtifactStatus.SUCCESS,
    )
    text = op._serialize_pair(art_a, art_b)
    assert "Artifact A" in text
    assert "Artifact B" in text
    assert "'decompose_0'" in text
    assert "'invert_1'" in text


def test_compare_bound_criterion() -> None:
    """with_bound_params can pre-fill criterion for bind combinator."""
    op = CompareOperator()
    bound = op.with_bound_params(criterion="scalability")
    assert bound._bound_params == {"criterion": "scalability"}
    assert op._bound_params == {}


def test_compare_bound_returns_protocol() -> None:
    """A bound compare operator still satisfies OperatorProtocol."""
    op = CompareOperator()
    bound = op.with_bound_params(criterion="quality")
    assert isinstance(bound, OperatorProtocol)
    assert bound.name == "compare"


def test_compare_rejects_non_list_input() -> None:
    """D-03: compare raises TypeError for non-list input."""
    from dillylang.vocab.types import Budget, Context

    op = CompareOperator()
    ctx = Context(
        problem="test",
        budget=Budget(max_llm_calls=10, max_tokens=10_000, max_wall_time_ms=60_000),
    )
    with pytest.raises(TypeError, match="expects a list"):
        op.run("not a list", ctx)


def test_compare_rejects_wrong_length_list() -> None:
    """D-03: compare raises TypeError for list with != 2 items."""
    from dillylang.vocab.types import Budget, Context

    op = CompareOperator()
    ctx = Context(
        problem="test",
        budget=Budget(max_llm_calls=10, max_tokens=10_000, max_wall_time_ms=60_000),
    )
    art = Artifact(
        id="x", operator="x", step_index=0,
        data={}, status=ArtifactStatus.SUCCESS,
    )
    with pytest.raises(TypeError, match="exactly 2"):
        op.run([art], ctx)
    with pytest.raises(TypeError, match="exactly 2"):
        op.run([art, art, art], ctx)
