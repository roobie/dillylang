"""CompareOperator: pairwise comparison of two artifacts on a criterion.

Wraps BaseDSPyOperator with the compare-specific prompt, schema, and
a run() override that handles the two-artifact input contract (D-03).

The key constraint: compare is strictly pairwise -- exactly 2 artifacts.
The winner must be one of the two artifact IDs or "tie" (M3).

Spec reference: INDEX.md section 6 (compare schema).
Steering parameter: criterion (required, via ADR-007).
Threat model: T-02-09 -- validate winner ID.
"""

from __future__ import annotations

import json
import time
from typing import Any

from dillylang.operators.adapter import prediction_to_vocab_output, vocab_schema_to_signature
from dillylang.operators.base import BaseDSPyOperator, _extract_call_metadata, _check_input_quality
from dillylang.vocab.schemas import CompareInput, CompareOutput
from dillylang.vocab.types import (
    Artifact,
    ArtifactStatus,
    Context,
    ItemError,
    RunResult,
    RunResultStatus,
)

# Prompt docstring guiding the LLM for pairwise comparison.
_COMPARE_DOCSTRING = (
    "Compare exactly two artifacts on the specified criterion. Identify the "
    "winner (or declare a tie) with clear rationale. Provide dimension-by-"
    "dimension comparison points, assessing each artifact independently on "
    "each dimension before comparing. The criterion is the lens -- do not "
    "compare on other dimensions. The winner must be one of the artifact IDs "
    "or the literal string 'tie'."
)


class CompareOperator(BaseDSPyOperator):
    """Judge operator: pairwise comparison of two artifacts.

    Receives exactly two Artifacts, compares them on the bound criterion,
    and returns a winner (artifact ID or "tie") with rationale and
    dimension-by-dimension comparison points.

    D-03: Strictly pairwise -- input must be exactly 2 artifacts.
    M3: Winner must be in {artifact_a.id, artifact_b.id, "tie"}.
    """

    def __init__(self) -> None:
        super().__init__(
            name="compare",
            docstring=_COMPARE_DOCSTRING,
            input_model=CompareInput,  # criterion is required
            output_model=CompareOutput,
            data_field_name="artifacts_to_compare",
            data_field_desc="two artifacts to compare, each presented with id and structured data",
        )

    def _serialize_pair(self, artifact_a: Artifact, artifact_b: Artifact) -> str:
        """Serialize two artifacts with A/B labeling for the LLM."""
        a_data = json.dumps(artifact_a.data, indent=2)
        b_data = json.dumps(artifact_b.data, indent=2)
        return (
            f"Artifact A ('{artifact_a.id}'):\n{a_data}\n\n"
            f"Artifact B ('{artifact_b.id}'):\n{b_data}"
        )

    def run(self, input: Any, ctx: Context) -> RunResult:
        """Execute compare with pairwise input handling and winner validation.

        1. Normalizes input to exactly 2 Artifacts (D-03)
        2. Serializes pair with A/B labeling
        3. Calls DSPy Predict
        4. Validates winner is in {artifact_a.id, artifact_b.id, "tie"} (M3)
        """
        # D-03: Strictly pairwise -- exactly 2 artifacts
        if not isinstance(input, list):
            raise TypeError(
                f"compare expects a list of exactly 2 Artifacts, got {type(input).__name__}"
            )
        if len(input) != 2:
            raise TypeError(
                f"compare expects exactly 2 Artifacts, got {len(input)}"
            )

        artifacts = input
        serialized = self._serialize_pair(artifacts[0], artifacts[1])

        # Input quality check
        input_warning = _check_input_quality(serialized)

        # Build kwargs: data field + steering params from bound_params
        kwargs: dict[str, Any] = {"artifacts_to_compare": serialized}
        if self._bound_params:
            kwargs.update(self._bound_params)

        start_time = time.monotonic()
        prediction = self.predict(**kwargs)
        latency_ms = int((time.monotonic() - start_time) * 1000)

        output = prediction_to_vocab_output(prediction, self._output_model)
        output_data = output.model_dump()

        call_metadata = _extract_call_metadata(
            latency_ms=latency_ms,
            input_data=serialized,
        )
        if input_warning:
            call_metadata["input_warning"] = input_warning

        # M3: Validate winner is a known artifact ID or "tie"
        valid_winners = {artifacts[0].id, artifacts[1].id, "tie"}
        winner = output_data.get("winner", "")
        if winner not in valid_winners:
            repair_msg = (
                f"Winner '{winner}' is not valid. Must be one of: "
                f"{artifacts[0].id}, {artifacts[1].id}, or 'tie'"
            )
            # Repair-once-then-fail-loud: retry predict with error context
            # (mirrors run_repair pattern from base.py)
            try:
                repair_kwargs = dict(kwargs)
                original_data = repair_kwargs.get("artifacts_to_compare", "")
                repair_kwargs["artifacts_to_compare"] = (
                    f"Previous attempt failed validation: {repair_msg}. "
                    "Fix the output to match the required schema.\n\n"
                    + original_data
                )
                prediction = self.predict(**repair_kwargs)
                output = prediction_to_vocab_output(prediction, self._output_model)
                output_data = output.model_dump()
                winner = output_data.get("winner", "")
                if winner not in valid_winners:
                    # Second failure -- fail loud
                    return RunResult(
                        output=Artifact(
                            id=f"{self._name}_invalid_winner",
                            operator=self._name,
                            step_index=len(ctx.trace),
                            data=output_data,
                            status=ArtifactStatus.FAILED,
                        ),
                        trace=[],
                        status=RunResultStatus.FAILED,
                        errors=[ItemError(
                            item_id=f"{self._name}_winner",
                            error_kind="invalid_winner",
                            message=repair_msg,
                        )],
                        call_metadata=call_metadata,
                    )
            except Exception as exc:
                return RunResult(
                    output=Artifact(
                        id=f"{self._name}_repair_failed",
                        operator=self._name,
                        step_index=len(ctx.trace),
                        data=output_data,
                        status=ArtifactStatus.FAILED,
                    ),
                    trace=[],
                    status=RunResultStatus.FAILED,
                    errors=[ItemError(
                        item_id=f"{self._name}_winner",
                        error_kind="repair_failed",
                        message=f"{repair_msg}; repair call failed: {exc}",
                    )],
                    call_metadata=call_metadata,
                )

        artifact = Artifact(
            id=f"{self._name}_{ctx.budget.llm_calls_used}",
            operator=self._name,
            step_index=len(ctx.trace),
            data=output_data,
            status=ArtifactStatus.SUCCESS,
        )

        return RunResult(
            output=artifact,
            trace=[],
            status=RunResultStatus.SUCCESS,
            call_metadata=call_metadata,
        )
