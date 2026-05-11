"""RankOperator: score and order artifacts by named criteria.

Wraps BaseDSPyOperator with the rank-specific prompt, schema, and
a run() override that handles the collection-input contract.

The key invariant: rank returns artifact IDs only -- never full
artifacts. The runtime resolves IDs to originals from context.
This prevents the LLM from mutating, fabricating, or partially
echoing source artifacts.

Spec reference: INDEX.md section 6 (rank schema), section 5 (identity invariant).
Steering parameters: criteria (required), top_k (optional).
Threat model: T-01-05-01 -- validate that top_k_ids reference real artifact IDs.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from dillylang.operators.adapter import prediction_to_vocab_output, vocab_schema_to_signature
from dillylang.operators.base import BaseDSPyOperator, _extract_call_metadata
from dillylang.vocab.schemas import RankInput, RankOutput
from dillylang.vocab.types import (
    Artifact,
    ArtifactStatus,
    Context,
    RunResult,
    RunResultStatus,
)

logger = logging.getLogger(__name__)

# Spec section 6 docstring with the IDs-only provenance invariant.
_RANK_DOCSTRING = (
    "Score and order artifacts by named criteria. Return artifact IDs only "
    "-- never full artifacts. The runtime resolves IDs to original artifacts "
    "from context. This prevents the LLM from mutating, fabricating, or "
    "partially echoing source artifacts. Rank each artifact on each "
    "criterion as high, medium, or low with rationale."
)


class RankOperator(BaseDSPyOperator):
    """Judge operator: rank a collection of artifacts by criteria.

    Receives a list of Artifacts (or a single Artifact), scores each
    on each criterion, and returns ordered artifact IDs. The top_k
    parameter limits the returned set.

    The run() override serializes the artifact collection and validates
    that returned IDs reference actual input artifacts (T-01-05-01).
    """

    def __init__(self) -> None:
        super().__init__(
            name="rank",
            docstring=_RANK_DOCSTRING,
            input_model=RankInput,
            output_model=RankOutput,
            data_field_name="artifacts_to_rank",
            data_field_desc=(
                "collection of artifacts to rank, each presented with id "
                "and structured data"
            ),
        )

    def _serialize_artifacts(self, artifacts: list[Artifact]) -> str:
        """Serialize artifacts for the LLM, presenting id and data.

        Format: Artifact '{id}': {json data} -- one per artifact.
        The LLM references these IDs in its ranking output.
        """
        parts = []
        for art in artifacts:
            data_str = json.dumps(art.data, indent=2)
            parts.append(f"Artifact '{art.id}': {data_str}")
        return "\n\n".join(parts)

    def run(self, input: Any, ctx: Context) -> RunResult:
        """Execute rank with collection-input handling and ID validation.

        1. Normalizes input to list[Artifact]
        2. Serializes artifacts for the LLM
        3. Calls DSPy Predict
        4. Validates that top_k_ids reference real artifact IDs (T-01-05-01)
        """
        # Normalize input to list[Artifact]
        if isinstance(input, list):
            artifacts = input
        elif isinstance(input, Artifact):
            artifacts = [input]
        else:
            # Fallback: delegate to base for non-artifact input
            return super().run(input, ctx)

        valid_ids = {art.id for art in artifacts}
        serialized = self._serialize_artifacts(artifacts)

        # Build kwargs: data field + steering params from bound_params
        kwargs: dict[str, Any] = {"artifacts_to_rank": serialized}
        if self._bound_params:
            kwargs.update(self._bound_params)

        start_time = time.monotonic()
        prediction = self.predict(**kwargs)
        latency_ms = int((time.monotonic() - start_time) * 1000)

        output = prediction_to_vocab_output(prediction, self._output_model)

        # Validate that returned IDs reference real artifacts (T-01-05-01).
        # Log warnings for fabricated IDs but don't fail -- the output may
        # still be partially useful.
        for rank_score in output.ranked:
            if rank_score.artifact_id not in valid_ids:
                logger.warning(
                    "rank returned fabricated artifact_id '%s' "
                    "(not in input collection: %s)",
                    rank_score.artifact_id,
                    valid_ids,
                )
        for tid in output.top_k_ids:
            if tid not in valid_ids:
                logger.warning(
                    "rank returned fabricated top_k_id '%s' "
                    "(not in input collection: %s)",
                    tid,
                    valid_ids,
                )

        artifact = Artifact(
            id=f"{self._name}_{ctx.budget.llm_calls_used}",
            operator=self._name,
            step_index=len(ctx.trace),
            data=output.model_dump(),
            status=ArtifactStatus.SUCCESS,
        )

        call_metadata = _extract_call_metadata(
            latency_ms=latency_ms,
            input_data=serialized,
        )

        return RunResult(
            output=artifact,
            trace=[],
            status=RunResultStatus.SUCCESS,
            call_metadata=call_metadata,
        )
