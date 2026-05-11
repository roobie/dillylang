"""Tests for static orthogonality metrics computation."""

from __future__ import annotations

import json
from pathlib import Path

from dillylang.skills.metrics import compute_efficacy, compute_metrics
from dillylang.vocab.schemas import DillylangSkillDescription
from dillylang.vocab.types import Artifact, ArtifactStatus, RunResult, RunResultStatus


def _make_description(
    operators: list[str] | None = None,
    pseudocode: str = "",
    combinators: list[str] | None = None,
) -> DillylangSkillDescription:
    """Build a minimal DillylangSkillDescription for testing metrics."""
    return DillylangSkillDescription(
        skill_name="test_skill",
        skill_purpose="testing metrics",
        activation_contract="manual",
        execution_model="sequential",
        recipe_shape="generative",
        source_contract_entrypoints=[],
        source_contract_inputs=[],
        source_contract_outputs=[],
        source_contract_control_flow=[],
        dillylang_pseudocode=pseudocode,
        dillylang_operators=operators or [],
        dillylang_combinators=combinators or [],
        stage_mapping=[],
        residue=[],
        open_questions=[],
        confidence="medium",
    )


def test_coverage_counts_distinct_axes():
    """Coverage counts unique axes; decompose+synthesize share compositionality."""
    desc = _make_description(
        operators=["decompose", "synthesize", "rotate"],
        pseudocode="pipe(decompose, synthesize, rotate)",
    )
    metrics = compute_metrics(desc)

    # decompose + synthesize -> compositionality (1 axis), rotate -> frame (1 axis)
    assert metrics.coverage == 2
    assert sorted(metrics.axes_touched) == ["compositionality", "frame"]
    assert "valence" in metrics.axes_missing
    assert "substrate" in metrics.axes_missing
    assert "abstraction" in metrics.axes_missing
    assert "feasibility" in metrics.axes_missing


def test_coverage_ignores_judges():
    """Judge operators don't touch thinking axes."""
    desc = _make_description(
        operators=["evaluate", "classify"],
        pseudocode="pipe(evaluate, classify)",
    )
    metrics = compute_metrics(desc)

    assert metrics.coverage == 0
    assert metrics.axes_touched == []
    assert len(metrics.axes_missing) == 6


def test_depth_pipe_sequential():
    """pipe(a, b) has depth = sum of children = 2."""
    desc = _make_description(
        operators=["decompose", "synthesize"],
        pseudocode="pipe(decompose, synthesize)",
    )
    metrics = compute_metrics(desc)

    assert metrics.depth == 2


def test_depth_parallel_counts_as_one():
    """parallel counts as 1 sequential step regardless of branch count."""
    desc = _make_description(
        operators=["decompose", "rotate", "synthesize"],
        pseudocode="pipe(parallel(decompose, rotate), synthesize)",
    )
    metrics = compute_metrics(desc)

    # parallel(decompose, rotate) = max(1, 1) = 1, then + synthesize = 1
    assert metrics.depth == 2


def test_cost_counts_llm_operators():
    """Cost counts all LLM-calling operators (transformers + judges)."""
    desc = _make_description(
        operators=["decompose", "rotate", "classify", "evaluate", "synthesize"],
        pseudocode="pipe(decompose, rotate, classify, evaluate, synthesize)",
    )
    metrics = compute_metrics(desc)

    assert metrics.cost == 5


def test_cost_excludes_non_llm():
    """Combinators are not LLM operators and don't count toward cost."""
    # In practice, combinators wouldn't appear in dillylang_operators list,
    # but test the exclusion logic anyway
    desc = _make_description(
        operators=["decompose", "pipe", "parallel"],
        pseudocode="pipe(decompose)",
    )
    metrics = compute_metrics(desc)

    # Only decompose is an LLM operator
    assert metrics.cost == 1


def test_efficiency_dual_metrics():
    """cost_efficiency = coverage/cost, depth_efficiency = coverage/depth."""
    # 3 axes: compositionality (decompose+synthesize), valence (invert), frame (rotate)
    # depth from pseudocode: pipe(decompose, invert, rotate, synthesize) = 4
    # cost: 4 LLM operators
    desc = _make_description(
        operators=["decompose", "invert", "rotate", "synthesize"],
        pseudocode="pipe(decompose, invert, rotate, synthesize)",
    )
    metrics = compute_metrics(desc)

    assert metrics.coverage == 3  # compositionality, valence, frame
    assert metrics.depth == 4
    assert metrics.cost == 4
    assert metrics.cost_efficiency == 0.75  # 3/4
    assert metrics.depth_efficiency == 0.75  # 3/4


def test_efficiency_zero_denominators():
    """Zero cost/depth produces 0.0 efficiency, not division errors."""
    desc = _make_description(operators=[], pseudocode="")
    metrics = compute_metrics(desc)

    assert metrics.cost_efficiency == 0.0
    assert metrics.depth_efficiency == 0.0
    assert metrics.coverage == 0
    assert metrics.depth == 0
    assert metrics.cost == 0


def test_depth_nested_pipe_parallel():
    """pipe(a, parallel(b, c), d) has depth 3: a=1, parallel=1, d=1."""
    desc = _make_description(
        operators=["decompose", "invert", "rotate", "synthesize"],
        pseudocode="pipe(decompose, parallel(invert, rotate), synthesize)",
    )
    metrics = compute_metrics(desc)

    # decompose(1) + parallel(max(1,1))=1 + synthesize(1) = 3
    assert metrics.depth == 3


def test_full_metrics_refine_recipe():
    """End-to-end: typical refine recipe with parallel operators."""
    desc = _make_description(
        operators=["decompose", "invert", "rotate", "synthesize"],
        pseudocode="pipe(decompose, parallel(invert, rotate), synthesize)",
    )
    metrics = compute_metrics(desc)

    # Coverage: compositionality (decompose+synthesize), valence (invert), frame (rotate)
    assert metrics.coverage == 3
    assert sorted(metrics.axes_touched) == ["compositionality", "frame", "valence"]

    # Depth: pipe(decompose=1, parallel(1,1)=1, synthesize=1) = 3
    assert metrics.depth == 3

    # Cost: 4 LLM operators
    assert metrics.cost == 4

    # Efficiency
    assert metrics.cost_efficiency == 0.75  # 3/4
    assert metrics.depth_efficiency == 1.0  # 3/3


# --- compute_efficacy tests ---

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _make_artifact(
    artifact_id: str, operator: str, step_index: int, data: dict | None = None
) -> Artifact:
    """Build a minimal Artifact for testing efficacy."""
    return Artifact(
        id=artifact_id,
        operator=operator,
        step_index=step_index,
        data=data or {},
        status=ArtifactStatus.SUCCESS,
    )


def _make_run_result(artifacts: dict[str, Artifact] | None = None) -> RunResult:
    """Build a minimal RunResult for testing efficacy."""
    output = _make_artifact("dummy", "dummy", 0)
    return RunResult(
        output=output,
        status=RunResultStatus.SUCCESS,
        artifacts=artifacts,
    )


def test_efficacy_empty_artifacts():
    """compute_efficacy returns 0.0 when artifacts dict is None."""
    result = _make_run_result(artifacts=None)
    assert compute_efficacy(result) == 0.0


def test_efficacy_no_synthesize_artifact():
    """compute_efficacy returns 0.0 when no synthesize artifact exists."""
    artifacts = {
        "decompose_0": _make_artifact("decompose_0", "decompose", 0),
        "rotate_1": _make_artifact("rotate_1", "rotate", 1),
    }
    result = _make_run_result(artifacts=artifacts)
    assert compute_efficacy(result) == 0.0


def test_efficacy_empty_contributions():
    """compute_efficacy returns 0.0 when all incorporates have empty contributions."""
    synth_data = {
        "incorporates": [
            {"source_artifact_id": "decompose_0", "contribution": ""},
            {"source_artifact_id": "rotate_1", "contribution": "   "},
        ],
    }
    artifacts = {
        "decompose_0": _make_artifact("decompose_0", "decompose", 0),
        "rotate_1": _make_artifact("rotate_1", "rotate", 1),
        "synthesize_2": _make_artifact("synthesize_2", "synthesize", 2, synth_data),
    }
    result = _make_run_result(artifacts=artifacts)
    assert compute_efficacy(result) == 0.0


def test_efficacy_partial_contributions():
    """compute_efficacy returns 0.75 with 3 of 4 non-empty contributions."""
    synth_data = {
        "incorporates": [
            {"source_artifact_id": "rotate_1", "contribution": "Frame rotation insight"},
            {"source_artifact_id": "classify_2", "contribution": "Problem type"},
            {"source_artifact_id": "evaluate_3", "contribution": "Fitness judgment"},
        ],
    }
    artifacts = {
        "decompose_0": _make_artifact("decompose_0", "decompose", 0),
        "rotate_1": _make_artifact("rotate_1", "rotate", 1),
        "classify_2": _make_artifact("classify_2", "classify", 2),
        "evaluate_3": _make_artifact("evaluate_3", "evaluate", 3),
        "synthesize_4": _make_artifact("synthesize_4", "synthesize", 4, synth_data),
    }
    result = _make_run_result(artifacts=artifacts)
    assert compute_efficacy(result) == 0.75


def test_efficacy_full_contributions():
    """compute_efficacy returns 1.0 when all upstream artifacts have non-empty contributions."""
    synth_data = {
        "incorporates": [
            {"source_artifact_id": "decompose_0", "contribution": "Structure"},
            {"source_artifact_id": "rotate_1", "contribution": "Frame"},
        ],
    }
    artifacts = {
        "decompose_0": _make_artifact("decompose_0", "decompose", 0),
        "rotate_1": _make_artifact("rotate_1", "rotate", 1),
        "synthesize_2": _make_artifact("synthesize_2", "synthesize", 2, synth_data),
    }
    result = _make_run_result(artifacts=artifacts)
    assert compute_efficacy(result) == 1.0


def test_efficacy_archived_fixture():
    """compute_efficacy on the archived translate-lateral-shift run returns 0.75.

    The fixture has 5 artifacts: decompose_0, rotate_1, classify_2, evaluate_3,
    synthesize_4. Synthesize incorporates 3 of 4 upstream artifacts with non-empty
    contributions (decompose_0 is absent from incorporates).
    """
    fixture_path = _FIXTURES_DIR / "translate-lateral-shift-run.json"
    with open(fixture_path) as f:
        raw = json.load(f)

    # Reconstruct RunResult from fixture JSON
    artifacts = {}
    for aid, adata in raw["artifacts"].items():
        artifacts[aid] = Artifact(
            id=adata["id"],
            operator=adata["operator"],
            step_index=adata["step_index"],
            data=adata["data"],
            status=ArtifactStatus(adata["status"]),
        )
    result = RunResult(
        output=artifacts[raw["output"]] if isinstance(raw["output"], str) else Artifact(**raw["output"]),
        status=RunResultStatus(raw["status"]),
        artifacts=artifacts,
    )
    assert compute_efficacy(result) == 0.75
