"""Unit tests for branch combinator (mock operators, no LLM calls).

Tests cover _extract_label (4 cases), BranchOperator construction (4 cases),
routing behavior (3 cases), trace emission (1 case), and M2 input
passthrough (1 case).
"""

from __future__ import annotations

from typing import Any

import pytest

from dillylang.combinators.branch import BranchOperator, _extract_label, branch
from dillylang.vocab.types import (
    Artifact,
    ArtifactStatus,
    Budget,
    Context,
    RunResult,
    RunResultStatus,
)


# --- Mock operators ---


class MockPipeline:
    """A mock pipeline that returns a labeled artifact."""

    def __init__(self, label: str) -> None:
        self._label = label
        self.call_count = 0
        self.last_input = None  # M2: track what input the route received

    @property
    def name(self) -> str:
        return f"mock_{self._label}"

    def run(self, input: Any, ctx: Context) -> RunResult:
        self.call_count += 1
        self.last_input = input  # M2: capture for assertion
        return RunResult(
            output=Artifact(
                id=f"branch_{self._label}_0",
                operator=self.name,
                step_index=0,
                data={"routed_to": self._label},
                status=ArtifactStatus.SUCCESS,
            ),
            trace=[],
            status=RunResultStatus.SUCCESS,
        )


def _make_ctx() -> Context:
    return Context(
        problem="test",
        budget=Budget(max_llm_calls=100, max_tokens=100_000, max_wall_time_ms=600_000),
    )


def _make_classified_artifact(taxonomy: str, label: str) -> Artifact:
    """Create an artifact with classify output structure."""
    return Artifact(
        id="classify_0",
        operator="classify",
        step_index=0,
        data={
            "classifications": [
                {
                    "taxonomy": taxonomy,
                    "label": label,
                    "rationale": "test",
                    "confidence": "high",
                }
            ]
        },
        status=ArtifactStatus.SUCCESS,
    )


# --- _extract_label tests ---


def test_extract_label_found() -> None:
    """Extracts label for a matching taxonomy."""
    art = _make_classified_artifact("problem_type", "optimization")
    assert _extract_label(art, "problem_type") == "optimization"


def test_extract_label_wrong_taxonomy() -> None:
    """Returns None when the requested taxonomy is not in classifications."""
    art = _make_classified_artifact("problem_type", "optimization")
    assert _extract_label(art, "recipe_shape") is None


def test_extract_label_missing_classifications() -> None:
    """Returns None when Artifact.data lacks a 'classifications' key."""
    art = Artifact(
        id="x", operator="x", step_index=0,
        data={"foo": "bar"}, status=ArtifactStatus.SUCCESS,
    )
    assert _extract_label(art, "anything") is None


def test_extract_label_non_artifact() -> None:
    """Returns None for non-Artifact input."""
    assert _extract_label("not an artifact", "anything") is None


# --- BranchOperator construction tests ---


def test_branch_requires_non_empty_taxonomy() -> None:
    """BranchOperator raises ValueError for empty taxonomy_name."""
    with pytest.raises(ValueError):
        BranchOperator("", {}, MockPipeline("default"))


def test_branch_requires_dict_routes() -> None:
    """BranchOperator raises TypeError for non-dict routes."""
    with pytest.raises(TypeError):
        BranchOperator("tax", "not a dict", MockPipeline("default"))  # type: ignore[arg-type]


def test_branch_factory_returns_branch_operator() -> None:
    """branch() factory creates a BranchOperator with correct name."""
    op = branch("tax", {"a": MockPipeline("a")}, MockPipeline("default"))
    assert isinstance(op, BranchOperator)
    assert op.name == "branch"


def test_branch_is_combinator() -> None:
    """BranchOperator has is_combinator = True."""
    op = branch("tax", {}, MockPipeline("default"))
    assert op.is_combinator is True


# --- BranchOperator routing tests ---


def test_branch_routes_to_matching_label() -> None:
    """Branch dispatches to the correct sub-pipeline for a matching label."""
    route_a = MockPipeline("route_a")
    route_b = MockPipeline("route_b")
    default = MockPipeline("default")
    op = branch(
        "problem_type",
        {"optimization": route_a, "analysis": route_b},
        default,
    )

    art = _make_classified_artifact("problem_type", "optimization")
    result = op.run(art, _make_ctx())

    assert result.status == RunResultStatus.SUCCESS
    assert route_a.call_count == 1
    assert route_b.call_count == 0
    assert default.call_count == 0


def test_branch_routes_to_default_for_unknown_label() -> None:
    """Branch uses default pipeline when label is not in routes."""
    route_a = MockPipeline("route_a")
    default = MockPipeline("default")
    op = branch("problem_type", {"optimization": route_a}, default)

    art = _make_classified_artifact("problem_type", "unknown_label")
    result = op.run(art, _make_ctx())

    assert result.status == RunResultStatus.SUCCESS
    assert route_a.call_count == 0
    assert default.call_count == 1


def test_branch_routes_to_default_when_no_classifications() -> None:
    """Branch uses default pipeline when upstream has no classifications."""
    default = MockPipeline("default")
    op = branch("problem_type", {"optimization": MockPipeline("a")}, default)

    art = Artifact(
        id="x", operator="x", step_index=0,
        data={}, status=ArtifactStatus.SUCCESS,
    )
    result = op.run(art, _make_ctx())

    assert default.call_count == 1


def test_branch_emits_trace_entries() -> None:
    """Branch emits combinator_start and combinator_end trace entries."""
    op = branch("tax", {"a": MockPipeline("a")}, MockPipeline("default"))
    art = _make_classified_artifact("tax", "a")
    result = op.run(art, _make_ctx())

    # Should have at least combinator_start and combinator_end
    assert len(result.trace) >= 2
    assert result.trace[0].operator_name == "branch"
    assert result.trace[-1].operator_name == "branch"


def test_branch_passes_classify_artifact_to_route() -> None:
    """M2: Routes receive the classify artifact (branch's input), not the original.

    In pipe(classify, branch(...)), branch's input IS the classify output artifact.
    The route should receive exactly this artifact.
    """
    route_a = MockPipeline("route_a")
    op = branch("problem_type", {"optimization": route_a}, MockPipeline("default"))

    classify_artifact = _make_classified_artifact("problem_type", "optimization")
    op.run(classify_artifact, _make_ctx())

    # The route received the classify artifact itself
    assert route_a.last_input is classify_artifact
    assert route_a.last_input.operator == "classify"
    assert "classifications" in route_a.last_input.data
