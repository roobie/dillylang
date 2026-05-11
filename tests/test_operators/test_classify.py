"""Unit tests for ClassifyOperator (no LLM calls).

Tests cover name, protocol compliance, required taxonomies,
signature fields, bound params, docstring, and B2 post-validation
(closed-set labels, taxonomy uniqueness).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dillylang.operators.classify import ClassifyOperator
from dillylang.vocab.protocol import OperatorProtocol
from dillylang.vocab.schemas import ClassifyInput


def test_classify_operator_name() -> None:
    """ClassifyOperator has the correct name."""
    op = ClassifyOperator()
    assert op.name == "classify"


def test_classify_implements_protocol() -> None:
    """ClassifyOperator satisfies OperatorProtocol."""
    op = ClassifyOperator()
    assert isinstance(op, OperatorProtocol)


def test_classify_requires_taxonomies() -> None:
    """ClassifyInput without taxonomies raises ValidationError."""
    with pytest.raises(ValidationError):
        ClassifyInput()  # type: ignore[call-arg]


def test_classify_accepts_taxonomies() -> None:
    """ClassifyInput accepts a taxonomies dict."""
    inp = ClassifyInput(taxonomies={"problem_type": ["optimization", "analysis"]})
    assert "problem_type" in inp.taxonomies


def test_classify_has_taxonomies_in_signature() -> None:
    """The generated signature includes a 'taxonomies' steering parameter."""
    op = ClassifyOperator()
    input_fields = list(op._signature.input_fields.keys())
    assert "taxonomies" in input_fields


def test_classify_has_output_fields() -> None:
    """The generated signature includes 'classifications' output field."""
    op = ClassifyOperator()
    output_fields = list(op._signature.output_fields.keys())
    assert "classifications" in output_fields


def test_classify_bound_taxonomies() -> None:
    """D-08: bind(classify, taxonomies={...}) produces a reusable classifier."""
    op = ClassifyOperator()
    bound = op.with_bound_params(
        taxonomies={"problem_type": ["optimization", "analysis", "design"]}
    )
    assert "problem_type" in bound._bound_params["taxonomies"]
    assert op._bound_params == {}  # original unchanged


def test_classify_docstring_contains_key_phrases() -> None:
    """The classify docstring mentions classification-relevant terms."""
    op = ClassifyOperator()
    doc = op._signature.__doc__
    assert any(
        word in doc.lower()
        for word in ["classify", "label", "taxonomy", "categor"]
    )


def test_classify_bound_returns_protocol() -> None:
    """A bound classify operator still satisfies OperatorProtocol."""
    op = ClassifyOperator()
    bound = op.with_bound_params(taxonomies={"x": ["a", "b"]})
    assert isinstance(bound, OperatorProtocol)
    assert bound.name == "classify"


# --- B2: ADR-005 post-validation tests ---


def test_classify_validate_detects_invalid_label() -> None:
    """B2: closed-set labels -- label must be in taxonomy's label list."""
    op = ClassifyOperator()
    taxonomies = {"problem_type": ["optimization", "analysis", "design"]}
    data = {
        "classifications": [
            {
                "taxonomy": "problem_type",
                "label": "fabricated_label",
                "rationale": "...",
                "confidence": "high",
            }
        ]
    }
    violations = op._validate_classifications(data, taxonomies)
    assert len(violations) == 1
    assert "fabricated_label" in violations[0]
    assert "problem_type" in violations[0]


def test_classify_validate_detects_duplicate_taxonomy() -> None:
    """B2: uniqueness by taxonomy -- one classification per taxonomy."""
    op = ClassifyOperator()
    taxonomies = {"problem_type": ["optimization", "analysis"]}
    data = {
        "classifications": [
            {
                "taxonomy": "problem_type",
                "label": "optimization",
                "rationale": "...",
                "confidence": "high",
            },
            {
                "taxonomy": "problem_type",
                "label": "analysis",
                "rationale": "...",
                "confidence": "high",
            },
        ]
    }
    violations = op._validate_classifications(data, taxonomies)
    assert any("Duplicate" in v for v in violations)


def test_classify_focus_in_signature() -> None:
    """Optional focus field appears in the DSPy signature as an input field."""
    op = ClassifyOperator()
    input_fields = list(op._signature.input_fields.keys())
    assert "focus" in input_fields


def test_classify_focus_flows_through_bind() -> None:
    """bind(classify, focus=...) makes focus available in bound params."""
    op = ClassifyOperator()
    bound = op.with_bound_params(
        taxonomies={"x": ["a", "b"]},
        focus="classify the target recipe, not the source skill",
    )
    assert bound._bound_params["focus"] == "classify the target recipe, not the source skill"


def test_classify_focus_optional() -> None:
    """ClassifyInput accepts taxonomies without focus."""
    inp = ClassifyInput(taxonomies={"x": ["a", "b"]})
    assert inp.focus is None


def test_classify_validate_accepts_valid_output() -> None:
    """B2: valid output has no violations."""
    op = ClassifyOperator()
    taxonomies = {
        "problem_type": ["optimization", "analysis"],
        "difficulty": ["easy", "hard"],
    }
    data = {
        "classifications": [
            {
                "taxonomy": "problem_type",
                "label": "optimization",
                "rationale": "...",
                "confidence": "high",
            },
            {
                "taxonomy": "difficulty",
                "label": "hard",
                "rationale": "...",
                "confidence": "medium",
            },
        ]
    }
    violations = op._validate_classifications(data, taxonomies)
    assert violations == []
