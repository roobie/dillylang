"""Tests for DecomposeOperator.

Unit tests run without LLM access. Integration tests (marked with
@pytest.mark.integration) require a configured LLM and are skipped
by default.
"""

from __future__ import annotations

import pytest

from dillylang.operators.decompose import DecomposeOperator
from dillylang.vocab.protocol import OperatorProtocol


def test_decompose_operator_name() -> None:
    """DecomposeOperator has the correct name."""
    op = DecomposeOperator()
    assert op.name == "decompose"


def test_decompose_implements_protocol() -> None:
    """DecomposeOperator satisfies OperatorProtocol."""
    op = DecomposeOperator()
    assert isinstance(op, OperatorProtocol)


def test_decompose_has_focus_in_signature() -> None:
    """The generated signature includes a 'focus' steering parameter."""
    op = DecomposeOperator()
    input_fields = list(op._signature.input_fields.keys())
    assert "focus" in input_fields


def test_decompose_has_output_fields() -> None:
    """The generated signature includes axioms, derivations, assumptions output fields."""
    op = DecomposeOperator()
    output_fields = list(op._signature.output_fields.keys())
    assert "axioms" in output_fields
    assert "derivations" in output_fields
    assert "assumptions" in output_fields


def test_decompose_docstring_contains_key_phrases() -> None:
    """The decompose docstring includes the spec's key directive phrases."""
    op = DecomposeOperator()
    doc = op._signature.__doc__
    assert "load-bearing" in doc
    assert "search for axioms" in doc
    assert "Three sharp axioms" in doc


def test_decompose_bound_params() -> None:
    """with_bound_params produces a copy with focus pre-filled."""
    op = DecomposeOperator()
    bound = op.with_bound_params(focus="requirements, constraints")
    assert bound._bound_params == {"focus": "requirements, constraints"}
    # Original is unaffected
    assert op._bound_params == {}
    # Bound operator retains name and protocol
    assert bound.name == "decompose"
    assert isinstance(bound, OperatorProtocol)


@pytest.mark.integration
def test_decompose_end_to_end(sample_context):
    """Integration: run decompose on a real problem with LLM.

    Requires: --run-integration flag and configured LLM.
    """
    from dillylang.vocab.types import RunResultStatus

    op = DecomposeOperator()
    result = op.run("Should we rewrite our monolith as microservices?", sample_context)

    assert result.status == RunResultStatus.SUCCESS
    assert result.trace == []  # runner owns trace
    assert result.call_metadata is not None

    artifact = result.output
    assert artifact.operator == "decompose"
    assert "axioms" in artifact.data
    assert "derivations" in artifact.data
    assert "assumptions" in artifact.data
