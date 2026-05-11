"""Tests for AbstractOperator.

Unit tests run without LLM access. Integration tests (marked with
@pytest.mark.integration) require a configured LLM and are skipped
by default.
"""

from __future__ import annotations

from dillylang.operators.abstract_op import AbstractOperator
from dillylang.vocab.protocol import OperatorProtocol


def test_abstract_operator_name() -> None:
    """AbstractOperator has the correct name."""
    op = AbstractOperator()
    assert op.name == "abstract"


def test_abstract_implements_protocol() -> None:
    """AbstractOperator satisfies OperatorProtocol."""
    op = AbstractOperator()
    assert isinstance(op, OperatorProtocol)


def test_abstract_has_output_fields() -> None:
    """The generated signature includes principles and source_pattern output fields."""
    op = AbstractOperator()
    output_fields = list(op._signature.output_fields.keys())
    assert "principles" in output_fields
    assert "source_pattern" in output_fields


def test_abstract_has_no_steering_params() -> None:
    """D-07: no steering params for abstract yet."""
    op = AbstractOperator()
    input_fields = list(op._signature.input_fields.keys())
    # Only the data field, no steering params
    assert input_fields == ["problem_text"]


def test_abstract_docstring_contains_key_phrases() -> None:
    """The abstract docstring addresses abstraction, not concretization."""
    op = AbstractOperator()
    doc = op._signature.__doc__
    # Verify the prompt addresses abstraction (not a mirror of concretize)
    assert any(word in doc.lower() for word in ["principle", "general", "pattern", "abstract"])
