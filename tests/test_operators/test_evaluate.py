"""Tests for EvaluateOperator.

Unit tests run without LLM access. Integration tests (marked with
@pytest.mark.integration) require a configured LLM and are skipped
by default.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dillylang.operators.evaluate import EvaluateOperator
from dillylang.vocab.protocol import OperatorProtocol
from dillylang.vocab.schemas import EvaluateInput


def test_evaluate_operator_name() -> None:
    """EvaluateOperator has the correct name."""
    op = EvaluateOperator()
    assert op.name == "evaluate"


def test_evaluate_implements_protocol() -> None:
    """EvaluateOperator satisfies OperatorProtocol."""
    op = EvaluateOperator()
    assert isinstance(op, OperatorProtocol)


def test_evaluate_requires_criterion() -> None:
    """EvaluateInput without criterion raises ValidationError.

    Unlike focus/target_frame, criterion has no default -- evaluate
    without a criterion is invalid per ADR-007.
    """
    with pytest.raises(ValidationError):
        EvaluateInput()  # type: ignore[call-arg]


def test_evaluate_accepts_criterion() -> None:
    """EvaluateInput accepts a criterion string."""
    inp = EvaluateInput(criterion="technical feasibility")
    assert inp.criterion == "technical feasibility"


def test_evaluate_has_criterion_in_signature() -> None:
    """The generated signature includes a 'criterion' steering parameter."""
    op = EvaluateOperator()
    input_fields = list(op._signature.input_fields.keys())
    assert "criterion" in input_fields


def test_evaluate_has_output_fields() -> None:
    """The generated signature includes verdict, evidence, rationale, confidence.

    criterion is NOT in output_fields -- it's an InputField (steering param).
    The adapter skips output fields that collide with already-registered inputs.
    """
    op = EvaluateOperator()
    output_fields = list(op._signature.output_fields.keys())
    assert "criterion" not in output_fields  # steering param, not output
    assert "verdict" in output_fields
    assert "evidence" in output_fields
    assert "rationale" in output_fields
    assert "confidence" in output_fields


def test_evaluate_bound_criterion() -> None:
    """with_bound_params can pre-fill criterion for bind combinator."""
    op = EvaluateOperator()
    bound = op.with_bound_params(criterion="scalability")
    assert bound._bound_params == {"criterion": "scalability"}
    assert op._bound_params == {}
    assert bound.name == "evaluate"
    assert isinstance(bound, OperatorProtocol)


@pytest.mark.integration
def test_evaluate_end_to_end(sample_context):
    """Integration: run evaluate on a real artifact with LLM."""
    from dillylang.vocab.types import Artifact, ArtifactStatus, RunResultStatus

    op = EvaluateOperator()
    bound = op.with_bound_params(criterion="technical feasibility")

    artifact = Artifact(
        id="test_0",
        operator="decompose",
        step_index=0,
        data={"axioms": [{"statement": "Python is suitable", "justification": "ecosystem"}]},
        status=ArtifactStatus.SUCCESS,
    )
    result = bound.run(artifact, sample_context)

    assert result.status == RunResultStatus.SUCCESS
    assert result.trace == []
    assert result.call_metadata is not None

    out = result.output
    assert out.operator == "evaluate"
    assert "verdict" in out.data
    assert out.data["verdict"] in ("pass", "partial", "fail")
