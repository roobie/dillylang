"""Tests for targeted enum repair in synthesize.

Verifies: partial validation returns correct split, enum repair patches
successfully, non-enum failures fall through to base retry, and the
repair prompt is well-formed.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import dspy
import pytest
from pydantic import ValidationError

from dillylang.operators.adapter import (
    FieldValidationError,
    PartialValidationResult,
    try_prediction_to_vocab_output,
)
from dillylang.operators.base import BaseDSPyOperator
from dillylang.operators.synthesize import SynthesizeOperator
from dillylang.vocab.schemas import SynthesizeOutput
from dillylang.vocab.types import (
    Artifact,
    ArtifactStatus,
    Budget,
    Context,
    RunResultStatus,
)


# --- Fixtures ---


def _make_context() -> Context:
    return Context(
        problem="test problem",
        budget=Budget(max_llm_calls=7, llm_calls_used=2),
    )


def _valid_synth_data() -> dict:
    """Minimal valid SynthesizeOutput as a dict."""
    return {
        "proposal": {"statement": "Use caching", "rationale": "Reduces latency"},
        "incorporates": [
            {"source_artifact_id": "invert_0", "contribution": "Identified failure risk"},
        ],
        "tradeoffs": [{"gained": "Speed", "given_up": "Memory"}],
        "open_questions": ["How much memory?"],
        "conflicts_addressed": [
            {"conflict": "Speed vs safety", "resolution": "resolved"},
        ],
        "confidence": "high",
    }


def _synth_data_with_bad_enums() -> dict:
    """SynthesizeOutput with invalid enum values (simulates 8B model output)."""
    data = _valid_synth_data()
    data["conflicts_addressed"] = [
        {"conflict": "Speed vs safety", "resolution": "resolved through integration"},
        {"conflict": "Cost vs quality", "resolution": "partially addressed"},
    ]
    data["confidence"] = "fairly high"
    return data


# --- Partial validation tests ---


class TestTryPredictionToVocabOutput:
    def test_valid_data_returns_no_errors(self) -> None:
        prediction = dspy.Prediction(**_valid_synth_data())
        result = try_prediction_to_vocab_output(prediction, SynthesizeOutput)

        assert not result.has_errors
        assert result.errors == []
        assert result.raw_data["confidence"] == "high"

    def test_invalid_enums_returns_field_errors(self) -> None:
        prediction = dspy.Prediction(**_synth_data_with_bad_enums())
        result = try_prediction_to_vocab_output(prediction, SynthesizeOutput)

        assert result.has_errors
        # Should have errors for resolution fields and confidence
        assert len(result.errors) >= 2

    def test_enum_only_flag_true_for_literal_failures(self) -> None:
        prediction = dspy.Prediction(**_synth_data_with_bad_enums())
        result = try_prediction_to_vocab_output(prediction, SynthesizeOutput)

        assert result.is_enum_only

    def test_enum_only_flag_false_for_structural_failures(self) -> None:
        """Non-enum failures (missing required fields) are not enum-repairable."""
        data = _valid_synth_data()
        data["proposal"] = "not a dict"  # structural failure, not enum
        prediction = dspy.Prediction(**data)
        result = try_prediction_to_vocab_output(prediction, SynthesizeOutput)

        assert result.has_errors
        assert not result.is_enum_only

    def test_field_errors_contain_valid_values(self) -> None:
        prediction = dspy.Prediction(**_synth_data_with_bad_enums())
        result = try_prediction_to_vocab_output(prediction, SynthesizeOutput)

        resolution_errors = [
            e for e in result.errors if "resolution" in e.field_path
        ]
        assert len(resolution_errors) >= 1
        # Should contain the valid literal options
        assert "resolved" in resolution_errors[0].valid_values
        assert "deferred" in resolution_errors[0].valid_values
        assert "accepted_as_tradeoff" in resolution_errors[0].valid_values

    def test_raw_data_preserved_on_failure(self) -> None:
        data = _synth_data_with_bad_enums()
        prediction = dspy.Prediction(**data)
        result = try_prediction_to_vocab_output(prediction, SynthesizeOutput)

        # All fields are in raw_data regardless of validation
        assert "proposal" in result.raw_data
        assert "incorporates" in result.raw_data
        assert "conflicts_addressed" in result.raw_data


# --- Synthesize targeted repair tests ---


class TestSynthesizeTargetedRepair:
    def test_targeted_repair_builds_correct_prompt(self) -> None:
        op = SynthesizeOperator()
        partial = PartialValidationResult(
            raw_data=_synth_data_with_bad_enums(),
            errors=[
                FieldValidationError(
                    field_path="conflicts_addressed.0.resolution",
                    raw_value="resolved through integration",
                    error_message="Input should be 'resolved', 'deferred' or 'accepted_as_tradeoff'",
                    valid_values=["resolved", "deferred", "accepted_as_tradeoff"],
                ),
            ],
        )

        prompt = op._build_enum_repair_prompt(partial)

        assert "conflicts_addressed.0.resolution" in prompt
        assert "resolved through integration" in prompt
        assert '"resolved"' in prompt
        assert '"deferred"' in prompt
        assert '"accepted_as_tradeoff"' in prompt

    def test_patch_enum_values_nested_path(self) -> None:
        """Patching navigates nested paths like conflicts_addressed.0.resolution."""
        op = SynthesizeOperator()
        raw_data = _synth_data_with_bad_enums()
        errors = [
            FieldValidationError(
                field_path="conflicts_addressed.0.resolution",
                raw_value="resolved through integration",
                error_message="literal_error",
                valid_values=["resolved", "deferred", "accepted_as_tradeoff"],
            ),
            FieldValidationError(
                field_path="conflicts_addressed.1.resolution",
                raw_value="partially addressed",
                error_message="literal_error",
                valid_values=["resolved", "deferred", "accepted_as_tradeoff"],
            ),
        ]

        # Simulate LLM returning valid JSON
        repair_response = '{"conflicts_addressed.0.resolution": "resolved", "conflicts_addressed.1.resolution": "deferred"}'

        patched = op._patch_enum_values(raw_data, errors, repair_response)

        assert patched["conflicts_addressed"][0]["resolution"] == "resolved"
        assert patched["conflicts_addressed"][1]["resolution"] == "deferred"

    def test_patch_falls_back_to_first_valid_value(self) -> None:
        """If LLM repair response is garbage, falls back to first valid option."""
        op = SynthesizeOperator()
        raw_data = _synth_data_with_bad_enums()
        errors = [
            FieldValidationError(
                field_path="conflicts_addressed.0.resolution",
                raw_value="whatever",
                error_message="literal_error",
                valid_values=["resolved", "deferred", "accepted_as_tradeoff"],
            ),
        ]

        patched = op._patch_enum_values(raw_data, errors, "unparseable garbage")

        # Falls back to first valid value
        assert patched["conflicts_addressed"][0]["resolution"] == "resolved"

    def test_parse_repair_response_valid_json(self) -> None:
        op = SynthesizeOperator()
        response = '{"conflicts_addressed.0.resolution": "deferred"}'
        errors = [
            FieldValidationError(
                field_path="conflicts_addressed.0.resolution",
                raw_value="x",
                error_message="",
                valid_values=["resolved", "deferred", "accepted_as_tradeoff"],
            ),
        ]

        result = op._parse_repair_response(response, errors)
        assert result == {"conflicts_addressed.0.resolution": "deferred"}

    def test_parse_repair_response_fallback_extraction(self) -> None:
        """When JSON parsing fails, extract values by matching against valid options."""
        op = SynthesizeOperator()
        response = "The resolution should be deferred for now."
        errors = [
            FieldValidationError(
                field_path="conflicts_addressed.0.resolution",
                raw_value="x",
                error_message="",
                valid_values=["resolved", "deferred", "accepted_as_tradeoff"],
            ),
        ]

        result = op._parse_repair_response(response, errors)
        assert result["conflicts_addressed.0.resolution"] == "deferred"

    def test_non_enum_failure_falls_through_to_base(self) -> None:
        """When relaxed re-run produces non-enum errors, fall through to base retry."""
        op = SynthesizeOperator()
        ctx = _make_context()

        # Mock the relaxed predict to return structurally invalid data
        with patch("dspy.Predict") as mock_predict_cls:
            mock_instance = MagicMock()
            mock_instance.return_value = MagicMock(
                proposal="not a dict",  # structural error, not enum
                incorporates="[]",
                tradeoffs="[]",
                open_questions="[]",
                conflicts_addressed="[]",
                confidence="high",
            )
            mock_predict_cls.return_value = mock_instance

            with patch.object(
                BaseDSPyOperator, "run_repair"
            ) as mock_base_repair:
                mock_base_repair.return_value = MagicMock(status=RunResultStatus.SUCCESS)
                op.run_repair("input", ctx, error="structural error")
                mock_base_repair.assert_called_once()

    def test_run_repair_succeeds_with_targeted_enum_fix(self) -> None:
        """End-to-end: relaxed re-run + targeted classify fixes enum errors."""
        op = SynthesizeOperator()
        ctx = _make_context()

        bad_data = _synth_data_with_bad_enums()

        # First call: relaxed predict returns data with bad enums
        # Second call: classify predict returns corrected values
        call_count = [0]

        def mock_predict_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # Relaxed re-run: return the bad enum data as strings
                return MagicMock(
                    proposal=json.dumps(bad_data["proposal"]),
                    incorporates=json.dumps(bad_data["incorporates"]),
                    tradeoffs=json.dumps(bad_data["tradeoffs"]),
                    open_questions=json.dumps(bad_data["open_questions"]),
                    conflicts_addressed=json.dumps(bad_data["conflicts_addressed"]),
                    confidence="fairly high",
                )
            else:
                # Classify repair call
                return MagicMock(
                    repaired_values='{"conflicts_addressed.0.resolution": "resolved", "conflicts_addressed.1.resolution": "deferred", "confidence": "high"}'
                )

        with patch("dspy.Predict") as mock_predict_cls:
            mock_instance = MagicMock()
            mock_instance.side_effect = mock_predict_side_effect
            mock_predict_cls.return_value = mock_instance

            result = op.run_repair("input", ctx, error="literal_error")

        assert result.status == RunResultStatus.SUCCESS
        assert result.output.status == ArtifactStatus.REPAIR_SUCCEEDED
        assert result.output.data["conflicts_addressed"][0]["resolution"] == "resolved"
        assert result.output.data["conflicts_addressed"][1]["resolution"] == "deferred"
        assert result.output.data["confidence"] == "high"
        assert result.call_metadata["repair_strategy"] == "targeted_enum"

    def test_run_repair_relaxed_rerun_produces_valid_output(self) -> None:
        """If relaxed re-run produces valid data, no classify call needed."""
        op = SynthesizeOperator()
        ctx = _make_context()

        valid_data = _valid_synth_data()

        with patch("dspy.Predict") as mock_predict_cls:
            mock_instance = MagicMock()
            mock_instance.return_value = MagicMock(
                proposal=json.dumps(valid_data["proposal"]),
                incorporates=json.dumps(valid_data["incorporates"]),
                tradeoffs=json.dumps(valid_data["tradeoffs"]),
                open_questions=json.dumps(valid_data["open_questions"]),
                conflicts_addressed=json.dumps(valid_data["conflicts_addressed"]),
                confidence="high",
            )
            mock_predict_cls.return_value = mock_instance

            result = op.run_repair("input", ctx, error="some error")

        assert result.status == RunResultStatus.SUCCESS
        assert result.call_metadata["repair_strategy"] == "relaxed_rerun"
