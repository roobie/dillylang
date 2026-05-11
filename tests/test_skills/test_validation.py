"""Structural validation gates + integration tests for translate and analyze.

Per D-13: layered validation. Part A is automated structural gates (no LLM,
always run). Part B is integration tests (real LLM, opt-in via --run-integration).

Structural gates validate:
  - Pantry name correctness (operators + combinators)
  - Metric invariants (coverage/axes/efficiency formulas)
  - Pydantic round-trip validation
  - Residue completeness
  - Ingestion on real skill directories
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from dillylang.skills.ingest import ingest_skill_directory
from dillylang.skills.metrics import compute_metrics
from dillylang.vocab.schemas import (
    AnalysisReport,
    DillylangSkillDescription,
    RecipeMetrics,
    StageMapping,
    StructuralImprovement,
    VocabularyResidue,
)

# --- Valid pantry names (canonical, from spec) ---

VALID_OPERATORS = frozenset({
    "decompose", "synthesize", "invert", "rotate", "analogize",
    "abstract", "concretize", "constrain", "relax",
    "evaluate", "rank", "classify", "compare",
})

VALID_COMBINATORS = frozenset({
    "pipe", "parallel", "bind", "map", "filter", "branch",
})


# --- Test helpers ---


def _make_mock_translate_result(skill_name: str) -> DillylangSkillDescription:
    """Create a realistic DillylangSkillDescription for structural validation."""
    return DillylangSkillDescription(
        skill_name=skill_name,
        skill_purpose="multi-perspective analysis",
        activation_contract="/lateral-shift",
        execution_model="Model C",
        recipe_shape="generative",
        source_contract_entrypoints=["/lateral-shift"],
        source_contract_inputs=["problem context", "current file"],
        source_contract_outputs=["analysis from multiple perspectives"],
        source_contract_control_flow=["parallel", "branch"],
        dillylang_pseudocode="pipe(decompose, parallel(rotate, invert, analogize), synthesize)",
        dillylang_operators=["decompose", "rotate", "invert", "analogize", "synthesize"],
        dillylang_combinators=["pipe", "parallel"],
        stage_mapping=[
            StageMapping(
                source_stage="perspective analysis",
                dillylang_expression="parallel(rotate, invert)",
                fit="direct",
            ),
            StageMapping(
                source_stage="synthesis",
                dillylang_expression="synthesize",
                fit="direct",
            ),
        ],
        residue=[
            VocabularyResidue(
                feature="tool use",
                why_it_does_not_fit="no IO operators in vocabulary",
                vocabulary_extension_signal=None,
            ),
        ],
        open_questions=["should analogize be included?"],
        confidence="medium",
    )


# =============================================================================
# Part A: Structural gate tests (no LLM, always run)
# =============================================================================


class TestStructuralGates:
    """Rerunnable structural validation per D-13 checklist."""

    def test_structural_gate_all_operators_valid_pantry_names(self) -> None:
        """Every operator in a DillylangSkillDescription is a known pantry name."""
        desc = _make_mock_translate_result("test-skill")
        for op in desc.dillylang_operators:
            assert op in VALID_OPERATORS, (
                f"Operator '{op}' not in valid pantry: {VALID_OPERATORS}"
            )

    def test_structural_gate_all_combinators_valid(self) -> None:
        """Every combinator in a DillylangSkillDescription is a known combinator."""
        desc = _make_mock_translate_result("test-skill")
        for comb in desc.dillylang_combinators:
            assert comb in VALID_COMBINATORS, (
                f"Combinator '{comb}' not in valid set: {VALID_COMBINATORS}"
            )

    def test_structural_gate_metrics_match_recipe(self) -> None:
        """Computed metrics satisfy invariants from D-06/D-10.

        coverage == len(axes_touched)
        coverage + len(axes_missing) == 6 (total axes)
        cost_efficiency == coverage / cost (if cost > 0)
        depth_efficiency == coverage / depth (if depth > 0)
        """
        desc = _make_mock_translate_result("test-skill")
        metrics = compute_metrics(desc)

        # Coverage equals count of axes touched
        assert metrics.coverage == len(metrics.axes_touched)

        # Total axes is fixed at 6 (compositionality, valence, frame,
        # substrate, abstraction, feasibility)
        assert metrics.coverage + len(metrics.axes_missing) == 6

        # Efficiency formulas (with float tolerance for rounding)
        if metrics.cost > 0:
            expected_cost_eff = round(metrics.coverage / metrics.cost, 4)
            assert abs(metrics.cost_efficiency - expected_cost_eff) < 1e-6
        if metrics.depth > 0:
            expected_depth_eff = round(metrics.coverage / metrics.depth, 4)
            assert abs(metrics.depth_efficiency - expected_depth_eff) < 1e-6

    def test_structural_gate_pydantic_validates(self) -> None:
        """DillylangSkillDescription and AnalysisReport round-trip via Pydantic."""
        desc = _make_mock_translate_result("test-skill")

        # DillylangSkillDescription round-trip
        dumped = desc.model_dump()
        restored = DillylangSkillDescription.model_validate(dumped)
        assert restored.skill_name == desc.skill_name
        assert restored.dillylang_operators == desc.dillylang_operators

        # AnalysisReport round-trip
        report = AnalysisReport(
            recipe_name="test-recipe",
            metrics=RecipeMetrics(
                coverage=3,
                depth=4,
                cost=5,
                cost_efficiency=0.6,
                depth_efficiency=0.75,
                axes_touched=["compositionality", "valence", "frame"],
                axes_missing=["substrate", "abstraction", "feasibility"],
            ),
            structural_verdict="partial",
            improvements=[
                StructuralImprovement(
                    category="gap",
                    description="Missing substrate axis",
                    rationale="Analogize operator would add cross-domain insight",
                ),
            ],
            summary="test-recipe: coverage=3/6, depth=4, cost=5.",
            confidence="medium",
        )
        report_dumped = report.model_dump()
        report_restored = AnalysisReport.model_validate(report_dumped)
        assert report_restored.recipe_name == report.recipe_name
        assert report_restored.metrics.coverage == 3
        assert report_restored.structural_verdict == "partial"

    def test_structural_gate_residue_marks_non_vocabulary(self) -> None:
        """Every residue entry has non-empty feature and why_it_does_not_fit."""
        desc = _make_mock_translate_result("test-skill")
        assert len(desc.residue) > 0, "Mock should have at least one residue entry"
        for r in desc.residue:
            assert r.feature.strip(), "Residue feature must be non-empty"
            assert r.why_it_does_not_fit.strip(), (
                "Residue why_it_does_not_fit must be non-empty"
            )


# =============================================================================
# Part A continued: Ingestion tests on real skill directories
# =============================================================================


class TestIngestion:
    """Validate ingestion on real skill directories from ~/devel/skills/rev1/."""

    def test_ingest_lateral_shift_succeeds(self) -> None:
        """lateral-shift directory ingests successfully (has SKILL.md + extras)."""
        skill_path = Path.home() / "devel/skills/rev1/lateral-shift"
        if not skill_path.exists():
            pytest.skip(f"Skill directory not found: {skill_path}")

        artifact = ingest_skill_directory(skill_path)

        # Should not fail (SKILL.md is present)
        assert artifact.status.value in ("success", "partial"), (
            f"Expected success/partial, got {artifact.status.value}"
        )
        # Data should contain files with SKILL.md included
        files = artifact.data.get("files", [])
        skill_md_found = any(f["path"] == "SKILL.md" for f in files)
        assert skill_md_found, "SKILL.md must be in ingested files"

    def test_ingest_phase_doc_review_succeeds(self) -> None:
        """phase-doc-review directory ingests successfully (SKILL.md only)."""
        skill_path = Path.home() / "devel/skills/rev1/phase-doc-review"
        if not skill_path.exists():
            pytest.skip(f"Skill directory not found: {skill_path}")

        artifact = ingest_skill_directory(skill_path)

        # Should succeed (only SKILL.md, well within limits)
        assert artifact.status.value == "success", (
            f"Expected success, got {artifact.status.value}"
        )
        # Data should contain files with SKILL.md included
        files = artifact.data.get("files", [])
        skill_md_found = any(f["path"] == "SKILL.md" for f in files)
        assert skill_md_found, "SKILL.md must be in ingested files"


# =============================================================================
# Part B: Integration tests (real LLM, marked with @pytest.mark.integration)
# =============================================================================


@pytest.mark.integration
class TestTranslateIntegration:
    """Real LLM integration tests for translate. Require --run-integration."""

    def test_translate_lateral_shift_integration(
        self, configure_dspy_lm: None, persist_pipeline_run: Any
    ) -> None:
        """translate produces valid DillylangSkillDescription on lateral-shift."""
        from dillylang.skills.translate import translate

        skill_path = Path.home() / "devel/skills/rev1/lateral-shift"
        if not skill_path.exists():
            pytest.skip(f"Skill directory not found: {skill_path}")

        t = translate(skill_path)

        # Basic validity
        assert isinstance(t.description, DillylangSkillDescription)
        assert t.description.skill_name, "skill_name must be non-empty"
        assert len(t.description.dillylang_operators) > 0, "Must identify operators"
        assert len(t.description.stage_mapping) > 0, "Must produce stage mappings"

        # All operators are valid pantry names
        for op in t.description.dillylang_operators:
            assert op in VALID_OPERATORS, f"Unknown operator: {op}"

        # Pydantic validation passes
        roundtripped = DillylangSkillDescription.model_validate(t.description.model_dump())
        assert roundtripped.skill_name == t.description.skill_name

        persist_pipeline_run(
            test_name="translate-lateral-shift",
            run_result=t.run_result,
            inputs={"skill_path": str(skill_path), "source_artifact": t.source_artifact.model_dump()},
            rendered={"description": t.description.model_dump()},
        )

    def test_translate_phase_doc_review_integration(
        self, configure_dspy_lm: None, persist_pipeline_run: Any
    ) -> None:
        """translate produces valid DillylangSkillDescription on phase-doc-review."""
        from dillylang.skills.translate import translate

        skill_path = Path.home() / "devel/skills/rev1/phase-doc-review"
        if not skill_path.exists():
            pytest.skip(f"Skill directory not found: {skill_path}")

        t = translate(skill_path)

        # Basic validity
        assert isinstance(t.description, DillylangSkillDescription)
        assert t.description.skill_name, "skill_name must be non-empty"
        assert len(t.description.dillylang_operators) > 0, "Must identify operators"

        # All operators are valid pantry names
        for op in t.description.dillylang_operators:
            assert op in VALID_OPERATORS, f"Unknown operator: {op}"

        # Pydantic validation passes
        roundtripped = DillylangSkillDescription.model_validate(t.description.model_dump())
        assert roundtripped.skill_name == t.description.skill_name

        persist_pipeline_run(
            test_name="translate-phase-doc-review",
            run_result=t.run_result,
            inputs={"skill_path": str(skill_path), "source_artifact": t.source_artifact.model_dump()},
            rendered={"description": t.description.model_dump()},
        )

    def test_translate_then_analyze_integration(
        self, configure_dspy_lm: None, persist_pipeline_run: Any
    ) -> None:
        """Full pipeline: translate -> analyze produces valid AnalysisReport."""
        from dillylang.skills.analyze import analyze
        from dillylang.skills.translate import translate

        skill_path = Path.home() / "devel/skills/rev1/lateral-shift"
        if not skill_path.exists():
            pytest.skip(f"Skill directory not found: {skill_path}")

        # Translate
        t = translate(skill_path)
        assert isinstance(t.description, DillylangSkillDescription)

        # Analyze
        a = analyze(t.description)

        # Basic validity
        assert isinstance(a.report, AnalysisReport)
        assert a.report.metrics.coverage > 0, "Coverage must be positive"
        assert isinstance(a.report.improvements, list)
        assert a.report.summary, "Summary must be non-empty"

        # Pydantic validation passes
        roundtripped = AnalysisReport.model_validate(a.report.model_dump())
        assert roundtripped.recipe_name == a.report.recipe_name

        persist_pipeline_run(
            test_name="translate-then-analyze-lateral-shift",
            run_result=t.run_result,
            inputs={"skill_path": str(skill_path), "source_artifact": t.source_artifact.model_dump()},
            rendered={
                "description": t.description.model_dump(),
                "analysis_report": a.report.model_dump(),
            },
            extra_runs={"analyze": a.run_result},
        )
