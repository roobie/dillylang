"""SynthesizeOperator: rebuild from collected upstream perspectives.

This is the highest-leverage prompt in the system. The anti-averaging
instruction is the core quality gate -- if synthesis "feels like averaging,"
the prompt has failed.

Spec reference: INDEX.md section 4 (synthesize schema).
ADR-006: base integration contract (6 fields).

Synthesize has no steering parameters in v0. The data channel receives
collected upstream artifacts (from parallel or preceding pipeline steps).
"""

from __future__ import annotations

import json
import time
from typing import Any

import dspy
from pydantic import BaseModel

from dillylang.operators.adapter import PartialValidationResult
from dillylang.operators.base import BaseDSPyOperator
from dillylang.vocab.schemas import SynthesizeOutput
from dillylang.vocab.types import (
    Artifact,
    ArtifactStatus,
    Context,
    RunResult,
    RunResultStatus,
)

# The full anti-averaging instruction per spec section 4. Every word
# here matters -- this is the most-iterated prompt in the system.
_SYNTHESIZE_DOCSTRING = (
    "Rebuild from the collected upstream perspectives. This is NOT a weighted "
    "average -- if your proposal feels like a weighted average, you have not "
    "synthesized -- you have summarized. Try again. Each upstream artifact "
    "must be acknowledged with a named contribution OR explicitly deferred to "
    "open_questions. Silent dropping is forbidden. Concrete tradeoffs only -- "
    "'balance flexibility and structure' is rejected. Surface every conflict "
    "between upstream perspectives and state whether it was resolved, deferred, "
    "or accepted as a tradeoff."
)


# Base fields whose type annotations must not be changed by subclasses (ADR-006 Rule 2)
_SYNTHESIZE_BASE_FIELDS = frozenset({
    "proposal", "incorporates", "tradeoffs",
    "open_questions", "conflicts_addressed", "confidence",
})


def _check_base_field_shadowing(
    extended_model: type[BaseModel],
    base_model: type[BaseModel] = SynthesizeOutput,
) -> list[str]:
    """Check that extended model does not shadow base field type annotations.

    ADR-006 Rule 2: extensions are additive top-level keys. They must not
    modify, reinterpret, or shadow base field semantics. A subclass that
    changes a base field's type annotation violates this rule.

    Returns list of violation descriptions (empty = valid).
    """
    violations: list[str] = []
    base_hints = base_model.__annotations__
    extended_hints = extended_model.__annotations__

    for field_name in _SYNTHESIZE_BASE_FIELDS:
        if field_name in extended_hints and field_name in base_hints:
            if extended_hints[field_name] != base_hints[field_name]:
                violations.append(
                    f"Field '{field_name}' has type {extended_hints[field_name]} "
                    f"in {extended_model.__name__}, but base SynthesizeOutput "
                    f"declares it as {base_hints[field_name]}. "
                    f"ADR-006 Rule 2: extensions must not shadow base fields."
                )
    return violations


class SynthesizeOperator(BaseDSPyOperator):
    """Integration operator: synthesize upstream artifacts into a coherent whole.

    Handles both single Artifact input (from pipe) and list[Artifact] input
    (from parallel). Each upstream artifact is presented with its id, operator,
    and structured data so the LLM can reference them by name.
    """

    def __init__(self, output_model: type[BaseModel] | None = None) -> None:
        """Create a SynthesizeOperator.

        Args:
            output_model: Optional extended output model. Must be a subclass of
                SynthesizeOutput (ADR-006 Rule 1: base fields always required).
                Must not shadow base field type annotations (ADR-006 Rule 2).
                If None, uses SynthesizeOutput directly.
        """
        resolved_model = output_model or SynthesizeOutput
        if not issubclass(resolved_model, SynthesizeOutput):
            raise TypeError(
                f"Extended output model must be a subclass of SynthesizeOutput, "
                f"got {resolved_model.__name__}. "
                f"ADR-006 Rule 1: base integration fields are always required."
            )

        # M4: Check for base-field shadowing
        if resolved_model is not SynthesizeOutput:
            shadowing_violations = _check_base_field_shadowing(resolved_model)
            if shadowing_violations:
                raise TypeError(
                    f"Extended output model {resolved_model.__name__} shadows "
                    f"base SynthesizeOutput fields: {'; '.join(shadowing_violations)}"
                )

        super().__init__(
            name="synthesize",
            docstring=_SYNTHESIZE_DOCSTRING,
            input_model=None,
            output_model=resolved_model,
            data_field_name="upstream_artifacts",
            data_field_desc=(
                "collected upstream artifacts from preceding pipeline steps, "
                "each with id and structured data"
            ),
        )

    def _serialize_artifacts(self, artifacts: list[Artifact]) -> str:
        """Serialize a list of Artifacts into text for the LLM.

        Each artifact is presented as:
          Artifact '{id}' ({operator}): {json data}

        This format lets the LLM reference specific artifacts by id in
        the incorporates and conflicts_addressed fields.
        """
        parts = []
        for art in artifacts:
            data_str = json.dumps(art.data, indent=2)
            parts.append(f"Artifact '{art.id}' ({art.operator}): {data_str}")
        return "\n\n".join(parts)

    def run(self, input: Any, ctx: Context) -> RunResult:
        """Execute synthesize with special input handling.

        Normalizes the input to a list of Artifacts, serializes them
        as the upstream_artifacts text, then delegates to the base run().
        """
        # Normalize input to list[Artifact]
        if isinstance(input, list):
            artifacts = input
        elif isinstance(input, Artifact):
            artifacts = [input]
        else:
            # Fallback: pass through as string to base run()
            return super().run(input, ctx)

        serialized = self._serialize_artifacts(artifacts)
        return super().run(serialized, ctx)

    def run_repair(self, input: Any, ctx: Context, error: str) -> RunResult:
        """Targeted enum repair: re-run with relaxed types, then fix enum fields.

        DSPy's AdapterParseError fires INSIDE predict() when output field types
        are strict Pydantic models. The prediction never reaches us. Strategy:
        re-run with a relaxed signature (all str outputs) so DSPy's adapter
        doesn't validate, then do our own partial validation + targeted repair.
        """
        # Build the same input kwargs as a normal run
        if isinstance(input, list):
            serialized = self._serialize_artifacts(input)
        elif isinstance(input, Artifact):
            serialized = self._serialize_artifacts([input])
        else:
            serialized = str(input)

        # Phase 1: Re-run with a relaxed signature (str output fields)
        # so DSPy doesn't validate the enum fields internally
        relaxed_sig = self._build_relaxed_signature()
        relaxed_predict = dspy.Predict(relaxed_sig)

        start_time = time.monotonic()
        relaxed_prediction = relaxed_predict(upstream_artifacts=serialized)
        phase1_latency = int((time.monotonic() - start_time) * 1000)

        # Phase 2: Parse raw strings into a data dict and try validation
        raw_data = self._parse_relaxed_prediction(relaxed_prediction)
        partial = self._validate_raw_data(raw_data)

        if not partial.has_errors:
            # Relaxed re-run produced valid output — done
            output = self._output_model.model_validate(partial.raw_data)
            return self._make_repair_result(output, ctx, phase1_latency, "relaxed_rerun")

        if not partial.is_enum_only:
            # Non-enum errors — can't do targeted repair, fall back to base
            return super().run_repair(input, ctx, error=error)

        # Phase 3: Targeted enum repair via minimal classify call
        repair_prompt = self._build_enum_repair_prompt(partial)

        start_time = time.monotonic()
        repair_sig = dspy.Signature(
            "classify_prompt -> repaired_values",
            instructions=(
                "You are given fields that need to be classified into exact values. "
                "Return ONLY a JSON object mapping each field path to its corrected value. "
                "Do not add explanation."
            ),
        )
        repair_predict = dspy.Predict(repair_sig)
        repair_result = repair_predict(classify_prompt=repair_prompt)
        phase2_latency = int((time.monotonic() - start_time) * 1000)

        patched_data = self._patch_enum_values(
            partial.raw_data, partial.errors, repair_result.repaired_values
        )

        output = self._output_model.model_validate(patched_data)
        return self._make_repair_result(
            output, ctx, phase1_latency + phase2_latency, "targeted_enum"
        )

    def _build_relaxed_signature(self) -> type[dspy.Signature]:
        """Build a signature with all output fields typed as str.

        DSPy's JSONAdapter won't attempt Pydantic validation on plain str fields,
        so this always succeeds at the DSPy level. We validate ourselves after.
        """
        fields: dict[str, Any] = {
            "__doc__": self._signature.__doc__,
            "__annotations__": {},
        }
        fields["__annotations__"]["upstream_artifacts"] = str
        fields["upstream_artifacts"] = dspy.InputField(
            desc="collected upstream artifacts from preceding pipeline steps"
        )

        for field_name, field_info in self._output_model.model_fields.items():
            fields["__annotations__"][field_name] = str
            desc = field_info.description or field_name
            fields[field_name] = dspy.OutputField(desc=desc)

        return type("SynthesizeRelaxedSignature", (dspy.Signature,), fields)

    def _parse_relaxed_prediction(self, prediction: dspy.Prediction) -> dict[str, Any]:
        """Parse string fields from relaxed prediction into structured data."""
        data: dict[str, Any] = {}
        for field_name in self._output_model.model_fields:
            raw = getattr(prediction, field_name, None)
            if raw is None:
                continue
            # Try JSON parse for complex fields (lists, dicts)
            if isinstance(raw, str):
                try:
                    data[field_name] = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    data[field_name] = raw
            else:
                # DSPy may have already parsed it
                data[field_name] = raw
        return data

    def _validate_raw_data(self, raw_data: dict[str, Any]) -> PartialValidationResult:
        """Validate raw data dict against the output model, returning partial result."""
        from dillylang.operators.adapter import _extract_field_errors

        from pydantic import ValidationError as PydanticValidationError
        try:
            self._output_model.model_validate(raw_data)
            return PartialValidationResult(raw_data=raw_data, errors=[])
        except PydanticValidationError as exc:
            errors = _extract_field_errors(exc)
            return PartialValidationResult(raw_data=raw_data, errors=errors)

    def _make_repair_result(
        self, output: BaseModel, ctx: Context, latency_ms: int, strategy: str
    ) -> RunResult:
        artifact = Artifact(
            id=f"{self._name}_{ctx.budget.llm_calls_used}",
            operator=self._name,
            step_index=len(ctx.trace),
            data=output.model_dump(),
            status=ArtifactStatus.REPAIR_SUCCEEDED,
        )
        return RunResult(
            output=artifact,
            trace=[],
            status=RunResultStatus.SUCCESS,
            call_metadata={
                "latency_ms": latency_ms,
                "repair_strategy": strategy,
            },
        )

    def _build_enum_repair_prompt(self, partial: PartialValidationResult) -> str:
        """Build a minimal forced-choice prompt for enum field repair."""
        lines = ["Classify each field into EXACTLY one of the valid values.\n"]
        for err in partial.errors:
            valid_str = ", ".join(f'"{v}"' for v in err.valid_values)
            lines.append(
                f"Field: {err.field_path}\n"
                f"  Current value: {err.raw_value!r}\n"
                f"  Valid options: [{valid_str}]\n"
            )
        lines.append(
            '\nReturn a JSON object like: {"field_path": "chosen_value", ...}'
        )
        return "\n".join(lines)

    def _patch_enum_values(
        self, raw_data: dict, errors: list, repaired_values_str: str
    ) -> dict:
        """Patch repaired enum values into the raw data dict.

        Handles nested field paths like "conflicts_addressed.0.resolution"
        by traversing the data structure.
        """
        # Parse the LLM's response as JSON
        repaired = self._parse_repair_response(repaired_values_str, errors)

        for err in errors:
            path_parts = err.field_path.split(".")
            value = repaired.get(err.field_path)
            if value is None:
                # Fallback: pick the first valid value rather than failing
                value = err.valid_values[0] if err.valid_values else err.raw_value

            # Navigate to the nested location and patch
            target = raw_data
            for part in path_parts[:-1]:
                if part.isdigit():
                    target = target[int(part)]
                else:
                    target = target[part]
            final_key = path_parts[-1]
            if final_key.isdigit():
                target[int(final_key)] = value
            else:
                target[final_key] = value

        return raw_data

    def _parse_repair_response(
        self, response: str, errors: list
    ) -> dict[str, str]:
        """Best-effort parse of the repair LLM's JSON response."""
        try:
            parsed = json.loads(response)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass

        # Fallback: try to extract values by matching against valid options
        result: dict[str, str] = {}
        response_lower = response.lower()
        for err in errors:
            for valid in err.valid_values:
                if valid.lower() in response_lower:
                    result[err.field_path] = valid
                    break
        return result
