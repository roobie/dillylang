"""Tests for RotateOperator.

Unit tests run without LLM access. Integration tests (marked with
@pytest.mark.integration) require a configured LLM and are skipped
by default.
"""

from __future__ import annotations

import pytest

from dillylang.operators.rotate import RotateOperator
from dillylang.vocab.protocol import OperatorProtocol


def test_rotate_operator_name() -> None:
    """RotateOperator has the correct name."""
    op = RotateOperator()
    assert op.name == "rotate"


def test_rotate_implements_protocol() -> None:
    """RotateOperator satisfies OperatorProtocol."""
    op = RotateOperator()
    assert isinstance(op, OperatorProtocol)


def test_rotate_has_target_frame_in_signature() -> None:
    """The generated signature includes a 'target_frame' steering parameter."""
    op = RotateOperator()
    input_fields = list(op._signature.input_fields.keys())
    assert "target_frame" in input_fields


def test_rotate_docstring_mentions_implicit_subject() -> None:
    """The rotate docstring probes for the implicit subject of the framing."""
    op = RotateOperator()
    doc = op._signature.__doc__
    assert "implicit subject" in doc


def test_rotate_has_output_fields() -> None:
    """The generated signature includes original_axis and rotations."""
    op = RotateOperator()
    output_fields = list(op._signature.output_fields.keys())
    assert "original_axis" in output_fields
    assert "rotations" in output_fields


def test_rotate_bound_target_frame() -> None:
    """with_bound_params can pre-fill target_frame for bind combinator."""
    op = RotateOperator()
    bound = op.with_bound_params(target_frame="user experience")
    assert bound._bound_params == {"target_frame": "user experience"}
    assert op._bound_params == {}
    assert bound.name == "rotate"
    assert isinstance(bound, OperatorProtocol)


@pytest.mark.integration
def test_rotate_end_to_end(sample_context):
    """Integration: run rotate on a real problem with LLM."""
    from dillylang.vocab.types import RunResultStatus

    op = RotateOperator()
    result = op.run("Should we rewrite our monolith as microservices?", sample_context)

    assert result.status == RunResultStatus.SUCCESS
    assert result.trace == []
    assert result.call_metadata is not None

    artifact = result.output
    assert artifact.operator == "rotate"
    assert "original_axis" in artifact.data
    assert "rotations" in artifact.data
