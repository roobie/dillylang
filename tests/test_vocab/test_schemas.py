"""Tests for dillylang.vocab.schemas -- operator I/O schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dillylang.vocab.schemas import (
    AbstractOutput,
    AddedConstraint,
    AnalogizeInput,
    AnalogizeOutput,
    Analogy,
    Assumption,
    Axiom,
    Classification,
    ClassifyInput,
    ClassifyOutput,
    CompareInput,
    CompareOutput,
    ComparisonPoint,
    ConcretizeOutput,
    ConflictResolution,
    ConstrainOutput,
    DecomposeInput,
    DecomposeOutput,
    Derivation,
    EvaluateInput,
    EvaluateOutput,
    FailureMode,
    Incorporation,
    Instance,
    InvertOutput,
    Principle,
    Proposal,
    RankInput,
    RankOutput,
    RankScores,
    RelaxedConstraint,
    RelaxOutput,
    RotateInput,
    RotateOutput,
    Rotation,
    SynthesizeOutput,
    Tradeoff,
)


def test_decompose_output_round_trip() -> None:
    """DecomposeOutput with sample data survives round-trip."""
    output = DecomposeOutput(
        axioms=[Axiom(statement="X holds", justification="fundamental")],
        derivations=[Derivation(claim="Y follows", depends_on=["X holds"])],
        assumptions=[
            Assumption(statement="Z assumed", load_bearing=True, testable="measure Z")
        ],
    )
    dumped = output.model_dump()
    restored = DecomposeOutput.model_validate(dumped)
    assert len(restored.axioms) == 1
    assert restored.axioms[0].statement == "X holds"
    assert len(restored.derivations) == 1
    assert restored.derivations[0].depends_on == ["X holds"]
    assert len(restored.assumptions) == 1
    assert restored.assumptions[0].load_bearing is True


def test_decompose_input_focus_default() -> None:
    """DecomposeInput().focus defaults to None (full-scope decomposition)."""
    di = DecomposeInput()
    assert di.focus is None


def test_decompose_input_focus_bound() -> None:
    """DecomposeInput accepts a focus string for narrowed decomposition."""
    di = DecomposeInput(focus="requirements, constraints")
    assert di.focus == "requirements, constraints"


def test_synthesize_output_all_base_fields() -> None:
    """SynthesizeOutput has exactly the 6 base integration fields from ADR-006."""
    output = SynthesizeOutput(
        proposal=Proposal(statement="do X", rationale="because Y"),
        incorporates=[
            Incorporation(source_artifact_id="invert_1", contribution="failure modes")
        ],
        tradeoffs=[Tradeoff(gained="safety", given_up="speed")],
        open_questions=["how to scale?"],
        conflicts_addressed=[
            ConflictResolution(conflict="speed vs safety", resolution="accepted_as_tradeoff")
        ],
        confidence="high",
    )
    field_names = list(output.model_dump().keys())
    expected = [
        "proposal", "incorporates", "tradeoffs",
        "open_questions", "conflicts_addressed", "confidence",
    ]
    assert field_names == expected


def test_invert_output_failure_mode_enums() -> None:
    """FailureMode likelihood and severity accept only valid Literal values."""
    fm = FailureMode(
        mode="data loss",
        mechanism="disk full",
        likelihood="high",
        severity="fatal",
        preventable_by="monitoring",
    )
    assert fm.likelihood == "high"
    assert fm.severity == "fatal"

    # Invalid values should raise ValidationError
    with pytest.raises(ValidationError):
        FailureMode(
            mode="x", mechanism="y",
            likelihood="extreme",  # invalid
            severity="fatal",
            preventable_by="z",
        )

    with pytest.raises(ValidationError):
        FailureMode(
            mode="x", mechanism="y",
            likelihood="high",
            severity="catastrophic",  # invalid
            preventable_by="z",
        )


def test_invert_output_round_trip() -> None:
    """InvertOutput with all fields survives round-trip."""
    output = InvertOutput(
        anti_goals=["fail to ship"],
        failure_modes=[
            FailureMode(
                mode="scope creep", mechanism="no scope control",
                likelihood="medium", severity="costly",
                preventable_by="scope freeze",
            )
        ],
        near_misses=["almost missed deadline"],
    )
    dumped = output.model_dump()
    restored = InvertOutput.model_validate(dumped)
    assert len(restored.failure_modes) == 1
    assert restored.failure_modes[0].mode == "scope creep"


def test_rotate_input_target_frame_default() -> None:
    """RotateInput().target_frame defaults to None (open-ended exploration)."""
    ri = RotateInput()
    assert ri.target_frame is None


def test_rotate_output_round_trip() -> None:
    """RotateOutput with rotations survives round-trip."""
    output = RotateOutput(
        original_axis="engineering efficiency",
        rotations=[
            Rotation(
                new_axis="user experience",
                rotation_kind="viewpoint_change",
                restated_problem="how does this affect users?",
                what_becomes_visible=["UX friction"],
                what_recedes=["implementation cost"],
            )
        ],
    )
    dumped = output.model_dump()
    restored = RotateOutput.model_validate(dumped)
    assert restored.original_axis == "engineering efficiency"
    assert restored.rotations[0].rotation_kind == "viewpoint_change"


def test_analogize_output_round_trip() -> None:
    """AnalogizeOutput with analogies and stowaways survives round-trip."""
    output = AnalogizeOutput(
        problem_signature="resource allocation under constraint",
        analogies=[
            Analogy(
                domain="biology",
                analog="immune system resource allocation",
                mechanism_mapping="T-cells prioritize threats like budget priorities",
                transferable_insight="adaptive allocation beats fixed allocation",
                stowaways=["biological systems have no budget meetings"],
            )
        ],
    )
    dumped = output.model_dump()
    restored = AnalogizeOutput.model_validate(dumped)
    assert len(restored.analogies[0].stowaways) == 1


def test_evaluate_input_criterion_required() -> None:
    """EvaluateInput(criterion=...) works; missing criterion raises ValidationError."""
    ei = EvaluateInput(criterion="load_bearing")
    assert ei.criterion == "load_bearing"

    with pytest.raises(ValidationError):
        EvaluateInput()  # type: ignore[call-arg]


def test_evaluate_output_verdict_values() -> None:
    """EvaluateOutput verdict accepts only pass/partial/fail."""
    eo = EvaluateOutput(
        verdict="partial",
        evidence=["some evidence"],
        rationale="partially meets criterion",
        confidence="medium",
    )
    assert eo.verdict == "partial"

    with pytest.raises(ValidationError):
        EvaluateOutput(
            verdict="maybe",  # invalid
            evidence=[],
            rationale="test",
            confidence="low",
        )


def test_rank_output_round_trip() -> None:
    """RankOutput with scored artifacts survives round-trip."""
    output = RankOutput(
        ranked=[
            RankScores(
                artifact_id="art_0",
                scores={"novelty": "high", "feasibility": "medium"},
                rationale="novel approach, moderate feasibility",
            ),
            RankScores(
                artifact_id="art_1",
                scores={"novelty": "low", "feasibility": "high"},
                rationale="safe approach, highly feasible",
            ),
        ],
        top_k_ids=["art_0"],
    )
    dumped = output.model_dump()
    restored = RankOutput.model_validate(dumped)
    assert len(restored.ranked) == 2
    assert restored.top_k_ids == ["art_0"]
    assert restored.ranked[0].scores["novelty"] == "high"


def test_rank_input_top_k_default() -> None:
    """RankInput.top_k defaults to None (return all)."""
    ri = RankInput(criteria=["novelty", "feasibility"])
    assert ri.top_k is None
    assert ri.criteria == ["novelty", "feasibility"]


def test_all_schemas_importable() -> None:
    """All Input/Output schema classes are importable from dillylang.vocab.schemas."""
    from dillylang.vocab.schemas import (
        AbstractOutput,
        AddedConstraint,
        AnalogizeInput,
        AnalogizeOutput,
        Classification,
        ClassifyInput,
        ClassifyOutput,
        CompareInput,
        CompareOutput,
        ComparisonPoint,
        ConcretizeOutput,
        ConstrainOutput,
        DecomposeInput,
        DecomposeOutput,
        EvaluateInput,
        EvaluateOutput,
        Instance,
        InvertOutput,
        Principle,
        RankInput,
        RankOutput,
        RelaxedConstraint,
        RelaxOutput,
        RotateInput,
        RotateOutput,
        SynthesizeOutput,
    )
    for cls in [
        DecomposeInput, DecomposeOutput, SynthesizeOutput, InvertOutput,
        RotateInput, RotateOutput, AnalogizeOutput,
        EvaluateInput, EvaluateOutput, RankInput, RankOutput,
        ClassifyInput, ClassifyOutput, Classification,
        AbstractOutput, Principle,
        ConcretizeOutput, Instance,
        ConstrainOutput, AddedConstraint,
        RelaxOutput, RelaxedConstraint,
        CompareInput, CompareOutput, ComparisonPoint,
        AnalogizeInput,
    ]:
        assert cls is not None


# --- Phase 2 schema tests ---


class TestClassifySchemas:
    """Tests for classify operator I/O schemas (ADR-005)."""

    def test_classify_input_round_trip(self) -> None:
        """ClassifyInput with taxonomies round-trips through model_dump/model_validate."""
        ci = ClassifyInput(taxonomies={"type": ["a", "b"], "severity": ["low", "high"]})
        dumped = ci.model_dump()
        restored = ClassifyInput.model_validate(dumped)
        assert restored.taxonomies == {"type": ["a", "b"], "severity": ["low", "high"]}

    def test_classify_input_taxonomies_required(self) -> None:
        """ClassifyInput() without taxonomies raises ValidationError."""
        with pytest.raises(ValidationError):
            ClassifyInput()  # type: ignore[call-arg]

    def test_classify_output_round_trip(self) -> None:
        """ClassifyOutput with classifications array validates and round-trips."""
        co = ClassifyOutput(
            classifications=[
                Classification(
                    taxonomy="type",
                    label="divergent",
                    rationale="explores multiple paths",
                    confidence="high",
                )
            ]
        )
        dumped = co.model_dump()
        restored = ClassifyOutput.model_validate(dumped)
        assert len(restored.classifications) == 1
        assert restored.classifications[0].taxonomy == "type"
        assert restored.classifications[0].label == "divergent"
        assert restored.classifications[0].confidence == "high"

    def test_classification_sub_model_fields(self) -> None:
        """Classification sub-model has taxonomy, label, rationale, confidence."""
        c = Classification(
            taxonomy="complexity",
            label="simple",
            rationale="single-step problem",
            confidence="medium",
        )
        assert c.taxonomy == "complexity"
        assert c.label == "simple"
        assert c.rationale == "single-step problem"
        assert c.confidence == "medium"

    def test_classification_confidence_normalized(self) -> None:
        """Classification.confidence normalizes mechanical variations."""
        c = Classification(
            taxonomy="t", label="l", rationale="r", confidence="HIGH"
        )
        assert c.confidence == "high"

    def test_classification_confidence_invalid(self) -> None:
        """Classification with invalid confidence raises ValidationError."""
        with pytest.raises(ValidationError):
            Classification(
                taxonomy="t", label="l", rationale="r", confidence="extreme"
            )


class TestCompareSchemas:
    """Tests for compare operator I/O schemas."""

    def test_compare_input_round_trip(self) -> None:
        """CompareInput with criterion round-trips."""
        ci = CompareInput(criterion="clarity")
        dumped = ci.model_dump()
        restored = CompareInput.model_validate(dumped)
        assert restored.criterion == "clarity"

    def test_compare_input_criterion_required(self) -> None:
        """CompareInput() without criterion raises ValidationError."""
        with pytest.raises(ValidationError):
            CompareInput()  # type: ignore[call-arg]

    def test_compare_output_round_trip(self) -> None:
        """CompareOutput with all fields round-trips."""
        co = CompareOutput(
            criterion="clarity",
            winner="art_a",
            rationale="art_a is more explicit",
            comparison_points=[
                ComparisonPoint(
                    dimension="explicitness",
                    artifact_a_assessment="very explicit",
                    artifact_b_assessment="somewhat vague",
                )
            ],
            confidence="high",
        )
        dumped = co.model_dump()
        restored = CompareOutput.model_validate(dumped)
        assert restored.winner == "art_a"
        assert restored.criterion == "clarity"
        assert restored.confidence == "high"
        assert len(restored.comparison_points) == 1

    def test_compare_output_confidence_normalized(self) -> None:
        """CompareOutput.confidence normalizes mechanical variations."""
        co = CompareOutput(
            criterion="c", winner="tie", rationale="r",
            comparison_points=[], confidence="MEDIUM",
        )
        assert co.confidence == "medium"


class TestAbstractSchemas:
    """Tests for abstract operator output schema."""

    def test_abstract_output_round_trip(self) -> None:
        """AbstractOutput with principles round-trips."""
        ao = AbstractOutput(
            principles=[
                Principle(
                    statement="separation of concerns",
                    grounding=["module A", "module B"],
                    abstraction_level="architectural pattern",
                )
            ],
            source_pattern="modular design",
        )
        dumped = ao.model_dump()
        restored = AbstractOutput.model_validate(dumped)
        assert len(restored.principles) == 1
        assert restored.principles[0].statement == "separation of concerns"
        assert restored.source_pattern == "modular design"

    def test_principle_sub_model_fields(self) -> None:
        """Principle sub-model has statement, grounding, abstraction_level."""
        p = Principle(
            statement="s", grounding=["a", "b"], abstraction_level="high"
        )
        assert p.statement == "s"
        assert p.grounding == ["a", "b"]
        assert p.abstraction_level == "high"


class TestConcretizeSchemas:
    """Tests for concretize operator output schema."""

    def test_concretize_output_round_trip(self) -> None:
        """ConcretizeOutput with instances round-trips."""
        co = ConcretizeOutput(
            instances=[
                Instance(
                    description="REST API endpoint",
                    derivation="applied separation of concerns to web services",
                    constraints_applied=["HTTP protocol", "stateless"],
                )
            ],
            target_domain="web services",
        )
        dumped = co.model_dump()
        restored = ConcretizeOutput.model_validate(dumped)
        assert len(restored.instances) == 1
        assert restored.target_domain == "web services"

    def test_instance_sub_model_fields(self) -> None:
        """Instance sub-model has description, derivation, constraints_applied."""
        i = Instance(
            description="d", derivation="r", constraints_applied=["c1"]
        )
        assert i.description == "d"
        assert i.constraints_applied == ["c1"]


class TestConstrainSchemas:
    """Tests for constrain operator output schema."""

    def test_constrain_output_round_trip(self) -> None:
        """ConstrainOutput with constraints_added round-trips."""
        co = ConstrainOutput(
            constraints_added=[
                AddedConstraint(
                    constraint="must use SQL",
                    justification="existing infrastructure",
                    impact="eliminates NoSQL options",
                )
            ],
            impact_on_solution_space="significantly narrowed",
            tradeoffs=[Tradeoff(gained="compatibility", given_up="flexibility")],
        )
        dumped = co.model_dump()
        restored = ConstrainOutput.model_validate(dumped)
        assert len(restored.constraints_added) == 1
        assert restored.impact_on_solution_space == "significantly narrowed"
        assert len(restored.tradeoffs) == 1

    def test_added_constraint_sub_model_fields(self) -> None:
        """AddedConstraint has constraint, justification, impact."""
        ac = AddedConstraint(
            constraint="c", justification="j", impact="i"
        )
        assert ac.constraint == "c"
        assert ac.justification == "j"
        assert ac.impact == "i"


class TestRelaxSchemas:
    """Tests for relax operator output schema."""

    def test_relax_output_round_trip(self) -> None:
        """RelaxOutput with constraints_removed round-trips."""
        ro = RelaxOutput(
            constraints_removed=[
                RelaxedConstraint(
                    original_constraint="must use SQL",
                    relaxation="allow any storage backend",
                    justification="flexibility needed for prototyping",
                )
            ],
            new_possibilities=["graph database", "document store"],
            risks_introduced=["migration complexity"],
        )
        dumped = ro.model_dump()
        restored = RelaxOutput.model_validate(dumped)
        assert len(restored.constraints_removed) == 1
        assert len(restored.new_possibilities) == 2
        assert len(restored.risks_introduced) == 1

    def test_relaxed_constraint_sub_model_fields(self) -> None:
        """RelaxedConstraint has original_constraint, relaxation, justification."""
        rc = RelaxedConstraint(
            original_constraint="oc", relaxation="r", justification="j"
        )
        assert rc.original_constraint == "oc"
        assert rc.relaxation == "r"


class TestAnalogizeInput:
    """Tests for AnalogizeInput steering parameter schema."""

    def test_analogize_input_with_domains(self) -> None:
        """AnalogizeInput(domains=["biology", "economics"]) round-trips."""
        ai = AnalogizeInput(domains=["biology", "economics"])
        dumped = ai.model_dump()
        restored = AnalogizeInput.model_validate(dumped)
        assert restored.domains == ["biology", "economics"]

    def test_analogize_input_domains_optional(self) -> None:
        """AnalogizeInput() succeeds with domains=None."""
        ai = AnalogizeInput()
        assert ai.domains is None


# --- Phase 3a meta-skill schema tests ---


class TestSkillFileSchemas:
    """Tests for SkillFile and NormalizedSkillFileKind."""

    def test_skill_file_round_trip(self) -> None:
        """SkillFile with all fields survives round-trip."""
        from dillylang.vocab.schemas import SkillFile

        sf = SkillFile(path="SKILL.md", kind="skill_md", content="# My Skill")
        dumped = sf.model_dump()
        restored = SkillFile.model_validate(dumped)
        assert restored.path == "SKILL.md"
        assert restored.kind == "skill_md"
        assert restored.content == "# My Skill"

    def test_skill_file_kind_normalization(self) -> None:
        """NormalizedSkillFileKind normalizes case variations."""
        from dillylang.vocab.schemas import SkillFile

        sf = SkillFile(path="x.md", kind="Skill_MD", content="")
        assert sf.kind == "skill_md"

        sf2 = SkillFile(path="y.md", kind="CLAUDE_MD", content="")
        assert sf2.kind == "claude_md"

    def test_skill_file_kind_invalid(self) -> None:
        """Invalid kind raises ValidationError."""
        from dillylang.vocab.schemas import SkillFile

        with pytest.raises(ValidationError):
            SkillFile(path="x", kind="unknown_kind", content="")


class TestTruncationInfo:
    """Tests for TruncationInfo defaults."""

    def test_truncation_info_defaults(self) -> None:
        """TruncationInfo() has sensible defaults for no-truncation case."""
        from dillylang.vocab.schemas import TruncationInfo

        ti = TruncationInfo()
        assert ti.occurred is False
        assert ti.files_dropped == []
        assert ti.bytes_dropped == 0
        assert ti.reason == ""

    def test_truncation_info_populated(self) -> None:
        """TruncationInfo with values round-trips."""
        from dillylang.vocab.schemas import TruncationInfo

        ti = TruncationInfo(
            occurred=True, files_dropped=["big.py"], bytes_dropped=5000,
            reason="exceeded 50KB limit"
        )
        dumped = ti.model_dump()
        restored = TruncationInfo.model_validate(dumped)
        assert restored.occurred is True
        assert restored.files_dropped == ["big.py"]
        assert restored.bytes_dropped == 5000


class TestSkillSourceBundle:
    """Tests for SkillSourceBundle round-trip."""

    def test_skill_source_bundle_round_trip(self) -> None:
        """SkillSourceBundle with nested SkillFiles round-trips."""
        from dillylang.vocab.schemas import SkillFile, SkillSourceBundle, TruncationInfo

        bundle = SkillSourceBundle(
            path="/skills/lateral-shift",
            files=[
                SkillFile(path="SKILL.md", kind="skill_md", content="# Skill"),
                SkillFile(path="run.py", kind="script", content="print('hi')"),
            ],
            entrypoints=[{"name": "main", "path": "run.py"}],
            detected_scripts=["run.py"],
            detected_prompts=[],
            detected_tools=["file_search"],
            detected_control_flow=["sequential"],
            ingestion_status="success",
            truncation=TruncationInfo(),
        )
        dumped = bundle.model_dump()
        restored = SkillSourceBundle.model_validate(dumped)
        assert restored.path == "/skills/lateral-shift"
        assert len(restored.files) == 2
        assert restored.files[0].kind == "skill_md"
        assert restored.ingestion_status == "success"
        assert restored.truncation.occurred is False

    def test_skill_source_bundle_ingestion_status_normalized(self) -> None:
        """NormalizedIngestionStatus normalizes case."""
        from dillylang.vocab.schemas import SkillSourceBundle

        bundle = SkillSourceBundle(
            path="/x", files=[], ingestion_status="PARTIAL"
        )
        assert bundle.ingestion_status == "partial"


class TestStageMapping:
    """Tests for StageMapping with NormalizedFit."""

    def test_stage_mapping_all_fit_values(self) -> None:
        """StageMapping accepts all three fit values."""
        from dillylang.vocab.schemas import StageMapping

        for fit in ("direct", "approximate", "outside_vocabulary"):
            sm = StageMapping(
                source_stage="step1",
                dillylang_expression="decompose",
                fit=fit,
            )
            assert sm.fit == fit

    def test_stage_mapping_fit_normalization(self) -> None:
        """NormalizedFit normalizes case and separator variations."""
        from dillylang.vocab.schemas import StageMapping

        sm = StageMapping(
            source_stage="s", dillylang_expression="e",
            fit="Outside-Vocabulary"
        )
        assert sm.fit == "outside_vocabulary"

    def test_stage_mapping_notes_optional(self) -> None:
        """StageMapping.notes defaults to empty string."""
        from dillylang.vocab.schemas import StageMapping

        sm = StageMapping(
            source_stage="s", dillylang_expression="e", fit="direct"
        )
        assert sm.notes == ""


class TestVocabularyResidue:
    """Tests for VocabularyResidue."""

    def test_vocabulary_residue_round_trip(self) -> None:
        """VocabularyResidue round-trips including optional extension signal."""
        from dillylang.vocab.schemas import VocabularyResidue

        vr = VocabularyResidue(
            feature="tool use",
            why_it_does_not_fit="operators cannot invoke tools",
            vocabulary_extension_signal="consider a 'tool_call' operator",
        )
        dumped = vr.model_dump()
        restored = VocabularyResidue.model_validate(dumped)
        assert restored.feature == "tool use"
        assert restored.vocabulary_extension_signal is not None

    def test_vocabulary_residue_signal_optional(self) -> None:
        """VocabularyResidue.vocabulary_extension_signal defaults to None."""
        from dillylang.vocab.schemas import VocabularyResidue

        vr = VocabularyResidue(
            feature="f", why_it_does_not_fit="w"
        )
        assert vr.vocabulary_extension_signal is None


class TestDillylangSkillDescription:
    """Tests for DillylangSkillDescription round-trip."""

    def test_dillylang_skill_description_round_trip(self) -> None:
        """DillylangSkillDescription with all fields round-trips."""
        from dillylang.vocab.schemas import (
            DillylangSkillDescription,
            StageMapping,
            VocabularyResidue,
        )

        desc = DillylangSkillDescription(
            skill_name="lateral-shift",
            skill_purpose="Generate lateral thinking perspectives on a problem",
            activation_contract="/lateral-shift <problem>",
            execution_model="sequential pipeline with parallel exploration",
            recipe_shape="pipe(decompose, parallel(rotate, analogize), synthesize)",
            source_contract_entrypoints=["SKILL.md"],
            source_contract_inputs=["problem statement"],
            source_contract_outputs=["lateral perspectives", "synthesis"],
            source_contract_control_flow=["sequential", "parallel fan-out"],
            dillylang_pseudocode="pipe(decompose(focus='structure'), parallel(rotate, analogize), synthesize)",
            dillylang_operators=["decompose", "rotate", "analogize", "synthesize"],
            dillylang_combinators=["pipe", "parallel"],
            stage_mapping=[
                StageMapping(
                    source_stage="break down problem",
                    dillylang_expression="decompose(focus='structure')",
                    fit="direct",
                )
            ],
            residue=[
                VocabularyResidue(
                    feature="interactive clarification",
                    why_it_does_not_fit="requires runtime interaction",
                )
            ],
            open_questions=["Should parallel fan-out be bounded?"],
            confidence="medium",
        )
        dumped = desc.model_dump()
        restored = DillylangSkillDescription.model_validate(dumped)
        assert restored.skill_name == "lateral-shift"
        assert len(restored.dillylang_operators) == 4
        assert len(restored.stage_mapping) == 1
        assert restored.stage_mapping[0].fit == "direct"
        assert len(restored.residue) == 1
        assert restored.confidence == "medium"


class TestRecipeMetrics:
    """Tests for RecipeMetrics."""

    def test_recipe_metrics_round_trip(self) -> None:
        """RecipeMetrics with computed values round-trips."""
        from dillylang.vocab.schemas import RecipeMetrics

        rm = RecipeMetrics(
            coverage=4,
            depth=3,
            cost=5,
            cost_efficiency=0.8,
            depth_efficiency=1.33,
            axes_touched=["decomposition", "rotation", "analogy", "synthesis"],
            axes_missing=["abstraction", "feasibility"],
        )
        dumped = rm.model_dump()
        restored = RecipeMetrics.model_validate(dumped)
        assert restored.coverage == 4
        assert restored.depth == 3
        assert restored.cost == 5
        assert restored.cost_efficiency == 0.8
        assert len(restored.axes_touched) == 4
        assert len(restored.axes_missing) == 2


class TestStructuralImprovement:
    """Tests for StructuralImprovement."""

    def test_structural_improvement_round_trip(self) -> None:
        """StructuralImprovement round-trips."""
        from dillylang.vocab.schemas import StructuralImprovement

        si = StructuralImprovement(
            category="axis_gap",
            description="No feasibility constraint applied",
            rationale="Recipe generates ideas without grounding in constraints",
        )
        dumped = si.model_dump()
        restored = StructuralImprovement.model_validate(dumped)
        assert restored.category == "axis_gap"
        assert restored.description == "No feasibility constraint applied"


class TestAnalysisReport:
    """Tests for AnalysisReport round-trip."""

    def test_analysis_report_round_trip(self) -> None:
        """AnalysisReport with nested metrics and improvements round-trips."""
        from dillylang.vocab.schemas import (
            AnalysisReport,
            RecipeMetrics,
            StructuralImprovement,
        )

        report = AnalysisReport(
            recipe_name="lateral-shift",
            metrics=RecipeMetrics(
                coverage=4, depth=3, cost=5, cost_efficiency=0.8,
                depth_efficiency=1.33,
                axes_touched=["decomposition", "rotation", "analogy", "synthesis"],
                axes_missing=["abstraction", "feasibility"],
            ),
            structural_verdict="partial",
            improvements=[
                StructuralImprovement(
                    category="axis_gap",
                    description="Add constrain step",
                    rationale="Grounds ideas in feasibility",
                )
            ],
            summary="Recipe covers 4/6 axes; missing feasibility grounding",
            confidence="medium",
        )
        dumped = report.model_dump()
        restored = AnalysisReport.model_validate(dumped)
        assert restored.recipe_name == "lateral-shift"
        assert restored.metrics.coverage == 4
        assert restored.structural_verdict == "partial"
        assert len(restored.improvements) == 1
        assert restored.confidence == "medium"

    def test_analysis_report_verdict_normalized(self) -> None:
        """AnalysisReport.structural_verdict normalizes case."""
        from dillylang.vocab.schemas import (
            AnalysisReport,
            RecipeMetrics,
        )

        report = AnalysisReport(
            recipe_name="test",
            metrics=RecipeMetrics(
                coverage=1, depth=1, cost=1, cost_efficiency=1.0,
                depth_efficiency=1.0, axes_touched=["x"], axes_missing=[],
            ),
            structural_verdict="PASS",
            improvements=[],
            summary="ok",
            confidence="high",
        )
        assert report.structural_verdict == "pass"


# --- Phase 3b schemas ---


class TestRecipeStage:
    """Tests for RecipeStage schema."""

    def test_round_trip(self) -> None:
        """RecipeStage round-trips through JSON with all fields."""
        from dillylang.vocab.schemas import RecipeStage

        stage = RecipeStage(
            operator="decompose",
            role="extract structure",
            bindings={"focus": "requirements"},
            axis="compositionality",
        )
        dumped = stage.model_dump()
        restored = RecipeStage.model_validate(dumped)
        assert restored.operator == "decompose"
        assert restored.role == "extract structure"
        assert restored.bindings == {"focus": "requirements"}
        assert restored.axis == "compositionality"

    def test_defaults(self) -> None:
        """RecipeStage defaults: bindings empty dict, axis None."""
        from dillylang.vocab.schemas import RecipeStage

        stage = RecipeStage(operator="invert", role="failure modes")
        assert stage.bindings == {}
        assert stage.axis is None


class TestRecipeStructure:
    """Tests for RecipeStructure schema."""

    def test_round_trip(self) -> None:
        """RecipeStructure round-trips through JSON."""
        from dillylang.vocab.schemas import RecipeStage, RecipeStructure

        structure = RecipeStructure(
            name="refine",
            purpose="multi-axis pressure",
            definition="pipe(decompose, parallel(invert, rotate), synthesize)",
            stages=[
                RecipeStage(operator="decompose", role="structure", axis="compositionality"),
                RecipeStage(operator="invert", role="failure", axis="valence"),
            ],
            cost=4,
            depth=3,
            axes=["compositionality", "valence", "frame"],
        )
        dumped = structure.model_dump()
        restored = RecipeStructure.model_validate(dumped)
        assert restored.name == "refine"
        assert len(restored.stages) == 2
        assert restored.cost == 4
        assert restored.existing_recipe is None


class TestDesignSynthesizeOutput:
    """Tests for DesignSynthesizeOutput schema."""

    def test_is_subclass_of_synthesize(self) -> None:
        """DesignSynthesizeOutput extends SynthesizeOutput."""
        from dillylang.vocab.schemas import (
            DesignSynthesizeOutput,
            SynthesizeOutput,
        )

        assert issubclass(DesignSynthesizeOutput, SynthesizeOutput)

    def test_has_recipe_structure(self) -> None:
        """DesignSynthesizeOutput has recipe_structure field."""
        from dillylang.vocab.schemas import (
            ConflictResolution,
            DesignSynthesizeOutput,
            Incorporation,
            Proposal,
            RecipeStage,
            RecipeStructure,
            Tradeoff,
        )

        output = DesignSynthesizeOutput(
            proposal=Proposal(statement="use refine", rationale="fits"),
            incorporates=[Incorporation(source_artifact_id="a", contribution="x")],
            tradeoffs=[Tradeoff(gained="speed", given_up="depth")],
            open_questions=["scaling?"],
            conflicts_addressed=[
                ConflictResolution(conflict="none", resolution="resolved")
            ],
            confidence="high",
            recipe_structure=RecipeStructure(
                name="refine",
                purpose="multi-axis",
                definition="pipe(decompose, synthesize)",
                stages=[RecipeStage(operator="decompose", role="structure")],
                cost=2,
                depth=2,
                axes=["compositionality"],
            ),
        )
        dumped = output.model_dump()
        restored = DesignSynthesizeOutput.model_validate(dumped)
        assert restored.recipe_structure.name == "refine"
        assert restored.proposal.statement == "use refine"


class TestImproveSynthesizeOutput:
    """Tests for ImproveSynthesizeOutput schema."""

    def test_is_subclass_of_synthesize(self) -> None:
        """ImproveSynthesizeOutput extends SynthesizeOutput."""
        from dillylang.vocab.schemas import (
            ImproveSynthesizeOutput,
            SynthesizeOutput,
        )

        assert issubclass(ImproveSynthesizeOutput, SynthesizeOutput)

    def test_has_revised_recipe_and_change_log(self) -> None:
        """ImproveSynthesizeOutput has revised_recipe, revised_operators, revised_combinators, change_log."""
        from dillylang.vocab.schemas import (
            ChangeLogEntry,
            ConflictResolution,
            ImproveSynthesizeOutput,
            Incorporation,
            Proposal,
            Tradeoff,
        )

        output = ImproveSynthesizeOutput(
            proposal=Proposal(statement="improved", rationale="better coverage"),
            incorporates=[Incorporation(source_artifact_id="a", contribution="x")],
            tradeoffs=[],
            open_questions=[],
            conflicts_addressed=[
                ConflictResolution(conflict="none", resolution="resolved")
            ],
            confidence="medium",
            revised_recipe="pipe(decompose, invert, synthesize)",
            revised_operators=["decompose", "invert", "synthesize"],
            revised_combinators=["pipe"],
            change_log=[
                ChangeLogEntry(
                    field_changed="pipeline",
                    old_value="pipe(decompose, synthesize)",
                    new_value="pipe(decompose, invert, synthesize)",
                    rationale="add valence axis",
                    improvement_ref="SI-001",
                )
            ],
        )
        dumped = output.model_dump()
        restored = ImproveSynthesizeOutput.model_validate(dumped)
        assert restored.revised_recipe == "pipe(decompose, invert, synthesize)"
        assert len(restored.change_log) == 1


class TestChangeLogEntry:
    """Tests for ChangeLogEntry schema."""

    def test_round_trip(self) -> None:
        """ChangeLogEntry round-trips through JSON."""
        from dillylang.vocab.schemas import ChangeLogEntry

        entry = ChangeLogEntry(
            field_changed="operator_list",
            old_value="decompose, synthesize",
            new_value="decompose, invert, synthesize",
            rationale="missing valence axis",
            improvement_ref="SI-001",
        )
        dumped = entry.model_dump()
        restored = ChangeLogEntry.model_validate(dumped)
        assert restored.field_changed == "operator_list"
        assert restored.improvement_ref == "SI-001"


class TestImproveOutput:
    """Tests for ImproveOutput schema."""

    def test_round_trip(self) -> None:
        """ImproveOutput round-trips with revised_description and change_log."""
        from dillylang.vocab.schemas import (
            ChangeLogEntry,
            DillylangSkillDescription,
            ImproveOutput,
        )

        desc = DillylangSkillDescription(
            skill_name="test",
            skill_purpose="testing",
            activation_contract="manual",
            execution_model="sequential",
            recipe_shape="generative",
            source_contract_entrypoints=[],
            source_contract_inputs=[],
            source_contract_outputs=[],
            source_contract_control_flow=[],
            dillylang_pseudocode="pipe(decompose, synthesize)",
            dillylang_operators=["decompose", "synthesize"],
            dillylang_combinators=["pipe"],
            stage_mapping=[],
            residue=[],
            open_questions=[],
            confidence="medium",
        )
        output = ImproveOutput(
            revised_description=desc,
            change_log=[
                ChangeLogEntry(
                    field_changed="operators",
                    old_value="",
                    new_value="invert",
                    rationale="add valence",
                    improvement_ref="SI-001",
                )
            ],
        )
        dumped = output.model_dump()
        restored = ImproveOutput.model_validate(dumped)
        assert restored.revised_description.skill_name == "test"
        assert len(restored.change_log) == 1


class TestRecipeDefinition:
    """Tests for RecipeDefinition schema."""

    def test_round_trip(self) -> None:
        """RecipeDefinition round-trips through JSON."""
        from dillylang.vocab.schemas import RecipeDefinition, RecipeStage

        defn = RecipeDefinition(
            recipe_name="refine",
            recipe_purpose="multi-axis",
            recipe_shape="generative",
            pipeline_definition="pipe(decompose, parallel(invert, rotate), synthesize)",
            pipeline_stages=[
                RecipeStage(operator="decompose", role="structure", axis="compositionality"),
            ],
            metrics_cost=4,
            metrics_depth=3,
            metrics_coverage=3,
            metrics_efficiency=0.75,
            metrics_axes=["compositionality", "valence", "frame"],
            design_rationale_shape_choice="generative fits diverge-converge",
            design_rationale_operator_selection=[
                {"operator": "decompose", "included": True, "reason": "structure needed"},
            ],
            existing_recipe_fit_closest="refine",
            existing_recipe_fit_verdict="pass",
            existing_recipe_fit_delta="use as-is",
            caveats=["prompt weight"],
            confidence="high",
        )
        dumped = defn.model_dump()
        restored = RecipeDefinition.model_validate(dumped)
        assert restored.recipe_name == "refine"
        assert restored.metrics_efficiency == 0.75
        assert restored.existing_recipe_fit_verdict == "pass"
        assert len(restored.pipeline_stages) == 1

    def test_defaults(self) -> None:
        """RecipeDefinition defaults: closest=None, delta=None, caveats=[]."""
        from dillylang.vocab.schemas import RecipeDefinition

        defn = RecipeDefinition(
            recipe_name="test",
            recipe_purpose="test",
            recipe_shape="evaluative",
            pipeline_definition="pipe(evaluate)",
            pipeline_stages=[],
            metrics_cost=1,
            metrics_depth=1,
            metrics_coverage=0,
            metrics_efficiency=0.0,
            metrics_axes=[],
            design_rationale_shape_choice="simple",
            design_rationale_operator_selection=[],
            existing_recipe_fit_verdict="fail",
            confidence="low",
        )
        assert defn.existing_recipe_fit_closest is None
        assert defn.existing_recipe_fit_delta is None
        assert defn.caveats == []
