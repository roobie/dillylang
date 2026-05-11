"""Unit tests for ConstrainOperator (no LLM calls).

Tests verify correct naming, protocol compliance, output schema fields,
no steering parameters (D-07), and that the prompt addresses constraining.
"""

from __future__ import annotations

from dillylang.operators.constrain import ConstrainOperator
from dillylang.vocab.protocol import OperatorProtocol


def test_constrain_operator_name() -> None:
    """ConstrainOperator has the correct name."""
    op = ConstrainOperator()
    assert op.name == "constrain"


def test_constrain_implements_protocol() -> None:
    """ConstrainOperator satisfies OperatorProtocol."""
    op = ConstrainOperator()
    assert isinstance(op, OperatorProtocol)


def test_constrain_has_output_fields() -> None:
    """The generated signature includes constrain-specific output fields."""
    op = ConstrainOperator()
    output_fields = list(op._signature.output_fields.keys())
    assert "constraints_added" in output_fields
    assert "impact_on_solution_space" in output_fields
    assert "tradeoffs" in output_fields


def test_constrain_has_no_steering_params() -> None:
    """D-07: no steering params for constrain yet."""
    op = ConstrainOperator()
    input_fields = list(op._signature.input_fields.keys())
    # Only the data field, no steering params
    assert input_fields == ["problem_text"]


def test_constrain_docstring_contains_key_phrases() -> None:
    """The constrain docstring addresses narrowing, not relaxation."""
    op = ConstrainOperator()
    doc = op._signature.__doc__
    assert any(word in doc.lower() for word in ["constraint", "narrow", "tighten", "limit"])
