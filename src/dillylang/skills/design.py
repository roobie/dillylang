"""Design meta-skill: compose a purpose-built Dillylang recipe from a goal.

Three phases:
  1. Deterministic ingestion -- create input artifact from goal text
  2. 5-operator LLM pipeline: pipe(decompose, parallel(classify, rotate, evaluate), synthesize)
  3. Deterministic rendering -- render_recipe_definition

Self-referential: uses Dillylang operators to reason about which Dillylang
operators to compose into a new recipe. The meta-recipe is fixed; its job is
to produce different object-level recipes for different goals.

Substrate-agnostic per D-05: composes vocabulary operators via combinators.
Pipeline shape per D-11 (design-recipe.PLAN.md): decompose first (unstructured
prose input needs structuring), then parallel characterization, then synthesize.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dillylang.combinators import bind, parallel, pipe
from dillylang.operators import (
    ClassifyOperator,
    DecomposeOperator,
    EvaluateOperator,
    RotateOperator,
    SynthesizeOperator,
)
from dillylang.runner.runner import PipelineRunner
from dillylang.vocab.schemas import (
    DesignSynthesizeOutput,
    RecipeDefinition,
    RecipeStage,
    RecipeStructure,
)
from dillylang.vocab.types import (
    Artifact,
    ArtifactStatus,
    Budget,
    RunResult,
    RunResultStatus,
)


@dataclass
class DesignResult:
    """Full design output: rendered recipe definition + pipeline internals."""

    definition: RecipeDefinition
    run_result: RunResult


# Vocabulary reference injected into steering params so the LLM grounds
# its output in concrete operator/combinator names. Shared concept with
# translate.py but duplicated here (~500 tokens) to avoid coupling.
# Per D-13: pantry knowledge is prompt-embedded, not discovered at runtime.
_VOCABULARY_REFERENCE = """\
Dillylang operator and combinator vocabulary -- use ONLY these names:

OPERATORS (thinking moves that transform artifacts):
- decompose: break into axioms, derivations, assumptions (axis: compositionality)
- synthesize: integrate multiple artifacts into coherent proposal (axis: compositionality)
- invert: find what guarantees failure, Munger/Jacobi inversion (axis: valence)
- rotate: change the axis of inquiry or viewpoint (axis: frame)
- analogize: find structural analogies in other domains (axis: substrate)
- abstract: extract general principles from concrete instances (axis: abstraction)
- concretize: produce concrete instances from abstract principles (axis: abstraction)
- constrain: narrow the solution space with explicit boundaries (axis: feasibility)
- relax: widen the solution space by removing constraints (axis: feasibility)
- evaluate: judge an artifact against an explicit criterion (judge, no axis)
- rank: order artifacts by criteria, returns IDs only (judge, no axis)
- compare: side-by-side comparison of two artifacts (judge, no axis)
- classify: assign labels from taxonomies (judge, no axis)

COMBINATORS (compose operators into pipelines):
- pipe: sequential -- output of step N feeds step N+1
- parallel: fan-out/fan-in -- same input to multiple operators, collect results
- bind: typed currying -- fix steering parameters at compose time
- map: apply an operator to each item in a collection
- filter: keep/drop items based on operator verdict (pass/partial=keep, fail=drop)
- branch: conditional dispatch -- classify then route to sub-pipelines

BUDGET CONSTRAINTS:
- Ceiling: 7 LLM calls per recipe
- Sweet spot: 4-5 calls
- A 3-call recipe is fine if it covers the goal
- Synthesis without curation past ~5 upstream artifacts is an anti-pattern
  (add rank or filter before synthesize)

ANTI-PATTERNS:
- Speculative operators (adding operators without requirements-backed justification)
- Pad-with-config-flags (making the recipe configurable instead of decisive)
- Synthesis without curation when > 5 upstream artifacts feed synthesize

KNOWN RECIPES (check before inventing new ones):
- refine: pipe(decompose, parallel(invert, rotate), synthesize) -- 4 calls
- wide_pass: pipe(decompose, parallel(analogize, invert, rotate), synthesize) -- 5 calls

A recipe is expressed as nested combinator calls, e.g.:
  pipe(parallel(decompose, invert, rotate), synthesize)"""


def _build_design_pipeline() -> Any:
    """Compose the design pipeline from vocabulary operators.

    Pipeline shape (decompose first since input is unstructured prose):
      pipe(
        bind(decompose, focus="..."),
        parallel(
          bind(classify, taxonomies={...}, focus="..."),
          bind(rotate, target_frame=_VOCABULARY_REFERENCE, focus="..."),
          bind(evaluate, criterion="...", focus="..."),
        ),
        SynthesizeOperator(output_model=DesignSynthesizeOutput),
      )

    5 LLM calls: 1 decompose + 3 parallel + 1 synthesize. Within budget.
    """
    return pipe(
        bind(
            DecomposeOperator(),
            focus=(
                "requirements, constraints, success criteria, assumptions "
                "about the problem"
            ),
        ),
        parallel(
            bind(
                ClassifyOperator(),
                taxonomies={
                    "problem_type": [
                        "decision",
                        "design",
                        "diagnosis",
                        "evaluation",
                        "exploration",
                        "strategy",
                    ],
                    "recipe_shape": [
                        "generative",
                        "evaluative",
                        "canonization",
                        "verification",
                        "other",
                    ],
                },
                focus=(
                    "Classify the decomposed goal by problem type and recipe "
                    "shape to determine which operators are structurally "
                    "relevant and what combinator structure to use"
                ),
            ),
            bind(
                RotateOperator(),
                target_frame=_VOCABULARY_REFERENCE,
                focus=(
                    "For each decomposed requirement, identify which "
                    "operator's axis-move serves it. Map requirements to "
                    "operator affordances. Produce concrete operator "
                    "selections, not abstract reframings."
                ),
            ),
            bind(
                EvaluateOperator(),
                criterion=(
                    "An existing Dillylang recipe (refine, wide_pass, or a "
                    "named pattern) already serves this goal's requirements "
                    "without modification or with only bind-level "
                    "customization."
                ),
                focus=(
                    "Evaluate whether an existing recipe already solves "
                    "this goal. Check refine (4 calls: decompose -> "
                    "parallel(invert, rotate) -> synthesize) and wide_pass "
                    "(5 calls: decompose -> parallel(analogize, invert, "
                    "rotate) -> synthesize) first."
                ),
            ),
        ),
        SynthesizeOperator(output_model=DesignSynthesizeOutput),
    )


def _find_artifact_data(
    artifacts: dict[str, Artifact], operator_prefix: str
) -> dict[str, Any]:
    """Find artifact data by operator name prefix. Returns empty dict if not found."""
    for _key, artifact in artifacts.items():
        if artifact.operator.startswith(operator_prefix):
            return artifact.data
    return {}


def render_recipe_definition(result: RunResult) -> RecipeDefinition:
    """Deterministic post-pipeline renderer: project artifact fields into RecipeDefinition.

    Every field is either a direct read from a typed artifact field or a
    trivial computation. No pseudocode parsing. No prose extraction.
    All field access uses .get() with safe defaults (T-03b-04 mitigation).
    """
    artifacts = result.artifacts or {}

    # Find artifacts by operator name prefix
    classify_data = _find_artifact_data(artifacts, "classify")
    rotate_data = _find_artifact_data(artifacts, "rotate")
    evaluate_data = _find_artifact_data(artifacts, "evaluate")
    synthesize_data = _find_artifact_data(artifacts, "synthesize")

    # Extract recipe_structure from synthesize (DesignSynthesizeOutput extension)
    recipe_structure = synthesize_data.get("recipe_structure", {})

    # Extract classify labels for recipe_shape and problem_type
    classifications = classify_data.get("classifications", [])
    recipe_shape = "unknown"
    shape_choice_rationale = ""
    for c in classifications:
        if c.get("taxonomy") == "recipe_shape":
            recipe_shape = c.get("label", "unknown")
        elif c.get("taxonomy") == "problem_type":
            shape_choice_rationale = c.get("rationale", "")

    # Map rotate rotations to operator selection entries
    rotations = rotate_data.get("rotations", [])
    operator_selection = [
        {
            "operator": r.get("new_axis", "unknown"),
            "included": True,
            "reason": r.get("restated_problem", ""),
        }
        for r in rotations
    ]

    # Extract existing recipe fit from evaluate
    evaluate_verdict = evaluate_data.get("verdict", "fail")
    evaluate_evidence = evaluate_data.get("evidence", [])
    evaluate_rationale = evaluate_data.get("rationale", "")

    # Derive closest existing recipe from evaluate evidence when pass/partial
    closest_recipe: str | None = None
    if evaluate_verdict in ("pass", "partial") and evaluate_evidence:
        # Use first evidence item as the closest recipe reference
        closest_recipe = evaluate_evidence[0] if evaluate_evidence else None

    # Extract pipeline stages from recipe_structure
    raw_stages = recipe_structure.get("stages", [])
    pipeline_stages = [
        RecipeStage(
            operator=s.get("operator", "unknown"),
            role=s.get("role", ""),
            bindings=s.get("bindings", {}),
            axis=s.get("axis"),
        )
        for s in raw_stages
    ]

    # Compute metrics
    axes = recipe_structure.get("axes", [])
    cost = recipe_structure.get("cost", 0)
    depth = recipe_structure.get("depth", 0)
    coverage = len(axes)
    efficiency = coverage / cost if cost > 0 else 0.0

    return RecipeDefinition(
        recipe_name=recipe_structure.get("name", "unnamed"),
        recipe_purpose=recipe_structure.get("purpose", ""),
        recipe_shape=recipe_shape,
        pipeline_definition=recipe_structure.get("definition", ""),
        pipeline_stages=pipeline_stages,
        metrics_cost=cost,
        metrics_depth=depth,
        metrics_coverage=coverage,
        metrics_efficiency=efficiency,
        metrics_axes=axes,
        design_rationale_shape_choice=shape_choice_rationale,
        design_rationale_operator_selection=operator_selection,
        existing_recipe_fit_closest=closest_recipe,
        existing_recipe_fit_verdict=evaluate_verdict,
        existing_recipe_fit_delta=evaluate_rationale or None,
        caveats=synthesize_data.get("open_questions", []),
        confidence=synthesize_data.get("confidence", "low"),
    )


def design(goal: str, budget: Budget | None = None) -> DesignResult:
    """Design a purpose-built Dillylang recipe from a goal description.

    Three phases:
      1. Deterministic ingestion -- create input artifact from goal text
      2. 5-operator LLM pipeline: pipe(decompose, parallel(classify, rotate,
         evaluate), synthesize)
      3. Deterministic rendering -- project artifacts into RecipeDefinition

    Returns DesignResult carrying the rendered definition and the full
    pipeline RunResult (with per-step trace).

    Args:
        goal: Natural-language problem statement or decision prompt.
        budget: Optional budget override. Default: 7 LLM calls.

    Raises:
        RuntimeError: If the LLM pipeline fails.
    """
    # Phase 1: Deterministic ingestion -- create input artifact
    input_artifact = Artifact(
        id="design_input_0",
        operator="design_input",
        step_index=0,
        data={"goal": goal},
        status=ArtifactStatus.SUCCESS,
    )

    # Phase 2: LLM pipeline
    pipeline = _build_design_pipeline()
    runner = PipelineRunner(budget=budget or Budget(max_llm_calls=7))
    run_result = runner.run(pipeline, input_artifact)

    if run_result.status == RunResultStatus.FAILED:
        msg = f"Design pipeline failed: {run_result.errors}"
        raise RuntimeError(msg)

    # Phase 3: Deterministic rendering
    definition = render_recipe_definition(run_result)

    return DesignResult(definition=definition, run_result=run_result)
