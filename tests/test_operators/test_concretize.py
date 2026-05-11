"""Tests for ConcretizeOperator.

Unit tests run without LLM access. Integration tests (marked with
@pytest.mark.integration) require a configured LLM and are skipped
by default.
"""

from __future__ import annotations

from dillylang.operators.concretize import ConcretizeOperator
from dillylang.vocab.protocol import OperatorProtocol


def test_concretize_operator_name() -> None:
    """ConcretizeOperator has the correct name."""
    op = ConcretizeOperator()
    assert op.name == "concretize"


def test_concretize_implements_protocol() -> None:
    """ConcretizeOperator satisfies OperatorProtocol."""
    op = ConcretizeOperator()
    assert isinstance(op, OperatorProtocol)


def test_concretize_has_output_fields() -> None:
    """The generated signature includes instances and target_domain output fields."""
    op = ConcretizeOperator()
    output_fields = list(op._signature.output_fields.keys())
    assert "instances" in output_fields
    assert "target_domain" in output_fields


def test_concretize_has_no_steering_params() -> None:
    """D-07: no steering params for concretize yet."""
    op = ConcretizeOperator()
    input_fields = list(op._signature.input_fields.keys())
    assert input_fields == ["problem_text"]


def test_concretize_docstring_contains_key_phrases() -> None:
    """The concretize docstring addresses concretization."""
    op = ConcretizeOperator()
    doc = op._signature.__doc__
    assert any(word in doc.lower() for word in ["concrete", "instance", "specific", "grounded"])


def test_abstract_and_concretize_have_different_docstrings() -> None:
    """D-02: independent prompts, not mirrored skeletons."""
    from dillylang.operators.abstract_op import AbstractOperator

    abstract_doc = AbstractOperator()._signature.__doc__
    concretize_doc = ConcretizeOperator()._signature.__doc__
    assert abstract_doc != concretize_doc
