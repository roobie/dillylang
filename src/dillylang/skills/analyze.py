"""Analyze meta-skill: compute orthogonality metrics and structural quality judgment.

Two phases:
  1. Pipeline: pipe(compute_metrics_node, bind(evaluate, criterion="...")) -- 1 LLM call
  2. Renderer: merge metrics + evaluate output into typed AnalysisReport

Per D-04: operates on static recipe structure (DillylangSkillDescription from translate).
No pipeline execution needed. Efficacy metric deferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dillylang.combinators import bind, pipe
from dillylang.operators import EvaluateOperator
from dillylang.runner.runner import PipelineRunner
from dillylang.skills.metrics import compute_metrics
from dillylang.vocab.schemas import (
    AnalysisReport,
    DillylangSkillDescription,
    RecipeMetrics,
    StructuralImprovement,
)
from dillylang.vocab.types import (
    Artifact,
    ArtifactStatus,
    Budget,
    Context,
    RunResult,
    RunResultStatus,
)


@dataclass
class AnalyzeResult:
    """Full analyze output: rendered report + pipeline internals."""

    report: AnalysisReport
    run_result: RunResult


class ComputeMetricsNode:
    """Pipeline-compatible wrapper for compute_metrics.

    Sets is_combinator = True so execute_node routes via .run() directly,
    bypassing run_operator_with_retry (no budget deduction, no trace emission).
    This is architecturally honest: compute_metrics is a deterministic
    computation, not an LLM operator. See ADR-009 for rationale.
    """

    is_combinator = True

    @property
    def name(self) -> str:
        return "compute_metrics"

    def run(self, input: Any, ctx: Context) -> RunResult:
        """Extract DillylangSkillDescription from input, compute metrics, return as Artifact."""
        # Input is either an Artifact (whose .data contains description fields)
        # or the raw description data
        if isinstance(input, Artifact):
            desc_data = input.data
        elif isinstance(input, dict):
            desc_data = input
        else:
            desc_data = {}

        description = DillylangSkillDescription.model_validate(desc_data)
        metrics = compute_metrics(description)

        # Pass both recipe description and metrics to evaluate -- evaluate
        # needs the recipe context to judge quality, not just the numbers.
        artifact = Artifact(
            id=f"compute_metrics_{len(ctx.trace)}",
            operator="compute_metrics",
            step_index=len(ctx.trace),
            data={
                "metrics": metrics.model_dump(),
                "recipe_description": description.model_dump(),
            },
            status=ArtifactStatus.SUCCESS,
        )

        # Store in ctx.artifacts for renderer access
        ctx.artifacts[artifact.id] = artifact

        return RunResult(
            output=artifact,
            trace=[],
            status=RunResultStatus.SUCCESS,
        )


def _build_analyze_pipeline() -> Any:
    """Compose the analyze pipeline.

    Pipeline shape (from CONTEXT.md D-07):
      pipe(
        compute_metrics_node,                              # deterministic, no LLM call
        bind(evaluate, criterion="structural recipe quality: axis gaps,
             redundant operators, anti-patterns, improvement opportunities"),
      )

    1 LLM call (evaluate only). compute_metrics is deterministic.
    """
    return pipe(
        ComputeMetricsNode(),
        bind(
            EvaluateOperator(),
            criterion=(
                "structural recipe quality: axis gaps, redundant operators, "
                "anti-patterns, improvement opportunities. Consider coverage "
                "of orthogonal thinking axes, pipeline depth efficiency, and "
                "whether each operator contributes non-trivially to the output."
            ),
        ),
    )


def render_analysis_report(
    result: RunResult,
    recipe_name: str,
    metrics: RecipeMetrics,
) -> AnalysisReport:
    """Merge metrics and evaluate judgment into typed AnalysisReport.

    Deterministic renderer per D-07 and D-09. Same pattern as
    render_dillylang_skill_description in translate.
    """
    artifacts = result.artifacts or {}

    # Find evaluate artifact -- looks for operator name starting with "evaluate"
    evaluate_data: dict[str, Any] = {}
    for artifact in artifacts.values():
        if artifact.operator.startswith("evaluate"):
            evaluate_data = artifact.data
            break

    # Extract structural verdict from evaluate (defaults for missing data per T-03-10)
    verdict = evaluate_data.get("verdict", "fail")
    confidence = evaluate_data.get("confidence", "low")
    evidence = evaluate_data.get("evidence", [])
    rationale = evaluate_data.get("rationale", "")

    # Build improvements from metrics gaps + evaluate evidence
    improvements: list[StructuralImprovement] = []

    # Improvements from metrics gaps (missing axes)
    for axis in metrics.axes_missing:
        improvements.append(
            StructuralImprovement(
                category="gap",
                description=f"Recipe does not touch the {axis} axis",
                rationale=f"Adding a {axis}-axis operator could reveal blind spots",
            )
        )

    # Improvements from evaluate evidence
    for item in evidence:
        category = (
            "anti-pattern"
            if "redundant" in item.lower() or "anti" in item.lower()
            else "opportunity"
        )
        improvements.append(
            StructuralImprovement(
                category=category,
                description=item,
                rationale=rationale,
            )
        )

    # Terse summary per D-09
    total_axes = len(metrics.axes_touched) + len(metrics.axes_missing)
    summary = (
        f"{recipe_name}: coverage={metrics.coverage}/{total_axes}, "
        f"depth={metrics.depth}, cost={metrics.cost}, "
        f"cost_eff={metrics.cost_efficiency:.2f}, depth_eff={metrics.depth_efficiency:.2f}. "
        f"Verdict: {verdict}. "
        f"{len(improvements)} improvement(s) identified."
    )

    return AnalysisReport(
        recipe_name=recipe_name,
        metrics=metrics,
        structural_verdict=verdict,
        improvements=improvements,
        summary=summary,
        confidence=confidence,
    )


def analyze(
    description: DillylangSkillDescription,
    budget: Budget | None = None,
) -> AnalyzeResult:
    """Analyze a translated recipe for structural improvements.

    Two phases:
      1. Pipeline: compute_metrics (deterministic) -> evaluate (1 LLM call)
      2. Renderer: merge metrics + evaluate into AnalysisReport

    Returns AnalyzeResult carrying the rendered report and the full
    pipeline RunResult (with per-step trace).

    Args:
        description: Output of translate -- the recipe to analyze.
        budget: Optional budget override. Default: 7 LLM calls (only 1 used).

    Raises:
        RuntimeError: If the pipeline fails.
    """
    # Pre-compute metrics (needed for renderer, also flows through pipeline)
    metrics = compute_metrics(description)

    # Build input artifact from description
    input_artifact = Artifact(
        id="analyze_input_0",
        operator="analyze_input",
        step_index=0,
        data=description.model_dump(),
        status=ArtifactStatus.SUCCESS,
    )

    # Run pipeline
    pipeline = _build_analyze_pipeline()
    runner = PipelineRunner(budget=budget or Budget(max_llm_calls=7))
    run_result = runner.run(pipeline, input_artifact)

    if run_result.status == RunResultStatus.FAILED:
        msg = f"Analyze pipeline failed: {run_result.errors}"
        raise RuntimeError(msg)

    # Render report
    report = render_analysis_report(run_result, description.skill_name, metrics)

    return AnalyzeResult(report=report, run_result=run_result)
