"""BaseDSPyOperator: abstract base implementing OperatorProtocol with DSPy Predict.

All concrete operators (decompose, synthesize, etc.) inherit from this base.
The base handles:
  - Signature creation via vocab_schema_to_signature
  - DSPy Predict calls with JSONAdapter configuration
  - Conversion back to vocabulary types via prediction_to_vocab_output
  - Bound parameter merging (for bind combinator)
  - Repair retry with validation error context

Operators return raw Artifact with empty trace -- TraceEntry construction
is the runner's responsibility (Plan 04). call_metadata carries the prompt
and response data that the runner uses to build verbose trace entries.
"""

from __future__ import annotations

import copy
import json
import re
import threading
import time
from typing import Any

import dspy
from pydantic import BaseModel

from dillylang.operators.adapter import (
    prediction_to_vocab_output,
    try_prediction_to_vocab_output,
    vocab_schema_to_signature,
)
from dillylang.vocab.types import (
    Artifact,
    ArtifactStatus,
    Context,
    RunResult,
    RunResultStatus,
)


# Verb/question patterns for input quality heuristic. Compiled once at import.
_VERB_PATTERNS = [
    re.compile(
        r"\b(how|why|what|when|where|which|can|could|should|would|will|does|do|is|are)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(design|build|create|implement|improve|analyze|evaluate|find|solve|explain"
        r"|describe|compare|develop|make|write|define|identify|determine|assess|explore"
        r"|consider|reduce|increase|optimize|prevent|ensure|handle|manage|fix|debug"
        r"|test|deploy|configure|set up|integrate)\b",
        re.IGNORECASE,
    ),
]


def _check_input_quality(text: str) -> str | None:
    """Heuristic check for input quality. Returns warning string or None.

    Conservative: prefer false negatives to false positives (D-01).
    Checks for question marks or verb-like patterns. A noun phrase lacking
    any question or verb indicator gets a warning. This is a signal, not
    a gate -- the operator still executes.
    """
    if not text or len(text.strip()) < 5:
        return None

    stripped = text.strip()

    # Question marks are strong signal of problem statement
    if "?" in stripped:
        return None

    # Check for common verb indicators (imperative or descriptive)
    for pattern in _VERB_PATTERNS:
        if pattern.search(stripped):
            return None

    # Noun-phrase heuristic: no question, no verb -- warn
    if len(stripped) > 50:
        return (
            f"Input may be a noun phrase rather than a problem statement. "
            f"Operators work best with questions or action-oriented descriptions. "
            f"Input begins with: '{stripped[:50]}...'"
        )
    return (
        f"Input may be a noun phrase rather than a problem statement. "
        f"Operators work best with questions or action-oriented descriptions. "
        f"Input: '{stripped}'"
    )


# Module-level flag + lock: ensure JSONAdapter is configured once (thread-safe)
_adapter_lock = threading.Lock()
_adapter_configured = False


def _ensure_json_adapter() -> None:
    """Configure DSPy to use JSONAdapter if not already set.

    Uses double-checked locking to avoid contention after first configuration.
    """
    global _adapter_configured  # noqa: PLW0603
    if _adapter_configured:
        return
    with _adapter_lock:
        if not _adapter_configured:
            if dspy.settings.config.get("adapter") is None:
                dspy.configure(adapter=dspy.JSONAdapter())
            _adapter_configured = True


class BaseDSPyOperator:
    """Abstract base for DSPy-backed operators implementing OperatorProtocol.

    Subclasses only need to call super().__init__() with the right parameters.
    The base class handles signature creation, predict setup, run execution,
    repair retry, and bound parameter merging.
    """

    def __init__(
        self,
        name: str,
        docstring: str,
        input_model: type[BaseModel] | None,
        output_model: type[BaseModel],
        data_field_name: str = "problem_text",
        data_field_desc: str = "problem statement or upstream artifact",
    ) -> None:
        self._name = name
        self._docstring = docstring
        self._input_model = input_model
        self._output_model = output_model
        self._data_field_name = data_field_name
        self._data_field_desc = data_field_desc
        self._bound_params: dict[str, Any] = {}
        # Stashed prediction from last failed run() — available to run_repair()
        self._last_failed_prediction: dspy.Prediction | None = None

        _ensure_json_adapter()

        self._signature = vocab_schema_to_signature(
            name=f"{name.capitalize()}Signature",
            docstring=docstring,
            input_model=input_model,
            output_model=output_model,
            data_field_name=data_field_name,
            data_field_desc=data_field_desc,
        )
        self.predict = dspy.Predict(self._signature)

    @property
    def name(self) -> str:
        return self._name

    def _extract_data_value(self, input: Any) -> str:
        """Extract the primary data string from the operator input.

        Handles Artifact (serializes .data as JSON), str (pass-through),
        and dict (JSON serializes).
        """
        if isinstance(input, Artifact):
            return json.dumps(input.data, indent=2)
        if isinstance(input, dict):
            return json.dumps(input, indent=2)
        return str(input)

    def _build_kwargs(self, input: Any) -> dict[str, Any]:
        """Build the kwargs dict for the DSPy predict call.

        Combines the data value, any input_model steering params from
        the input, and any bound params (bound params override).
        """
        data_value = self._extract_data_value(input)
        kwargs: dict[str, Any] = {self._data_field_name: data_value}

        # Extract steering params from input if it's a Pydantic model
        # matching the input_model schema
        if self._input_model is not None and isinstance(input, self._input_model):
            for field_name in self._input_model.model_fields:
                val = getattr(input, field_name, None)
                if val is not None:
                    kwargs[field_name] = val

        # Bound params override (from bind combinator)
        if self._bound_params:
            kwargs.update(self._bound_params)

        # DSPy signatures declare all fields as str; serialize structured
        # values so DSPy doesn't emit type-mismatch warnings.
        for key, val in kwargs.items():
            if isinstance(val, (dict, list)):
                kwargs[key] = json.dumps(val)

        return kwargs

    def run(self, input: Any, ctx: Context) -> RunResult:
        """Execute the operator via DSPy Predict.

        Returns RunResult with:
          - output: Artifact containing structured data
          - trace: [] (empty -- runner owns TraceEntry construction)
          - status: SUCCESS
          - call_metadata: prompt, response, tokens, latency for trace building
            (includes input_warning when heuristic fires)
        """
        kwargs = self._build_kwargs(input)

        # Input validation gate (D-01): heuristic warning, never rejection.
        # Warning propagates via call_metadata on RunResult -- accessible to
        # trace viewer and any consumer via result.call_metadata["input_warning"].
        input_warning = _check_input_quality(
            kwargs.get(self._data_field_name, "")
        )

        history_idx = _get_history_index()
        start_time = time.monotonic()
        prediction = self.predict(**kwargs)
        latency_ms = int((time.monotonic() - start_time) * 1000)

        # Stash prediction before validation — if prediction_to_vocab_output
        # raises, run_repair() can access the raw LLM output for targeted repair.
        self._last_failed_prediction = prediction

        output = prediction_to_vocab_output(prediction, self._output_model)

        # Validation succeeded — clear the stash
        self._last_failed_prediction = None

        artifact = Artifact(
            id=f"{self._name}_{ctx.budget.llm_calls_used}",
            operator=self._name,
            step_index=len(ctx.trace),
            data=output.model_dump(),
            status=ArtifactStatus.SUCCESS,
        )

        call_metadata = _extract_call_metadata(
            latency_ms=latency_ms,
            input_data=kwargs.get(self._data_field_name, ""),
            history_index=history_idx,
        )
        if input_warning:
            call_metadata["input_warning"] = input_warning

        return RunResult(
            output=artifact,
            trace=[],
            status=RunResultStatus.SUCCESS,
            call_metadata=call_metadata,
        )

    def run_repair(self, input: Any, ctx: Context, error: str) -> RunResult:
        """Retry with validation error context prepended to the data field.

        Called by the runner (Plan 04) on parse/validation failure. Includes
        the error message so the LLM can attempt a corrected response.
        """
        kwargs = self._build_kwargs(input)

        # Prepend repair instruction to the data field
        original_data = kwargs.get(self._data_field_name, "")
        repair_prefix = (
            f"Previous attempt failed validation: {error}. "
            "Fix the output to match the required schema.\n\n"
        )
        kwargs[self._data_field_name] = repair_prefix + original_data

        history_idx = _get_history_index()
        start_time = time.monotonic()
        prediction = self.predict(**kwargs)
        latency_ms = int((time.monotonic() - start_time) * 1000)

        output = prediction_to_vocab_output(prediction, self._output_model)

        artifact = Artifact(
            id=f"{self._name}_{ctx.budget.llm_calls_used}",
            operator=self._name,
            step_index=len(ctx.trace),
            data=output.model_dump(),
            status=ArtifactStatus.REPAIR_SUCCEEDED,
        )

        call_metadata = _extract_call_metadata(
            latency_ms=latency_ms,
            input_data=kwargs.get(self._data_field_name, ""),
            history_index=history_idx,
        )

        return RunResult(
            output=artifact,
            trace=[],
            status=RunResultStatus.SUCCESS,
            call_metadata=call_metadata,
        )

    def with_bound_params(self, **params: Any) -> BaseDSPyOperator:
        """Return a shallow copy with merged bound parameters.

        This is the substrate-side API that bind (Plan 06) calls,
        keeping currying semantics clean across the adapter boundary.
        Bound params override any input-provided values for the same field.
        """
        clone = copy.copy(self)
        clone._bound_params = {**self._bound_params, **params}
        return clone


def _get_history_index() -> int:
    """Return current length of the active LM's history list.

    Used to snapshot before predict() so we can read the new entry after.
    """
    try:
        lm = dspy.settings.lm
        if lm is not None:
            return len(lm.history)
    except Exception:
        pass
    return -1


def _extract_call_metadata(
    latency_ms: int,
    input_data: str,
    history_index: int = -1,
) -> dict[str, Any]:
    """Extract call metadata from DSPy LM history for the runner's trace builder.

    Reads the history entry at history_index (snapshotted before predict())
    to get rendered prompt, raw response, and token usage.
    """
    rendered_prompt: str | None = None
    raw_response: str | None = None
    tokens_used: int | None = None

    try:
        lm = dspy.settings.lm
        if lm is not None and history_index >= 0 and history_index < len(lm.history):
            entry = lm.history[history_index]
            # Render prompt from messages list (what was actually sent to the LLM)
            messages = entry.get("messages")
            if messages:
                rendered_prompt = "\n".join(
                    f"[{m.get('role', '?')}] {m.get('content', '')}"
                    for m in messages
                )
            elif entry.get("prompt"):
                rendered_prompt = entry["prompt"]

            # Raw response: the text outputs the LLM returned
            outputs = entry.get("outputs")
            if outputs:
                raw_response = "\n---\n".join(
                    o if isinstance(o, str) else str(o) for o in outputs
                )

            # Token usage from the usage dict
            usage = entry.get("usage", {})
            if usage:
                tokens_used = usage.get("total_tokens")
    except Exception:
        pass  # Non-critical: metadata is best-effort

    return {
        "rendered_prompt": rendered_prompt,
        "raw_response": raw_response,
        "tokens_used": tokens_used,
        "latency_ms": latency_ms,
        "input_data": input_data,
    }
