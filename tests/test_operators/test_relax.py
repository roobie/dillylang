"""Unit tests for RelaxOperator (no LLM calls).

Tests verify correct naming, protocol compliance, output schema fields,
no steering parameters (D-07), prompt content, and that constrain and
relax have independent docstrings (D-02).
"""

from __future__ import annotations

from dillylang.operators.relax import RelaxOperator
from dillylang.vocab.protocol import OperatorProtocol


def test_relax_operator_name() -> None:
    """RelaxOperator has the correct name."""
    op = RelaxOperator()
    assert op.name == "relax"


def test_relax_implements_protocol() -> None:
    """RelaxOperator satisfies OperatorProtocol."""
    op = RelaxOperator()
    assert isinstance(op, OperatorProtocol)


def test_relax_has_output_fields() -> None:
    """The generated signature includes relax-specific output fields."""
    op = RelaxOperator()
    output_fields = list(op._signature.output_fields.keys())
    assert "constraints_removed" in output_fields
    assert "new_possibilities" in output_fields
    assert "risks_introduced" in output_fields


def test_relax_has_no_steering_params() -> None:
    """D-07: no steering params for relax yet."""
    op = RelaxOperator()
    input_fields = list(op._signature.input_fields.keys())
    # Only the data field, no steering params
    assert input_fields == ["problem_text"]


def test_relax_docstring_contains_key_phrases() -> None:
    """The relax docstring addresses widening, not constraining."""
    op = RelaxOperator()
    doc = op._signature.__doc__
    assert any(word in doc.lower() for word in ["loosen", "relax", "widen", "remove"])


def test_constrain_and_relax_have_different_docstrings() -> None:
    """D-02: independent prompts, not mirrored skeletons."""
    from dillylang.operators.constrain import ConstrainOperator

    constrain_doc = ConstrainOperator()._signature.__doc__
    relax_doc = RelaxOperator()._signature.__doc__
    assert constrain_doc != relax_doc
