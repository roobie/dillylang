"""Translate meta-skill: convert a Claude Code skill directory to a Dillylang recipe.

Three phases:
  1. Deterministic ingestion (no LLM) -- ingest_skill_directory
  2. 5-operator LLM pipeline: pipe(decompose, parallel(rotate, classify, evaluate), synthesize)
  3. Deterministic rendering (no LLM) -- render_dillylang_skill_description

Substrate-agnostic per D-05: composes vocabulary operators via combinators.
Refine topology: decompose first, then parallel(rotate, classify, evaluate),
then synthesize. 5 LLM calls within budget sweet spot.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
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
from dillylang.skills.ingest import ingest_skill_directory
from dillylang.vocab.schemas import (
    DillylangSkillDescription,
    StageMapping,
    TranslateSynthesizeOutput,
    VocabularyResidue,
)
from dillylang.vocab.types import (
    Artifact,
    Budget,
    RunResult,
    RunResultStatus,
)


@dataclass
class TranslateResult:
    """Full translate output: rendered description + pipeline internals."""

    description: DillylangSkillDescription
    run_result: RunResult
    source_artifact: Artifact


# Vocabulary reference injected into steering params so non-frontier models
# can ground their output in concrete operator/combinator names.
# Mirrors the approach of the Model C recipe runner's "read operator output
# fields before executing" pattern.
_VOCABULARY_REFERENCE = """\
Dillylang operator and combinator vocabulary — use ONLY these names:

OPERATORS (thinking moves that transform artifacts):
- decompose: break into axioms, derivations, assumptions
- synthesize: integrate multiple artifacts into coherent proposal
- invert: find what guarantees failure (Munger/Jacobi inversion)
- rotate: change the axis of inquiry or viewpoint
- analogize: find structural analogies in other domains
- abstract: extract general principles from concrete instances
- concretize: produce concrete instances from abstract principles
- constrain: narrow the solution space with explicit boundaries
- relax: widen the solution space by removing constraints
- evaluate: judge an artifact against an explicit criterion
- rank: order artifacts by criteria (returns IDs only)
- compare: side-by-side comparison of two artifacts
- classify: assign labels from taxonomies

COMBINATORS (compose operators into pipelines):
- pipe: sequential — output of step N feeds step N+1
- parallel: fan-out/fan-in — same input to multiple operators, collect results
- bind: typed currying — fix steering parameters at compose time
- map: apply an operator to each item in a collection
- filter: keep/drop items based on operator verdict (pass/partial=keep, fail=drop)
- branch: conditional dispatch — classify then route to sub-pipelines

A recipe is expressed as nested combinator calls, e.g.:
  pipe(parallel(decompose, invert, rotate), synthesize)

Each operator produces a typed artifact with specific fields. Map each stage \
of the input skill to the closest operator(s) and combinator structure."""


def _build_translate_pipeline() -> Any:
    """Compose the translate pipeline from vocabulary operators.

    Pipeline shape (refine topology — decompose first, then parallel analysis):
      pipe(
        bind(decompose, focus="..."),
        parallel(
          bind(rotate, target_frame=_VOCABULARY_REFERENCE, focus="..."),
          bind(classify, taxonomies={...}, focus="..."),
          bind(evaluate, criterion="...", focus="..."),
        ),
        SynthesizeOperator(),
      )

    5 LLM calls: 1 decompose + 3 parallel + 1 synthesize. Within budget.
    """
    return pipe(
        bind(
            DecomposeOperator(),
            focus=(
                "Decompose the skill's operational architecture — not its "
                "philosophical premise. Extract axioms about: how it triggers, "
                "what stages execute in what order, what typed inputs/outputs "
                "flow between stages, what hard dependencies gate execution, "
                "and what control flow decisions the skill makes. Each axiom "
                "should be specific enough to falsify against the skill's "
                "source text."
            ),
        ),
        parallel(
            bind(
                RotateOperator(),
                target_frame=_VOCABULARY_REFERENCE,
                focus=(
                    "The input is a structural decomposition (axioms, derivations, "
                    "assumptions) of a skill. Ground each rotation in specific axioms "
                    "from the input — name the axiom your restated_problem builds on. "
                    "Produce concrete Dillylang recipe fragments, not abstract reframings."
                ),
            ),
            bind(
                ClassifyOperator(),
                taxonomies={
                    "execution_model": [
                        "Model A",
                        "Model B",
                        "Model C",
                        "agentic",
                        "hybrid",
                    ],
                    "recipe_shape": [
                        "generative",
                        "evaluative",
                        "canonization",
                        "verification",
                        "orchestration",
                        "other",
                    ],
                },
                focus=(
                    "The input is a structural decomposition of a skill. Classify "
                    "the Dillylang recipe this skill would become when translated "
                    "into typed operators and combinators — not the skill's current "
                    "implementation. Reference specific axioms or derivations from "
                    "the input in your rationale."
                ),
            ),
            bind(
                EvaluateOperator(),
                criterion=(
                    "All load-bearing behavior in this skill is expressible using "
                    "Dillylang operators, combinators, artifacts, and execution-model "
                    "vocabulary without changing semantics. "
                    "Operators: decompose, synthesize, invert, rotate, analogize, "
                    "abstract, concretize, constrain, relax, evaluate, rank, compare, "
                    "classify. Combinators: pipe, parallel, bind, map, filter, branch."
                ),
                focus=(
                    "The input is a structural decomposition of a skill. Evaluate "
                    "translatability by checking each axiom and derivation against "
                    "the vocabulary — cite which specific axioms map cleanly and "
                    "which resist translation."
                ),
            ),
        ),
        SynthesizeOperator(output_model=TranslateSynthesizeOutput),
    )


def _find_artifact_data(
    artifacts: dict[str, Artifact], operator_prefix: str
) -> dict[str, Any]:
    """Find artifact data by operator name prefix. Returns empty dict if not found."""
    for _key, artifact in artifacts.items():
        if artifact.operator.startswith(operator_prefix):
            return artifact.data
    return {}


def render_dillylang_skill_description(
    result: Any,
    skill_name: str,
    source_artifact: Artifact | None = None,
) -> DillylangSkillDescription:
    """Project full artifact collection into DillylangSkillDescription.

    Deterministic post-pipeline renderer. Reads specific artifacts by operator
    name to populate typed fields. source_artifact provides ingestion data
    (entrypoints, detected features).

    Uses .get() with defaults throughout for resilience (T-03-07 mitigation).
    """
    artifacts = result.artifacts or {}
    source_data: dict[str, Any] = (
        source_artifact.data if source_artifact is not None else {}
    )

    # Find artifacts by operator name prefix
    classify_data = _find_artifact_data(artifacts, "classify")
    decompose_data = _find_artifact_data(artifacts, "decompose")
    rotate_data = _find_artifact_data(artifacts, "rotate")
    evaluate_data = _find_artifact_data(artifacts, "evaluate")
    synthesize_data = _find_artifact_data(artifacts, "synthesize")

    # Extract execution_model and recipe_shape from classify
    classifications = classify_data.get("classifications", [])
    execution_model = "unknown"
    recipe_shape = "unknown"
    for c in classifications:
        if c.get("taxonomy") == "execution_model":
            execution_model = c.get("label", "unknown")
        elif c.get("taxonomy") == "recipe_shape":
            recipe_shape = c.get("label", "unknown")

    # Extract source contract from ingestion bundle
    entrypoints_raw = source_data.get("entrypoints", [])
    source_contract_entrypoints = [
        e.get("command", str(e)) for e in entrypoints_raw
    ]
    source_contract_control_flow = source_data.get("detected_control_flow", [])

    # Extract inputs/outputs from decompose axioms+derivations
    source_contract_inputs: list[str] = []
    source_contract_outputs: list[str] = []
    for axiom in decompose_data.get("axioms", []):
        stmt = axiom.get("statement", "")
        if any(kw in stmt.lower() for kw in ("input", "reads", "receives", "accepts")):
            source_contract_inputs.append(stmt)
        if any(kw in stmt.lower() for kw in ("output", "produces", "returns", "writes")):
            source_contract_outputs.append(stmt)
    for deriv in decompose_data.get("derivations", []):
        claim = deriv.get("claim", "")
        if any(kw in claim.lower() for kw in ("input", "reads", "receives")):
            source_contract_inputs.append(claim)
        if any(kw in claim.lower() for kw in ("output", "produces", "returns")):
            source_contract_outputs.append(claim)

    # Extract pseudocode: prefer explicit dillylang_recipe field (TranslateSynthesizeOutput),
    # fall back to proposal.statement for backwards compat with older pipeline runs
    dillylang_pseudocode = synthesize_data.get(
        "dillylang_recipe", ""
    ) or synthesize_data.get("proposal", {}).get("statement", "")

    # Extract operators/combinators: prefer explicit structured fields from
    # TranslateSynthesizeOutput, fall back to string-matching extraction
    raw_operators = synthesize_data.get("recipe_operators") or _extract_operator_names(
        dillylang_pseudocode, rotate_data
    )
    raw_combinators = synthesize_data.get("recipe_combinators") or _extract_combinator_names(
        dillylang_pseudocode
    )
    # Filter to valid pantry names only (model may hallucinate)
    dillylang_operators = [op for op in raw_operators if op in _OPERATOR_NAMES]
    dillylang_combinators = [c for c in raw_combinators if c in _COMBINATOR_NAMES]

    # Extract stage_mapping from rotate rotations
    stage_mapping = _extract_stage_mappings(rotate_data)

    # Extract residue from evaluate evidence (partial/fail verdicts)
    residue = _extract_residue(evaluate_data)

    # Extract open_questions and confidence from synthesize
    open_questions = synthesize_data.get("open_questions", [])
    confidence = synthesize_data.get("confidence", "low")

    # Derive skill_purpose and activation_contract from decompose
    skill_purpose = _derive_purpose(decompose_data, source_data)
    activation_contract = _derive_activation(source_data, entrypoints_raw)

    return DillylangSkillDescription(
        skill_name=skill_name,
        skill_purpose=skill_purpose,
        activation_contract=activation_contract,
        execution_model=execution_model,
        recipe_shape=recipe_shape,
        source_contract_entrypoints=source_contract_entrypoints,
        source_contract_inputs=source_contract_inputs,
        source_contract_outputs=source_contract_outputs,
        source_contract_control_flow=source_contract_control_flow,
        dillylang_pseudocode=dillylang_pseudocode,
        dillylang_operators=dillylang_operators,
        dillylang_combinators=dillylang_combinators,
        stage_mapping=stage_mapping,
        residue=residue,
        open_questions=open_questions,
        confidence=confidence,
    )


# --- Private extraction helpers ---

# Known operator names for extraction
_OPERATOR_NAMES = {
    "decompose", "synthesize", "invert", "rotate", "analogize",
    "abstract", "concretize", "constrain", "relax",
    "evaluate", "rank", "compare", "classify",
}

# Known combinator names for extraction
_COMBINATOR_NAMES = {"pipe", "parallel", "bind", "map", "filter", "branch"}


def _extract_operator_names(
    pseudocode: str, rotate_data: dict[str, Any]
) -> list[str]:
    """Extract Dillylang operator names mentioned in pseudocode or rotate output."""
    found: set[str] = set()
    text = pseudocode.lower()
    for name in _OPERATOR_NAMES:
        if name in text:
            found.add(name)
    # Also check rotate rotations for operator mentions
    for rotation in rotate_data.get("rotations", []):
        restated = rotation.get("restated_problem", "").lower()
        for name in _OPERATOR_NAMES:
            if name in restated:
                found.add(name)
    return sorted(found)


def _extract_combinator_names(pseudocode: str) -> list[str]:
    """Extract Dillylang combinator names mentioned in pseudocode."""
    found: set[str] = set()
    text = pseudocode.lower()
    for name in _COMBINATOR_NAMES:
        if name in text:
            found.add(name)
    return sorted(found)


def _extract_stage_mappings(rotate_data: dict[str, Any]) -> list[StageMapping]:
    """Map rotate rotations to StageMapping objects."""
    mappings: list[StageMapping] = []
    for rotation in rotate_data.get("rotations", []):
        # Each rotation's restated_problem is the dillylang expression
        source = rotation.get("new_axis", "")
        expression = rotation.get("restated_problem", "")
        # Determine fit from rotation kind
        kind = rotation.get("rotation_kind", "axis_change")
        fit = "direct" if kind == "axis_change" else "approximate"
        mappings.append(
            StageMapping(
                source_stage=source,
                dillylang_expression=expression,
                fit=fit,
                notes="; ".join(rotation.get("what_becomes_visible", [])),
            )
        )
    return mappings


def _extract_residue(evaluate_data: dict[str, Any]) -> list[VocabularyResidue]:
    """Extract vocabulary residue from evaluate evidence on partial/fail verdicts."""
    residue: list[VocabularyResidue] = []
    verdict = evaluate_data.get("verdict", "pass")
    if verdict in ("partial", "fail"):
        for evidence_item in evaluate_data.get("evidence", []):
            residue.append(
                VocabularyResidue(
                    feature=evidence_item,
                    why_it_does_not_fit=evaluate_data.get("rationale", ""),
                    vocabulary_extension_signal=None,
                )
            )
    return residue


def _derive_purpose(
    decompose_data: dict[str, Any], source_data: dict[str, Any]
) -> str:
    """Derive skill purpose from decompose axioms or source path."""
    axioms = decompose_data.get("axioms", [])
    if axioms:
        return axioms[0].get("statement", "unknown purpose")
    return source_data.get("path", "unknown skill")


def _derive_activation(
    source_data: dict[str, Any], entrypoints: list[dict[str, str]]
) -> str:
    """Derive activation contract from entrypoints."""
    if entrypoints:
        commands = [e.get("command", "") for e in entrypoints]
        return f"Activated via: {', '.join(commands)}"
    return "activation unknown"


def translate(
    skill_path: str | Path, budget: Budget | None = None
) -> TranslateResult:
    """Translate a Claude Code skill directory to a Dillylang recipe description.

    Three phases:
      1. Deterministic ingestion (no LLM)
      2. 5-operator LLM pipeline: pipe(decompose, parallel(rotate, classify, evaluate), synthesize)
      3. Deterministic rendering (no LLM)

    Returns TranslateResult carrying the rendered description, the full
    pipeline RunResult (with per-step trace), and the source artifact.

    Args:
        skill_path: Path to a Claude Code skill directory containing SKILL.md.
        budget: Optional budget override. Default: 7 LLM calls.

    Raises:
        ValueError: If skill_path does not exist or SKILL.md is missing/truncated.
        RuntimeError: If the LLM pipeline fails.
    """
    # 1. Deterministic ingestion
    source_artifact = ingest_skill_directory(skill_path)
    if source_artifact.status.value == "failed":
        msg = f"Skill ingestion failed for {skill_path}"
        raise ValueError(msg)

    # 2. LLM pipeline
    pipeline = _build_translate_pipeline()
    runner = PipelineRunner(budget=budget or Budget(max_llm_calls=7))
    run_result = runner.run(pipeline, source_artifact)

    if run_result.status == RunResultStatus.FAILED:
        msg = f"Translate pipeline failed: {run_result.errors}"
        raise RuntimeError(msg)

    # 3. Deterministic rendering
    skill_name = Path(skill_path).name
    description = render_dillylang_skill_description(
        run_result, skill_name, source_artifact
    )

    return TranslateResult(
        description=description,
        run_result=run_result,
        source_artifact=source_artifact,
    )
