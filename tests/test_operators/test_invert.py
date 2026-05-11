"""Tests for InvertOperator.

Unit tests run without LLM access. Integration tests (marked with
@pytest.mark.integration) require a configured LLM and are skipped
by default.
"""

from __future__ import annotations

import pytest

from dillylang.operators.invert import InvertOperator
from dillylang.vocab.protocol import OperatorProtocol


def test_invert_operator_name() -> None:
    """InvertOperator has the correct name."""
    op = InvertOperator()
    assert op.name == "invert"


def test_invert_implements_protocol() -> None:
    """InvertOperator satisfies OperatorProtocol."""
    op = InvertOperator()
    assert isinstance(op, OperatorProtocol)


def test_invert_docstring_requires_mechanism() -> None:
    """The invert docstring requires concrete mechanisms, not generic risks."""
    op = InvertOperator()
    doc = op._signature.__doc__
    assert "mechanism" in doc


def test_invert_has_output_fields() -> None:
    """The generated signature includes anti_goals, failure_modes, near_misses."""
    op = InvertOperator()
    output_fields = list(op._signature.output_fields.keys())
    assert "anti_goals" in output_fields
    assert "failure_modes" in output_fields
    assert "near_misses" in output_fields


def test_invert_no_steering_params() -> None:
    """Invert has no steering parameters in v0 -- only the data field."""
    op = InvertOperator()
    input_fields = list(op._signature.input_fields.keys())
    assert input_fields == ["problem_text"]


def test_invert_bound_params() -> None:
    """with_bound_params produces a copy that retains name and protocol."""
    op = InvertOperator()
    bound = op.with_bound_params(some_param="value")
    assert bound._bound_params == {"some_param": "value"}
    assert op._bound_params == {}
    assert bound.name == "invert"
    assert isinstance(bound, OperatorProtocol)


@pytest.mark.integration
def test_invert_end_to_end(sample_context):
    """Integration: run invert on a real problem with LLM."""
    from dillylang.vocab.types import RunResultStatus

    op = InvertOperator()
    result = op.run("Should we rewrite our monolith as microservices?", sample_context)

    assert result.status == RunResultStatus.SUCCESS
    assert result.trace == []
    assert result.call_metadata is not None

    artifact = result.output
    assert artifact.operator == "invert"
    assert "anti_goals" in artifact.data
    assert "failure_modes" in artifact.data
    assert "near_misses" in artifact.data
