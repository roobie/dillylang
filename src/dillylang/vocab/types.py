"""Vocabulary leaf layer: core types with zero runtime dependencies.

All types in this module are pure Pydantic models and stdlib enums.
Nothing here imports DSPy or any substrate -- the adapter boundary
lives in dillylang.operators. This invariant is tested.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ArtifactStatus(str, Enum):
    """Per-artifact outcome status."""

    SUCCESS = "success"
    REPAIR_SUCCEEDED = "repair_succeeded"
    FAILED = "failed"
    PARTIAL = "partial"


class ItemError(BaseModel):
    """Per-item error detail for collection operations."""

    item_id: str
    error_kind: str  # e.g. "parse_failure", "llm_error", "predicate_error"
    message: str


class Artifact(BaseModel):
    """Unit of data flowing between operators.

    Keyed in Context.artifacts by "{operator_name}_{step_index}".
    """

    id: str  # unique within a pipeline run
    operator: str  # which operator produced this
    step_index: int  # position in pipeline
    data: dict[str, Any]  # the operator's structured output
    status: ArtifactStatus
    errors: list[ItemError] | None = None


class Budget(BaseModel):
    """Per-pipeline resource budget.

    Ceiling is 7 LLM calls (spec section 10). Sweet spot is 4-5.
    Individual operators consume from the budget; they cannot override it.
    """

    max_llm_calls: int = Field(default=7, description="ceiling per spec: 7")
    max_tokens: int = Field(default=100_000, description="~100K total per pipeline")
    max_wall_time_ms: int = Field(default=300_000, description="300s wall time")
    llm_calls_used: int = 0
    tokens_used: int = 0
    elapsed_ms: int = 0


class TraceEventType(str, Enum):
    """Discriminator for trace entry kinds."""

    LLM_CALL = "llm_call"
    COMBINATOR_START = "combinator_start"
    COMBINATOR_END = "combinator_end"
    SELECTOR = "selector"


class TraceEntry(BaseModel):
    """Single event in a pipeline execution trace.

    Traces are always emitted in RunResult (ADR-002); persistence is opt-in.
    Treat trace data as sensitive -- it may contain rendered prompts and
    raw LLM responses.
    """

    trace_id: str  # unique within a pipeline run
    event_type: TraceEventType
    operator_name: str
    step_index: int
    timestamp: datetime
    status: ArtifactStatus

    # present for llm_call events
    input: Any | None = None
    rendered_prompt: str | None = None
    raw_response: str | None = None
    parsed_output: Any | None = None
    tokens_used: int | None = None
    latency_ms: int | None = None

    # present for combinator_start/combinator_end events
    children: list[str] | None = None  # trace_ids of child entries

    # present for selector events
    field: str | None = None  # e.g. "assumptions"
    selected_count: int | None = None


class RunResultStatus(str, Enum):
    """Overall pipeline/operator run outcome."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    BUDGET_EXHAUSTED = "budget_exhausted"


class RunResult(BaseModel):
    """Canonical return type for every .run() call.

    Operators, combinators, and full pipelines all return this.
    """

    output: Artifact | list[Artifact]
    trace: list[TraceEntry] = Field(default_factory=list)
    status: RunResultStatus
    errors: list[ItemError] | None = None
    budget: Budget | None = Field(
        default=None,
        description="Populated by runner at completion; trace viewer reads for budget summary",
    )
    call_metadata: dict[str, Any] | None = Field(
        default=None,
        description="Populated by substrate operators with rendered_prompt, raw_response, etc.",
    )
    artifacts: dict[str, Artifact] | None = Field(
        default=None,
        description="All artifacts produced during pipeline execution. "
        "Populated by PipelineRunner; used by post-pipeline renderers.",
    )


class Context(BaseModel):
    """Immutable-problem execution context passed to every operator.

    The problem field is the original user input and should not be mutated.
    Artifacts accumulate as the pipeline runs; keyed by "{op_name}_{step_index}".

    Meta-skill pipelines pass Artifact as problem (structured input from
    upstream pipeline stages). Standard pipelines pass str.
    """

    problem: str | Artifact
    artifacts: dict[str, Artifact] = Field(default_factory=dict)
    trace: list[TraceEntry] = Field(default_factory=list)
    budget: Budget = Field(default_factory=Budget)
