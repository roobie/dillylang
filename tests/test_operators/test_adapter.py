"""Tests for the vocab-to-DSPy adapter boundary.

Verifies that Pydantic vocabulary schemas convert correctly to DSPy Signatures
and that DSPy Predictions convert back to vocabulary Pydantic models.
"""

from __future__ import annotations

import dspy

from dillylang.operators.adapter import prediction_to_vocab_output, vocab_schema_to_signature
from dillylang.vocab.schemas import (
    DecomposeInput,
    DecomposeOutput,
    InvertOutput,
)


def test_vocab_schema_to_signature_creates_input_fields() -> None:
    """Signature from DecomposeInput + DecomposeOutput has data + steering + output fields."""
    sig = vocab_schema_to_signature(
        name="DecomposeSig",
        docstring="Test decompose.",
        input_model=DecomposeInput,
        output_model=DecomposeOutput,
    )

    input_fields = list(sig.input_fields.keys())
    output_fields = list(sig.output_fields.keys())

    # Data channel always present
    assert "problem_text" in input_fields
    # Steering parameter from DecomposeInput
    assert "focus" in input_fields
    # Output fields from DecomposeOutput
    assert "axioms" in output_fields
    assert "derivations" in output_fields
    assert "assumptions" in output_fields


def test_vocab_schema_to_signature_no_input_model() -> None:
    """Signature from None + InvertOutput has only data InputField and output fields."""
    sig = vocab_schema_to_signature(
        name="InvertSig",
        docstring="Test invert.",
        input_model=None,
        output_model=InvertOutput,
    )

    input_fields = list(sig.input_fields.keys())
    output_fields = list(sig.output_fields.keys())

    # Only data channel -- no steering params
    assert input_fields == ["problem_text"]
    # InvertOutput fields
    assert "anti_goals" in output_fields
    assert "failure_modes" in output_fields
    assert "near_misses" in output_fields


def test_vocab_schema_to_signature_preserves_descriptions() -> None:
    """Field descriptions from Pydantic Field(description=...) appear in DSPy fields."""
    sig = vocab_schema_to_signature(
        name="DecomposeSig",
        docstring="Test.",
        input_model=DecomposeInput,
        output_model=DecomposeOutput,
    )

    # Check steering param description
    focus_field = sig.model_fields["focus"]
    assert "structural aspects" in (focus_field.json_schema_extra or {}).get("desc", "")

    # Check output field description
    axioms_field = sig.model_fields["axioms"]
    assert "foundational" in (axioms_field.json_schema_extra or {}).get("desc", "")


def test_vocab_schema_to_signature_custom_data_field() -> None:
    """Custom data_field_name and data_field_desc are used in the signature."""
    sig = vocab_schema_to_signature(
        name="SynthSig",
        docstring="Test synth.",
        input_model=None,
        output_model=InvertOutput,
        data_field_name="upstream_artifacts",
        data_field_desc="collected upstream outputs",
    )

    input_fields = list(sig.input_fields.keys())
    assert "upstream_artifacts" in input_fields
    assert "problem_text" not in input_fields


def test_prediction_to_vocab_output() -> None:
    """Mock Prediction with decompose fields converts to DecomposeOutput."""
    prediction = dspy.Prediction(
        axioms=[
            {"statement": "Users need fast feedback", "justification": "UX research"},
        ],
        derivations=[
            {"claim": "Cache improves latency", "depends_on": ["Users need fast feedback"]},
        ],
        assumptions=[
            {
                "statement": "Network is reliable",
                "load_bearing": True,
                "testable": "Monitor packet loss",
            },
        ],
    )

    output = prediction_to_vocab_output(prediction, DecomposeOutput)

    assert isinstance(output, DecomposeOutput)
    assert len(output.axioms) == 1
    assert output.axioms[0].statement == "Users need fast feedback"
    assert len(output.derivations) == 1
    assert output.derivations[0].claim == "Cache improves latency"
    assert len(output.assumptions) == 1
    assert output.assumptions[0].load_bearing is True
