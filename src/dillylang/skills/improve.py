"""Improve meta-skill: revise a recipe using translate output + analyze output.

Two phases:
  1. Pipeline: pipe(decompose, synthesize) -- 2 LLM calls
  2. Renderer: merge synthesize output into revised DillylangSkillDescription

Per D-01: works entirely in vocabulary space -- never touches raw skill files.
Per D-02: output is revised DillylangSkillDescription + structured change log.
Per D-04: no self-check -- the caller decides quality externally.
Per D-04b: stops at revised description; no vocab->files renderer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dillylang.combinators import bind, pipe
from dillylang.operators import DecomposeOperator, SynthesizeOperator
from dillylang.skills.design import _VOCABULARY_REFERENCE
from dillylang.runner.runner import PipelineRunner
from dillylang.vocab.schemas import (
    AnalysisReport,
    ChangeLogEntry,
    DillylangSkillDescription,
    ImproveOutput,
    ImproveSynthesizeOutput,
    StageMapping,
    VocabularyResidue,
)
from dillylang.vocab.types import (
    Artifact,
    ArtifactStatus,
    Budget,
    RunResult,
    RunResultStatus,
)


@dataclass
class ImproveResult:
    """Full improve output: revised description + change log + pipeline internals."""

    output: ImproveOutput
    run_result: RunResult


def prepare_improve_input(
    description: DillylangSkillDescription,
    analysis: AnalysisReport,
) -> Artifact:
    """Merge translate output + analyze output into a single pipeline input.

    Both models serialized into Artifact.data so decompose receives the
    full context: what the recipe IS (description) and what should CHANGE
    (analysis.improvements). Per D-01: works entirely in vocabulary space.
    """
    return Artifact(
        id="improve_input_0",
        operator="improve_input",
        step_index=0,
        data={
            "recipe_description": description.model_dump(),
            "analysis_report": analysis.model_dump(),
        },
        status=ArtifactStatus.SUCCESS,
    )


def _build_improve_pipeline() -> Any:
    """Compose the improve pipeline.

    Pipeline shape (D-03): pipe(decompose, synthesize). 2 LLM calls.
    Decompose breaks AnalysisReport improvements into atomic changes.
    Synthesize integrates atomic changes into a revised DillylangSkillDescription.
    """
    return pipe(
        bind(
            DecomposeOperator(),
            focus=(
                "Break the AnalysisReport improvements into atomic, independent changes. "
                "Each change should modify exactly one aspect of the recipe: add an operator, "
                "remove redundancy, restructure a combinator, adjust a binding, or fill an "
                "axis gap. For each atomic change, state: (1) what to change, (2) why "
                "(referencing the AnalysisReport improvement), (3) the before state, "
                "(4) the after state. The recipe_description in the input shows the current "
                "recipe; the analysis_report.improvements list what needs changing."
            ),
        ),
        bind(
            SynthesizeOperator(output_model=ImproveSynthesizeOutput),
            focus=(
                "Use ONLY operators and combinators from the Dillylang vocabulary "
                "when revising the recipe. Do not invent operator names or use axis "
                "names (feasibility, frame, etc.) as operators — use the operator "
                "that moves along that axis (constrain/relax for feasibility, "
                "rotate for frame).\n\n" + _VOCABULARY_REFERENCE
            ),
        ),
    )


def render_improve_output(
    result: RunResult,
    original_description: DillylangSkillDescription,
) -> ImproveOutput:
    """Project synthesize artifact into ImproveOutput with revised description.

    Deterministic renderer. Reads synthesize artifact data, overlays onto
    original description for fields that improve changes (pseudocode,
    operators, combinators, stage_mapping, residue, open_questions,
    confidence). Unchanged fields (activation_contract, execution_model,
    source_contract_*) carry over from original.
    """
    artifacts = result.artifacts or {}

    # Find synthesize artifact by operator prefix
    synthesize_data: dict[str, Any] = {}
    for artifact in artifacts.values():
        if artifact.operator.startswith("synthesize"):
            synthesize_data = artifact.data
            break

    # Extract revised recipe fields from synthesize output, with defaults
    revised_recipe = synthesize_data.get("revised_recipe", original_description.dillylang_pseudocode)
    revised_operators = synthesize_data.get("revised_operators", original_description.dillylang_operators)
    revised_combinators = synthesize_data.get("revised_combinators", original_description.dillylang_combinators)

    # Extract change log -- each entry maps to a ChangeLogEntry
    raw_change_log = synthesize_data.get("change_log", [])
    change_log = [
        ChangeLogEntry(
            field_changed=entry.get("field_changed", "unknown"),
            old_value=entry.get("old_value", ""),
            new_value=entry.get("new_value", ""),
            rationale=entry.get("rationale", ""),
            improvement_ref=entry.get("improvement_ref", ""),
        )
        for entry in raw_change_log
    ]

    # Extract optional overrides for structural fields
    raw_stage_mapping = synthesize_data.get("stage_mapping")
    stage_mapping = (
        [StageMapping.model_validate(sm) for sm in raw_stage_mapping]
        if raw_stage_mapping is not None
        else original_description.stage_mapping
    )

    raw_residue = synthesize_data.get("residue")
    residue = (
        [VocabularyResidue.model_validate(r) for r in raw_residue]
        if raw_residue is not None
        else original_description.residue
    )

    open_questions = synthesize_data.get("open_questions", original_description.open_questions)
    confidence = synthesize_data.get("confidence", original_description.confidence)

    # Build revised description: overlay changed fields onto original
    revised_description = DillylangSkillDescription(
        # Preserved from original (improve doesn't change these)
        skill_name=original_description.skill_name,
        skill_purpose=original_description.skill_purpose,
        activation_contract=original_description.activation_contract,
        execution_model=original_description.execution_model,
        recipe_shape=original_description.recipe_shape,
        source_contract_entrypoints=original_description.source_contract_entrypoints,
        source_contract_inputs=original_description.source_contract_inputs,
        source_contract_outputs=original_description.source_contract_outputs,
        source_contract_control_flow=original_description.source_contract_control_flow,
        # Revised by improve
        dillylang_pseudocode=revised_recipe,
        dillylang_operators=revised_operators,
        dillylang_combinators=revised_combinators,
        stage_mapping=stage_mapping,
        residue=residue,
        open_questions=open_questions,
        confidence=confidence,
    )

    return ImproveOutput(
        revised_description=revised_description,
        change_log=change_log,
    )


def improve(
    description: DillylangSkillDescription,
    analysis: AnalysisReport,
    budget: Budget | None = None,
) -> ImproveResult:
    """Improve a recipe using translate output + analyze output.

    Two phases:
      1. Pipeline: pipe(decompose, synthesize) -- 2 LLM calls
      2. Renderer: merge synthesize output into revised DillylangSkillDescription

    Per D-01: works entirely in vocabulary space -- never touches raw skill files.
    Per D-04: no self-check. The caller composes validation externally.
    Per D-04b: stops at revised DillylangSkillDescription + change log.

    Args:
        description: Output of translate -- the recipe to improve.
        analysis: Output of analyze -- structural improvements to apply.
        budget: Optional budget override. Default: 5 LLM calls.

    Returns:
        ImproveResult carrying the rendered ImproveOutput and the full
        pipeline RunResult (with per-step trace).

    Raises:
        RuntimeError: If the pipeline fails.
    """
    # Phase 1: merge both inputs into single artifact
    input_artifact = prepare_improve_input(description, analysis)

    # Phase 2: run pipeline (decompose + synthesize = 2 LLM calls)
    pipeline = _build_improve_pipeline()
    runner = PipelineRunner(budget=budget or Budget(max_llm_calls=5))
    run_result = runner.run(pipeline, input_artifact)

    if run_result.status == RunResultStatus.FAILED:
        msg = f"Improve pipeline failed: {run_result.errors}"
        raise RuntimeError(msg)

    # Phase 3: render output
    output = render_improve_output(run_result, description)

    return ImproveResult(output=output, run_result=run_result)
