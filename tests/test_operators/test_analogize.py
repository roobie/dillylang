"""Tests for AnalogizeOperator.

Unit tests run without LLM access. Integration tests (marked with
@pytest.mark.integration) require a configured LLM and are skipped
by default.
"""

from __future__ import annotations

import pytest

from dillylang.operators.analogize import AnalogizeOperator
from dillylang.vocab.protocol import OperatorProtocol


def test_analogize_operator_name() -> None:
    """AnalogizeOperator has the correct name."""
    op = AnalogizeOperator()
    assert op.name == "analogize"


def test_analogize_implements_protocol() -> None:
    """AnalogizeOperator satisfies OperatorProtocol."""
    op = AnalogizeOperator()
    assert isinstance(op, OperatorProtocol)


def test_analogize_docstring_mentions_stowaways() -> None:
    """The analogize docstring includes the stowaways anti-pattern guard."""
    op = AnalogizeOperator()
    doc = op._signature.__doc__
    assert "stowaways" in doc


def test_analogize_has_output_fields() -> None:
    """The generated signature includes problem_signature and analogies."""
    op = AnalogizeOperator()
    output_fields = list(op._signature.output_fields.keys())
    assert "problem_signature" in output_fields
    assert "analogies" in output_fields


def test_analogize_has_domains_steering_param() -> None:
    """Analogize has 'domains' as a steering parameter in its signature."""
    op = AnalogizeOperator()
    input_fields = list(op._signature.input_fields.keys())
    assert "problem_text" in input_fields
    assert "domains" in input_fields


def test_analogize_bound_params() -> None:
    """with_bound_params produces a copy that retains name and protocol."""
    op = AnalogizeOperator()
    bound = op.with_bound_params(domains=["biology", "economics"])
    assert bound._bound_params == {"domains": ["biology", "economics"]}
    assert op._bound_params == {}
    assert bound.name == "analogize"
    assert isinstance(bound, OperatorProtocol)


@pytest.mark.integration
def test_analogize_end_to_end(sample_context):
    """Integration: run analogize on a real problem with LLM."""
    from dillylang.vocab.types import RunResultStatus

    op = AnalogizeOperator()
    result = op.run("Should we rewrite our monolith as microservices?", sample_context)

    assert result.status == RunResultStatus.SUCCESS
    assert result.trace == []
    assert result.call_metadata is not None

    artifact = result.output
    assert artifact.operator == "analogize"
    assert "problem_signature" in artifact.data
    assert "analogies" in artifact.data
