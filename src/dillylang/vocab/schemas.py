"""Operator input/output schemas for all operators.

Pure Pydantic models defining the structured I/O contracts. Operators
with steering parameters (focus, target_frame, criterion, criteria/top_k,
taxonomies, domains) get Input models. All operators get Output models.

Zero DSPy imports -- the adapter boundary is in dillylang.operators.

Schema sources:
  - spec/INDEX.md section 6 (output schemas)
  - ADR-005 (classify operator schema)
  - ADR-007 (steering parameter input schemas)
  - ADR-006 (synthesize base integration contract)
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import AliasChoices, BaseModel, BeforeValidator, Field


def _normalize_literal(value: Any, valid: set[str]) -> Any:
    """Normalize mechanical string variations to match Literal values.

    Handles case, whitespace, hyphens/underscores/spaces interchangeably.
    Returns the original value unchanged if no match — Pydantic's Literal
    check then fails loud.
    """
    if not isinstance(value, str):
        return value
    # Canonical form: lowercase, strip, collapse whitespace, normalize separators
    canon = re.sub(r"[\s_-]+", "_", value.strip().lower())
    for v in valid:
        if canon == v:
            return v
    return value


_RESOLUTION_VALUES = {"resolved", "deferred", "accepted_as_tradeoff"}
_CONFIDENCE_VALUES = {"low", "medium", "high"}
_SEVERITY_VALUES = {"recoverable", "costly", "fatal"}
_ROTATION_KIND_VALUES = {"axis_change", "viewpoint_change"}
_VERDICT_VALUES = {"pass", "partial", "fail"}

NormalizedResolution = Annotated[
    Literal["resolved", "deferred", "accepted_as_tradeoff"],
    BeforeValidator(lambda v: _normalize_literal(v, _RESOLUTION_VALUES)),
]
NormalizedConfidence = Annotated[
    Literal["low", "medium", "high"],
    BeforeValidator(lambda v: _normalize_literal(v, _CONFIDENCE_VALUES)),
]
NormalizedSeverity = Annotated[
    Literal["recoverable", "costly", "fatal"],
    BeforeValidator(lambda v: _normalize_literal(v, _SEVERITY_VALUES)),
]
NormalizedRotationKind = Annotated[
    Literal["axis_change", "viewpoint_change"],
    BeforeValidator(lambda v: _normalize_literal(v, _ROTATION_KIND_VALUES)),
]
NormalizedVerdict = Annotated[
    Literal["pass", "partial", "fail"],
    BeforeValidator(lambda v: _normalize_literal(v, _VERDICT_VALUES)),
]


# --- decompose (spec section 6 + ADR-007) ---


class DecomposeInput(BaseModel):
    """Steering parameters for decompose. Data arrives via pipeline."""

    focus: str | None = Field(
        default=None,
        description="structural aspects to focus decomposition on",
    )


class Axiom(BaseModel):
    """A foundational statement not derivable from other statements."""

    # Non-frontier models may omit justification or use "reasoning"/"rationale".
    statement: str = Field(description="the axiom itself")
    justification: str = Field(
        default="",
        description="why this is foundational",
        validation_alias=AliasChoices("justification", "reasoning", "rationale"),
    )


class Derivation(BaseModel):
    """A claim that follows from axioms or other derivations."""

    model_config = {"populate_by_name": True}

    # Non-frontier models use "conclusion" for claim, "premises" for depends_on.
    claim: str = Field(
        description="the derived claim",
        validation_alias=AliasChoices("claim", "conclusion"),
    )
    depends_on: list[str] = Field(
        description="axiom/derivation statements this depends on",
        validation_alias=AliasChoices("depends_on", "premises"),
    )


class Assumption(BaseModel):
    """Something treated as true without justification."""

    statement: str = Field(description="the assumption")
    load_bearing: bool = Field(
        default=True,
        description="whether the conclusion depends on this",
    )
    testable: str = Field(
        default="",
        description="how this assumption could be tested or falsified",
    )


class DecomposeOutput(BaseModel):
    """Structural decomposition into axioms, derivations, and assumptions."""

    axioms: list[Axiom] = Field(description="foundational, non-derivable statements")
    derivations: list[Derivation] = Field(description="claims following from axioms")
    assumptions: list[Assumption] = Field(description="unverified premises")


# --- synthesize (spec section 6 + ADR-006) ---


class Incorporation(BaseModel):
    """How a specific upstream artifact contributed to synthesis."""

    source_artifact_id: str = Field(description="id of the upstream artifact")
    contribution: str = Field(description="what this artifact contributed")


class Tradeoff(BaseModel):
    """An explicit tradeoff made during synthesis."""

    gained: str = Field(description="what was gained")
    given_up: str = Field(description="what was given up")


class ConflictResolution(BaseModel):
    """How a conflict between upstream artifacts was handled."""

    conflict: str = Field(description="description of the conflict")
    resolution: NormalizedResolution = Field(
        description="exactly one of: resolved, deferred, accepted_as_tradeoff"
    )


class Proposal(BaseModel):
    """The core synthesis output."""

    statement: str = Field(description="the synthesized proposal")
    rationale: str = Field(description="why this synthesis, not another")


class SynthesizeOutput(BaseModel):
    """Integration of upstream artifacts into a coherent whole.

    The six base fields form the minimum integration contract (ADR-006).
    Extensions add domain-specific payload as additive top-level keys.
    """

    proposal: Proposal = Field(description="the synthesized proposal")
    incorporates: list[Incorporation] = Field(
        description="how each upstream artifact contributed"
    )
    tradeoffs: list[Tradeoff] = Field(description="explicit tradeoffs made")
    open_questions: list[str] = Field(description="unresolved questions deferred for later")
    conflicts_addressed: list[ConflictResolution] = Field(
        description="conflicts between upstream artifacts and their resolution"
    )
    confidence: NormalizedConfidence = Field(
        description="exactly one of: low, medium, high"
    )


# --- invert (spec section 6) ---


class FailureMode(BaseModel):
    """A specific way something can fail, with causal mechanism."""

    mode: str = Field(description="the failure mode")
    mechanism: str = Field(description="concrete causal mechanism")
    likelihood: NormalizedConfidence = Field(
        description="exactly one of: low, medium, high"
    )
    severity: NormalizedSeverity = Field(
        description="exactly one of: recoverable, costly, fatal"
    )
    preventable_by: str = Field(description="what would prevent this failure")


class InvertOutput(BaseModel):
    """Munger/Jacobi inversion: what guarantees failure."""

    anti_goals: list[str] = Field(description="inverted goals -- what to avoid")
    failure_modes: list[FailureMode] = Field(
        description="specific failure scenarios with mechanisms"
    )
    near_misses: list[str] = Field(
        description="things that almost fail but don't -- boundary conditions"
    )


# --- rotate (spec section 6 + ADR-007) ---


class RotateInput(BaseModel):
    """Steering parameters for rotate. Data arrives via pipeline."""

    target_frame: str | None = Field(
        default=None,
        description="frame of reference to rotate toward",
    )
    focus: str | None = Field(
        default=None,
        description="what to rotate and how — frames the rotation task when the input needs contextual grounding",
    )


class Rotation(BaseModel):
    """A single frame rotation with what it reveals and obscures."""

    new_axis: str = Field(description="the new axis of inquiry")
    rotation_kind: NormalizedRotationKind = Field(
        description="exactly one of: axis_change, viewpoint_change"
    )
    restated_problem: str = Field(description="problem restated from the new frame")
    what_becomes_visible: list[str] = Field(description="what this frame reveals")
    what_recedes: list[str] = Field(description="what this frame obscures")


class RotateOutput(BaseModel):
    """Frame rotation: changing the axis of inquiry."""

    original_axis: str = Field(description="the original frame of reference")
    rotations: list[Rotation] = Field(description="alternative frames explored")


# --- analogize (spec section 6) ---


class Analogy(BaseModel):
    """A structural mapping to another domain."""

    domain: str = Field(description="the source domain of the analogy")
    analog: str = Field(description="the analog in the source domain")
    mechanism_mapping: str = Field(description="how the mechanism transfers")
    transferable_insight: str = Field(description="what insight transfers")
    stowaways: list[str] = Field(
        description="what about the source domain does NOT transfer cleanly"
    )


class AnalogizeOutput(BaseModel):
    """Cross-domain structural analogy with stowaway detection."""

    problem_signature: str = Field(description="structural signature of the problem")
    analogies: list[Analogy] = Field(description="structural analogies found")


class AnalogizeInput(BaseModel):
    """Steering parameters for analogize. Domains is optional.

    When bound, constrains analogy search to specified source domains.
    When unbound (None), analogize searches freely across domains.
    Formalized per ADR-007 table (downstream from rotate/decompose pattern).
    """

    domains: list[str] | None = Field(
        default=None,
        description="source domains to search for structural analogies",
    )


# --- evaluate (spec section 6 + ADR-007 note) ---


class EvaluateInput(BaseModel):
    """Steering parameters for evaluate. Criterion is REQUIRED.

    Unlike focus/target_frame, criterion has no sensible default --
    evaluate without a criterion is invalid (ADR-007).
    """

    criterion: str = Field(description="the criterion to judge the artifact against")
    focus: str | None = Field(
        default=None,
        description="what to evaluate and how — frames the evaluation task when the input needs contextual grounding",
    )


class EvaluateOutput(BaseModel):
    """Judgment of an artifact against an explicit criterion."""

    verdict: NormalizedVerdict = Field(
        description="exactly one of: pass, partial, fail (pass=keep, partial=keep, fail=drop)"
    )
    evidence: list[str] = Field(description="evidence supporting the verdict")
    rationale: str = Field(description="reasoning behind the verdict")
    confidence: NormalizedConfidence = Field(
        description="exactly one of: low, medium, high"
    )


# --- rank (spec section 6) ---


class RankInput(BaseModel):
    """Input parameters for rank operator."""

    criteria: list[str] = Field(description="criteria to rank against")
    top_k: int | None = Field(default=None, description="return only top K; None=all")


class RankScores(BaseModel):
    """Per-artifact scores across all criteria."""

    artifact_id: str = Field(description="id of the ranked artifact (IDs only, not full artifacts)")
    scores: dict[str, NormalizedConfidence] = Field(
        description="scores per criterion, each exactly one of: high, medium, low"
    )
    rationale: str = Field(description="reasoning for this ranking")


class RankOutput(BaseModel):
    """Ordered ranking of artifacts by named criteria.

    The LLM returns IDs only -- never full artifacts. The runtime
    resolves IDs to original artifacts from context.
    """

    ranked: list[RankScores] = Field(description="artifacts in ranked order")
    top_k_ids: list[str] = Field(description="top-K artifact IDs")


# --- classify (ADR-005) ---


class ClassifyInput(BaseModel):
    """Steering parameters for classify. Taxonomies is REQUIRED.

    Each taxonomy maps a name to valid labels. The operator assigns
    exactly one label per taxonomy (ADR-005: single-label per taxonomy).
    Taxonomies without exhaustive coverage should include an escape
    label ("other", "unknown") -- the operator enforces closed-set labels.
    """

    taxonomies: dict[str, list[str]] = Field(
        description="mapping from taxonomy name to list of valid labels",
    )
    focus: str | None = Field(
        default=None,
        description="what to classify — frames the classification target when it differs from the raw input data",
    )


class Classification(BaseModel):
    """A single classification result for one taxonomy."""

    taxonomy: str = Field(description="which taxonomy this classification is for")
    label: str = Field(description="the assigned label from the taxonomy")
    rationale: str = Field(description="reasoning for choosing this label")
    confidence: NormalizedConfidence = Field(
        description="exactly one of: low, medium, high"
    )


class ClassifyOutput(BaseModel):
    """Structured label assignments from provided taxonomies.

    One Classification per taxonomy in the input. Rationale and confidence
    required on each (ADR-005: judge-operator precedent).
    """

    classifications: list[Classification] = Field(
        description="one classification per taxonomy",
    )


# --- abstract (abstraction axis up, no Input model per ADR-007) ---


class Principle(BaseModel):
    """A general principle extracted from concrete instances."""

    statement: str = Field(description="the general principle")
    grounding: list[str] = Field(
        description="concrete instances this was derived from"
    )
    abstraction_level: str = Field(
        description="how abstract this principle is relative to the input"
    )


class AbstractOutput(BaseModel):
    """General principles extracted from concrete instances."""

    principles: list[Principle] = Field(description="general principles found")
    source_pattern: str = Field(
        description="the structural pattern connecting the concrete instances"
    )


# --- concretize (abstraction axis down, no Input model per ADR-007) ---


class Instance(BaseModel):
    """A concrete instance derived from abstract principles."""

    description: str = Field(description="the concrete instance")
    derivation: str = Field(
        description="how this was derived from the abstract principle"
    )
    constraints_applied: list[str] = Field(
        description="domain constraints that shaped this instance"
    )


class ConcretizeOutput(BaseModel):
    """Concrete instances derived from abstract principles."""

    instances: list[Instance] = Field(description="concrete instances generated")
    target_domain: str = Field(
        description="the domain these instances are grounded in"
    )


# --- constrain (feasibility axis narrow, no Input model per ADR-007) ---


class AddedConstraint(BaseModel):
    """A constraint added to narrow the solution space."""

    constraint: str = Field(description="the constraint statement")
    justification: str = Field(description="why this constraint helps")
    impact: str = Field(description="how this narrows the solution space")


class ConstrainOutput(BaseModel):
    """Tightened constraints on a problem or artifact.

    Reuses existing Tradeoff model from synthesize (same gained/given_up structure).
    """

    constraints_added: list[AddedConstraint] = Field(
        description="new constraints introduced"
    )
    impact_on_solution_space: str = Field(
        description="overall effect on the solution space"
    )
    tradeoffs: list[Tradeoff] = Field(
        description="tradeoffs from adding these constraints"
    )


# --- relax (feasibility axis wide, no Input model per ADR-007) ---


class RelaxedConstraint(BaseModel):
    """A constraint removed or loosened."""

    original_constraint: str = Field(
        description="the constraint that was relaxed"
    )
    relaxation: str = Field(description="how the constraint was loosened")
    justification: str = Field(description="why relaxing this is acceptable")


class RelaxOutput(BaseModel):
    """Loosened constraints on a problem or artifact."""

    constraints_removed: list[RelaxedConstraint] = Field(
        description="constraints relaxed or removed"
    )
    new_possibilities: list[str] = Field(
        description="what becomes possible after relaxation"
    )
    risks_introduced: list[str] = Field(
        description="risks from removing these constraints"
    )


# --- compare (pairwise artifact comparison) ---


class CompareInput(BaseModel):
    """Steering parameters for compare. Criterion is REQUIRED.

    Like evaluate's criterion, compare's criterion has no sensible default --
    comparison without a criterion is invalid.
    """

    criterion: str = Field(
        description="the criterion to compare the two artifacts on"
    )


class ComparisonPoint(BaseModel):
    """A specific dimension of comparison between two artifacts."""

    dimension: str = Field(description="what aspect is being compared")
    artifact_a_assessment: str = Field(
        description="how artifact A performs on this dimension"
    )
    artifact_b_assessment: str = Field(
        description="how artifact B performs on this dimension"
    )


class CompareOutput(BaseModel):
    """Pairwise comparison of two artifacts on a criterion."""

    criterion: str = Field(description="the criterion compared on")
    winner: str = Field(
        description="id of the artifact that is stronger on this criterion, or 'tie'"
    )
    rationale: str = Field(description="reasoning for the verdict")
    comparison_points: list[ComparisonPoint] = Field(
        description="dimension-by-dimension comparison"
    )
    confidence: NormalizedConfidence = Field(
        description="exactly one of: low, medium, high"
    )


# --- meta-skills (translate + analyze, Phase 3a) ---

_SKILL_FILE_KIND_VALUES = {
    "skill_md", "readme", "claude_md", "script", "prompt", "config", "other"
}
NormalizedSkillFileKind = Annotated[
    Literal["skill_md", "readme", "claude_md", "script", "prompt", "config", "other"],
    BeforeValidator(lambda v: _normalize_literal(v, _SKILL_FILE_KIND_VALUES)),
]

_INGESTION_STATUS_VALUES = {"success", "partial", "failed"}
NormalizedIngestionStatus = Annotated[
    Literal["success", "partial", "failed"],
    BeforeValidator(lambda v: _normalize_literal(v, _INGESTION_STATUS_VALUES)),
]

_FIT_VALUES = {"direct", "approximate", "outside_vocabulary"}
NormalizedFit = Annotated[
    Literal["direct", "approximate", "outside_vocabulary"],
    BeforeValidator(lambda v: _normalize_literal(v, _FIT_VALUES)),
]


class SkillFile(BaseModel):
    """A single file from a skill directory, classified by kind."""

    path: str = Field(description="relative path within the skill directory")
    kind: NormalizedSkillFileKind = Field(
        description="file role: skill_md, readme, claude_md, script, prompt, config, other"
    )
    content: str = Field(description="full text content of the file")


class TruncationInfo(BaseModel):
    """Tracks whether ingestion truncated content. Per D-12: visible, not silent."""

    occurred: bool = Field(default=False, description="whether any truncation happened")
    files_dropped: list[str] = Field(
        default_factory=list, description="paths of files dropped due to limits"
    )
    bytes_dropped: int = Field(default=0, description="total bytes dropped")
    reason: str = Field(default="", description="why truncation occurred")


class SkillSourceBundle(BaseModel):
    """Ingested skill directory: all files, detected structure, truncation status.

    Per D-03, D-11, D-12: typed contract for translate's input boundary.
    """

    path: str = Field(description="root path of the skill directory")
    files: list[SkillFile] = Field(description="all ingested files")
    entrypoints: list[dict[str, str]] = Field(
        default_factory=list, description="detected entrypoint mappings"
    )
    detected_scripts: list[str] = Field(
        default_factory=list, description="script files found"
    )
    detected_prompts: list[str] = Field(
        default_factory=list, description="prompt files found"
    )
    detected_tools: list[str] = Field(
        default_factory=list, description="tool-use indicators found"
    )
    detected_control_flow: list[str] = Field(
        default_factory=list, description="control flow patterns found"
    )
    ingestion_status: NormalizedIngestionStatus = Field(
        description="success, partial, or failed"
    )
    truncation: TruncationInfo = Field(
        default_factory=TruncationInfo, description="truncation details if any"
    )


class StageMapping(BaseModel):
    """Maps a source skill stage to a Dillylang expression with fit quality."""

    source_stage: str = Field(description="stage name from the original skill")
    dillylang_expression: str = Field(
        description="equivalent Dillylang operator/combinator expression"
    )
    fit: NormalizedFit = Field(
        description="how well the mapping fits: direct, approximate, outside_vocabulary"
    )
    notes: str = Field(default="", description="additional context about the mapping")


class VocabularyResidue(BaseModel):
    """A skill feature that doesn't map cleanly to Dillylang vocabulary."""

    feature: str = Field(description="the skill feature that doesn't fit")
    why_it_does_not_fit: str = Field(description="explanation of the vocabulary gap")
    vocabulary_extension_signal: str | None = Field(
        default=None, description="signal for potential vocabulary extension"
    )


class DillylangSkillDescription(BaseModel):
    """Complete translation of a skill into Dillylang vocabulary.

    Per D-03: typed output of the translate meta-skill. Contains the full
    recipe description, stage mappings, residue, and confidence assessment.
    """

    skill_name: str = Field(description="name of the translated skill")
    skill_purpose: str = Field(description="one-line purpose of the skill")
    activation_contract: str = Field(description="when/how the skill activates")
    execution_model: str = Field(description="how the skill executes (sequential, parallel, etc.)")
    recipe_shape: str = Field(description="high-level recipe structure description")
    source_contract_entrypoints: list[str] = Field(
        description="entrypoints from the source skill"
    )
    source_contract_inputs: list[str] = Field(
        description="inputs the source skill expects"
    )
    source_contract_outputs: list[str] = Field(
        description="outputs the source skill produces"
    )
    source_contract_control_flow: list[str] = Field(
        description="control flow patterns in the source skill"
    )
    dillylang_pseudocode: str = Field(
        description="recipe expressed in Dillylang pseudocode notation"
    )
    dillylang_operators: list[str] = Field(
        description="operators used in the recipe"
    )
    dillylang_combinators: list[str] = Field(
        description="combinators used in the recipe"
    )
    stage_mapping: list[StageMapping] = Field(
        description="per-stage mapping from source to Dillylang"
    )
    residue: list[VocabularyResidue] = Field(
        description="features that don't map to current vocabulary"
    )
    open_questions: list[str] = Field(
        description="unresolved questions about the translation"
    )
    confidence: NormalizedConfidence = Field(
        description="overall translation confidence: low, medium, high"
    )


class TranslateSynthesizeOutput(SynthesizeOutput):
    """Extended synthesize output for the translate meta-skill (ADR-006 compliant).

    Adds explicit recipe fields so the LLM produces structured Dillylang
    output rather than relying on string-matching operator names in free text.
    """

    dillylang_recipe: str = Field(
        description=(
            "the skill expressed as a Dillylang recipe using nested combinator "
            "calls, e.g. pipe(parallel(decompose, rotate, invert), synthesize). "
            "Use ONLY valid operator names: decompose, synthesize, invert, rotate, "
            "analogize, abstract, concretize, constrain, relax, evaluate, rank, "
            "compare, classify. Use ONLY valid combinator names: pipe, parallel, "
            "bind, map, filter, branch."
        )
    )
    recipe_operators: list[str] = Field(
        description=(
            "operators used in the recipe, from this set ONLY: decompose, "
            "synthesize, invert, rotate, analogize, abstract, concretize, "
            "constrain, relax, evaluate, rank, compare, classify"
        )
    )
    recipe_combinators: list[str] = Field(
        description=(
            "combinators used in the recipe, from this set ONLY: pipe, "
            "parallel, bind, map, filter, branch"
        )
    )


class RecipeMetrics(BaseModel):
    """Static orthogonality metrics computable from recipe structure.

    Per D-06, D-10: depth = critical path (tree height), cost = total LLM calls,
    efficiency ratios measure coverage relative to resource consumption.
    """

    coverage: int = Field(description="distinct orthogonal axes touched")
    depth: int = Field(description="sequential move count (critical path / tree height)")
    cost: int = Field(description="total LLM calls in the recipe")
    cost_efficiency: float = Field(description="coverage / cost")
    depth_efficiency: float = Field(description="coverage / depth")
    axes_touched: list[str] = Field(description="which axes the recipe touches")
    axes_missing: list[str] = Field(description="axes not covered by the recipe")


class StructuralImprovement(BaseModel):
    """A concrete structural improvement suggestion. Per D-09."""

    category: str = Field(description="improvement category (e.g. axis_gap, redundancy)")
    description: str = Field(description="what to improve")
    rationale: str = Field(description="why this improvement matters")


class AnalysisReport(BaseModel):
    """Typed output of the analyze meta-skill.

    Per D-03, D-09: machine-readable metrics + human-readable summary.
    Downstream consumer is the improve skill in Phase 3b.
    """

    recipe_name: str = Field(description="name of the analyzed recipe")
    metrics: RecipeMetrics = Field(description="static orthogonality metrics")
    structural_verdict: NormalizedVerdict = Field(
        description="overall structural quality: pass, partial, fail"
    )
    improvements: list[StructuralImprovement] = Field(
        description="concrete structural improvement suggestions"
    )
    summary: str = Field(description="terse natural-language summary of the analysis")
    confidence: NormalizedConfidence = Field(
        description="analysis confidence: low, medium, high"
    )


# --- meta-skills (design + improve, Phase 3b) ---


class RecipeStage(BaseModel):
    """A single stage in a Dillylang recipe pipeline.

    Each stage maps an operator to its role, optional steering parameter
    bindings, and the thinking axis it touches (if any).
    """

    operator: str = Field(description="operator name from the pantry")
    role: str = Field(description="what this operator does in the recipe")
    bindings: dict[str, str] = Field(
        default_factory=dict,
        description="steering parameters bound at compose time",
    )
    axis: str | None = Field(
        default=None, description="thinking axis touched, if any"
    )


class RecipeStructure(BaseModel):
    """Typed pipeline definition produced by design_recipe's synthesize step.

    Carries structured recipe data so the renderer reads typed fields
    directly instead of parsing pseudocode from prose (ADR-006).
    """

    name: str = Field(description="recipe name")
    purpose: str = Field(description="one-line recipe purpose")
    definition: str = Field(description="Dillylang pseudocode notation")
    existing_recipe: str | None = Field(
        default=None,
        description="name of existing recipe if evaluate returned pass",
    )
    stages: list[RecipeStage] = Field(description="ordered pipeline stages")
    cost: int = Field(description="total LLM calls")
    depth: int = Field(description="critical path length")
    axes: list[str] = Field(description="thinking axes touched")


class DesignSynthesizeOutput(SynthesizeOutput):
    """Extended synthesize output for design_recipe (ADR-006 compliant).

    Adds recipe_structure so the renderer gets typed pipeline data
    without parsing pseudocode from proposal prose.
    """

    recipe_structure: RecipeStructure = Field(
        description="typed pipeline definition with stages, bindings, and axes"
    )


class ChangeLogEntry(BaseModel):
    """A single change in an improve skill's revision history.

    Tracks what changed, from what to what, why, and which analysis
    improvement motivated the change.
    """

    field_changed: str = Field(description="which part of the recipe was modified")
    old_value: str = Field(description="previous state (empty string for additions)")
    new_value: str = Field(description="new state (empty string for removals)")
    rationale: str = Field(description="why this change was made")
    improvement_ref: str = Field(
        description="reference to AnalysisReport improvement that motivated this change"
    )


class ImproveSynthesizeOutput(SynthesizeOutput):
    """Extended synthesize output for improve (ADR-006 compliant).

    Adds the revised recipe and a structured change log so the renderer
    can produce a diff-like summary of what changed and why.
    """

    revised_recipe: str = Field(
        description="the improved recipe in Dillylang pseudocode"
    )
    revised_operators: list[str] = Field(
        description="operators used in the revised recipe"
    )
    revised_combinators: list[str] = Field(
        description="combinators used in the revised recipe"
    )
    change_log: list[ChangeLogEntry] = Field(
        description="structured log of what changed and why"
    )


class ImproveOutput(BaseModel):
    """Rendered output of the improve meta-skill.

    Contains the improved skill description (same schema as translate's
    output, per D-02) and a change log documenting each modification.
    """

    revised_description: DillylangSkillDescription = Field(
        description="the improved skill description"
    )
    change_log: list[ChangeLogEntry] = Field(
        description="what was modified and why"
    )


class RecipeDefinition(BaseModel):
    """Rendered output of the design_recipe meta-skill.

    Deterministic projection of the full artifact collection into a
    structured recipe definition. Every field traces to a typed artifact
    field or a trivial computation — no pseudocode parsing.
    """

    recipe_name: str = Field(description="recipe name")
    recipe_purpose: str = Field(description="one-line recipe purpose")
    recipe_shape: str = Field(description="high-level recipe shape (e.g. generative, evaluative)")
    pipeline_definition: str = Field(description="Dillylang pseudocode")
    pipeline_stages: list[RecipeStage] = Field(description="ordered pipeline stages")
    metrics_cost: int = Field(description="total LLM calls")
    metrics_depth: int = Field(description="critical path length")
    metrics_coverage: int = Field(description="distinct orthogonal axes touched")
    metrics_efficiency: float = Field(description="coverage / cost")
    metrics_axes: list[str] = Field(description="thinking axes touched")
    design_rationale_shape_choice: str = Field(
        description="why this recipe shape was chosen"
    )
    design_rationale_operator_selection: list[dict[str, Any]] = Field(
        description="per-operator inclusion decision (operator, included, reason)"
    )
    existing_recipe_fit_closest: str | None = Field(
        default=None, description="closest existing recipe, if any"
    )
    existing_recipe_fit_verdict: NormalizedVerdict = Field(
        description="pass, partial, or fail"
    )
    existing_recipe_fit_delta: str | None = Field(
        default=None, description="what differs from the closest existing recipe"
    )
    caveats: list[str] = Field(
        default_factory=list, description="known limitations or concerns"
    )
    confidence: NormalizedConfidence = Field(
        description="overall design confidence: low, medium, high"
    )
