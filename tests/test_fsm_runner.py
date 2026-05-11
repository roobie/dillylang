"""Tests for the FSM recipe runner (dillylang.agent_skills.fsm_runner).

Organized by test domain (not by source function):
  - canary:     schema/registry drift detection
  - recipe:     YAML parsing & structural validation
  - refs:       reference resolution (pure function)
  - lifecycle:  FSM happy paths (start → submit → complete)
  - failures:   every error path
  - gc:         stale session cleanup
  - cli:        Click surface smoke tests

Design rules (from invert analysis):
  - Real Pydantic models, never mocked validators (FM2)
  - Fixtures built via model_validate round-trip, not handcrafted JSON (FM3)
  - Every terminal state reachable (FM5)
  - Registry completeness canary (FM9)
  - tmp_path + DILLYLANG_STATE_DIR for isolation (FM1)
"""

from __future__ import annotations

import inspect
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner
from pydantic import BaseModel

import dillylang.agent_skills.fsm_runner as fsm_runner
from dillylang.agent_skills.fsm_runner import (
    RecipeError,
    ReferenceError_,
    SessionError,
    StepError,
    _do_start,
    _do_submit,
    _do_status,
    _gc_stale_sessions,
    _get_output_model,
    _load_operator_registry,
    _load_recipe,
    _parse_input,
    _resolve_refs,
    _session_dir,
    cli,
)

# Real Pydantic models — never mocked
from dillylang.vocab import schemas as vocab_schemas
from dillylang.vocab.schemas import (
    DecomposeOutput,
    InvertOutput,
    SynthesizeOutput,
    TranslateSynthesizeOutput,
)

# ── Shared fixtures ──────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolate_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Every test gets its own STATE_ROOT via env + module patch."""
    state_dir = tmp_path / "sessions"
    state_dir.mkdir()
    monkeypatch.setenv("DILLYLANG_STATE_DIR", str(state_dir))
    monkeypatch.setattr(fsm_runner, "STATE_ROOT", state_dir)
    return state_dir


# -- Recipe fixtures --


def _minimal_recipe_data() -> dict[str, Any]:
    """2-step recipe: decompose → synthesize."""
    return {
        "name": "test-recipe",
        "description": "minimal test recipe",
        "input": {"problem": "str"},
        "steps": {
            "decompose": {
                "operator": "decompose",
                "prompt": "Decompose the problem.",
                "input": {"src": "$input.problem"},
                "output": {"axioms": "list", "derivations": "list", "assumptions": "list"},
            },
            "synthesize": {
                "operator": "synthesize",
                "prompt": "Synthesize from decomposition.",
                "input": {"src": "$decompose"},
                "output": {"proposal": "object"},
            },
        },
        "flow": ["decompose", "synthesize"],
    }


def _three_step_recipe_data() -> dict[str, Any]:
    """3-step recipe: decompose → invert → synthesize (for budget tests)."""
    data = _minimal_recipe_data()
    data["steps"]["invert"] = {
        "operator": "invert",
        "prompt": "Invert the problem.",
        "input": {"src": "$decompose"},
        "output": {"anti_goals": "list"},
    }
    data["flow"] = ["decompose", "invert", "synthesize"]
    data["steps"]["synthesize"]["input"] = {"src": "$invert"}
    return data


@pytest.fixture
def minimal_recipe(tmp_path: Path) -> Path:
    path = tmp_path / "recipe.yaml"
    path.write_text(yaml.dump(_minimal_recipe_data()))
    return path


@pytest.fixture
def three_step_recipe(tmp_path: Path) -> Path:
    path = tmp_path / "recipe.yaml"
    path.write_text(yaml.dump(_three_step_recipe_data()))
    return path


# -- Operator output fixtures (round-trip through real models, FM3) --


def _make_decompose_output() -> dict[str, Any]:
    return DecomposeOutput.model_validate({
        "axioms": [{"statement": "A is true", "justification": "foundational"}],
        "derivations": [{"claim": "B follows from A", "depends_on": ["A is true"]}],
        "assumptions": [{"statement": "C is assumed", "load_bearing": True, "testable": "check C"}],
    }).model_dump()


def _make_invert_output() -> dict[str, Any]:
    return InvertOutput.model_validate({
        "anti_goals": ["fail completely"],
        "failure_modes": [{
            "mode": "total collapse",
            "mechanism": "ignoring constraints",
            "likelihood": "medium",
            "severity": "fatal",
            "preventable_by": "validation",
        }],
        "near_misses": ["almost failed"],
    }).model_dump()


def _make_synthesize_output() -> dict[str, Any]:
    return SynthesizeOutput.model_validate({
        "proposal": {"statement": "Do X", "rationale": "Because Y"},
        "incorporates": [{"source_artifact_id": "decompose_0", "contribution": "structure"}],
        "tradeoffs": [{"gained": "clarity", "given_up": "brevity"}],
        "open_questions": ["what about Z?"],
        "conflicts_addressed": [{"conflict": "A vs B", "resolution": "resolved"}],
        "confidence": "medium",
    }).model_dump()


_OUTPUT_FIXTURES: dict[str, tuple[type[BaseModel], Any]] = {
    "decompose": (DecomposeOutput, _make_decompose_output),
    "invert": (InvertOutput, _make_invert_output),
    "synthesize": (SynthesizeOutput, _make_synthesize_output),
}


@pytest.fixture
def valid_decompose_output() -> dict[str, Any]:
    return _make_decompose_output()


@pytest.fixture
def valid_invert_output() -> dict[str, Any]:
    return _make_invert_output()


@pytest.fixture
def valid_synthesize_output() -> dict[str, Any]:
    return _make_synthesize_output()


# -- Session helpers --


def _start_session(
    recipe_path: Path,
    input_data: dict[str, Any] | None = None,
    budget: int = 7,
    runner_cmd: str | None = None,
) -> str:
    """Start a session, return session_id."""
    if input_data is None:
        input_data = {"problem": "test problem"}
    return _do_start(
        recipe_path,
        json.dumps(input_data),
        budget,
        persist=False,
        runner_cmd=runner_cmd,
    )


def _write_pending(session_id: str, step_name: str, data: dict[str, Any]) -> Path:
    """Write output JSON to the pending dir for a step."""
    pending = _session_dir(session_id) / "pending" / f"{step_name}.json"
    pending.write_text(json.dumps(data))
    return pending


def _read_meta(session_id: str) -> dict[str, Any]:
    return json.loads((_session_dir(session_id) / "meta.json").read_text())


def _session_at(
    recipe_path: Path,
    *,
    completed_steps: dict[str, dict[str, Any]],
    budget: int = 7,
) -> str:
    """Create a session pre-advanced to a specific FSM position.

    Replays start + submit for each completed step. Avoids duplicating
    the full start→submit sequence in every failure-path test (D4).
    """
    sid = _start_session(recipe_path, budget=budget)
    for step_name, output_data in completed_steps.items():
        _write_pending(sid, step_name, output_data)
        _do_submit(sid, step_name)
    return sid


# ═══════════════════════════════════════════════════════════════════════
# CANARY — schema/registry drift detection (run first, fail fast)
# ═══════════════════════════════════════════════════════════════════════


class TestCanary:
    """Detect schema/registry drift before anything else."""

    def test_all_output_models_importable(self) -> None:
        """Every class in the operator registry is a real BaseModel subclass."""
        registry = _load_operator_registry()
        for key, model_cls in registry.items():
            assert issubclass(model_cls, BaseModel), (
                f"registry[{key!r}] = {model_cls} is not a BaseModel subclass"
            )

    def test_registry_covers_all_schema_exports(self) -> None:
        """Every *Output class in vocab.schemas has a registry entry.

        Catches FM9: new operator added to schemas but not to the runner's registry.
        Non-operator outputs excluded by convention (D3): *Report classes are
        meta-skill analysis outputs, and classes already in the registry
        (including subclasses) are covered by definition.
        """
        registry = _load_operator_registry()
        registry_models = set(registry.values())

        exported_outputs: dict[str, type[BaseModel]] = {}
        for name, obj in inspect.getmembers(vocab_schemas, inspect.isclass):
            if (
                name.endswith("Output")
                and issubclass(obj, BaseModel)
                and obj is not BaseModel
            ):
                exported_outputs[name] = obj

        # Auto-exclude by naming convention + registry membership (D3)
        non_operator_outputs = {
            name
            for name, cls in exported_outputs.items()
            if name.endswith("Report") or cls in registry_models
        }

        uncovered = {
            name
            for name, cls in exported_outputs.items()
            if name not in non_operator_outputs and cls not in registry_models
        }
        assert not uncovered, (
            f"Output models missing from runner registry: {uncovered}. "
            f"Add them to _OPERATOR_OUTPUT_MODELS in fsm_runner.py."
        )

    @pytest.mark.parametrize("name", ["decompose", "invert", "synthesize"])
    def test_fixture_round_trips_losslessly(self, name: str) -> None:
        """Fixtures survive model_validate → model_dump → model_validate (D6)."""
        model_cls, make_fn = _OUTPUT_FIXTURES[name]
        data = make_fn()
        revalidated = model_cls.model_validate(data)
        assert revalidated.model_dump() == data


# ═══════════════════════════════════════════════════════════════════════
# RECIPE — parsing & structural validation
# ═══════════════════════════════════════════════════════════════════════


class TestRecipeParsing:

    def test_valid_recipe_parses(self, minimal_recipe: Path) -> None:
        recipe = _load_recipe(minimal_recipe)
        assert recipe.name == "test-recipe"
        assert recipe.flow == ["decompose", "synthesize"]
        assert set(recipe.steps.keys()) == {"decompose", "synthesize"}

    def test_recipe_step_attributes(self, minimal_recipe: Path) -> None:
        recipe = _load_recipe(minimal_recipe)
        step = recipe.steps["decompose"]
        assert step.operator == "decompose"
        assert step.prompt == "Decompose the problem."
        assert "$input.problem" in step.input_refs.values()

    def test_missing_flow_key(self, tmp_path: Path) -> None:
        data = _minimal_recipe_data()
        del data["flow"]
        path = tmp_path / "bad.yaml"
        path.write_text(yaml.dump(data))
        with pytest.raises(RecipeError, match="no flow"):
            _load_recipe(path)

    def test_flow_references_undefined_step(self, tmp_path: Path) -> None:
        data = _minimal_recipe_data()
        data["flow"].append("nonexistent")
        path = tmp_path / "bad.yaml"
        path.write_text(yaml.dump(data))
        with pytest.raises(RecipeError, match="undefined step.*nonexistent"):
            _load_recipe(path)

    def test_forward_reference_in_flow(self, tmp_path: Path) -> None:
        """Step B refs $A but B comes before A in flow order."""
        data = {
            "name": "bad-ref",
            "steps": {
                "a": {"operator": "decompose", "prompt": "go", "input": {"x": "$b"}},
                "b": {"operator": "invert", "prompt": "go"},
            },
            "flow": ["a", "b"],
        }
        path = tmp_path / "bad.yaml"
        path.write_text(yaml.dump(data))
        with pytest.raises(RecipeError, match="hasn't completed yet"):
            _load_recipe(path)

    def test_input_ref_to_recipe_input_is_valid(self, tmp_path: Path) -> None:
        """$input references are always valid regardless of flow position."""
        data = {
            "name": "input-ref",
            "steps": {
                "a": {"operator": "decompose", "prompt": "go", "input": {"x": "$input.field"}},
            },
            "flow": ["a"],
        }
        path = tmp_path / "ok.yaml"
        path.write_text(yaml.dump(data))
        recipe = _load_recipe(path)
        assert recipe.flow == ["a"]

    def test_output_model_key_override(self, tmp_path: Path) -> None:
        """Per-step output_model overrides the operator name for validation lookup."""
        data = _minimal_recipe_data()
        data["steps"]["synthesize"]["output_model"] = "translate_synthesize"
        path = tmp_path / "override.yaml"
        path.write_text(yaml.dump(data))
        recipe = _load_recipe(path)
        step = recipe.steps["synthesize"]
        assert step.output_model_key == "translate_synthesize"
        model = _get_output_model(step)
        assert model is TranslateSynthesizeOutput

    def test_invalid_yaml_raises_recipe_error(self, tmp_path: Path) -> None:
        """Malformed YAML is wrapped in RecipeError, not bare yaml.YAMLError (D5)."""
        path = tmp_path / "bad.yaml"
        path.write_text("{{{{not: yaml: at: all")
        with pytest.raises(RecipeError, match="invalid YAML"):
            _load_recipe(path)


class TestParseInput:

    def test_json_string(self) -> None:
        result = _parse_input('{"problem": "test"}')
        assert result == {"problem": "test"}

    def test_at_file(self, tmp_path: Path) -> None:
        path = tmp_path / "input.json"
        path.write_text('{"problem": "from file"}')
        result = _parse_input(f"@{path}")
        assert result == {"problem": "from file"}

    def test_missing_at_file(self) -> None:
        with pytest.raises(RecipeError, match="input file not found"):
            _parse_input("@/nonexistent/path.json")

    def test_malformed_json(self) -> None:
        with pytest.raises(RecipeError, match="invalid input JSON"):
            _parse_input("{bad json")


# ═══════════════════════════════════════════════════════════════════════
# REFS — reference resolution (pure function, isolated)
# ═══════════════════════════════════════════════════════════════════════


class TestResolveRefs:

    def test_literal_value_passthrough(self) -> None:
        result = _resolve_refs({"key": "plain_string"}, {}, Path("/unused"))
        assert result == {"key": "plain_string"}

    def test_input_ref_field(self) -> None:
        result = _resolve_refs(
            {"src": "$input.problem"},
            {"problem": "the question"},
            Path("/unused"),
        )
        assert result == {"src": "the question"}

    def test_input_ref_whole(self) -> None:
        recipe_input = {"problem": "x", "extra": "y"}
        result = _resolve_refs({"src": "$input"}, recipe_input, Path("/unused"))
        assert result == {"src": recipe_input}

    def test_step_ref_field(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "decompose.json").write_text(
            json.dumps({"axioms": [{"statement": "A"}]})
        )
        result = _resolve_refs({"src": "$decompose.axioms"}, {}, state_dir)
        assert result == {"src": [{"statement": "A"}]}

    def test_step_ref_whole(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        data: dict[str, Any] = {"axioms": [], "derivations": [], "assumptions": []}
        (state_dir / "decompose.json").write_text(json.dumps(data))
        result = _resolve_refs({"src": "$decompose"}, {}, state_dir)
        assert result == {"src": data}

    def test_missing_step_file(self, tmp_path: Path) -> None:
        with pytest.raises(ReferenceError_, match="does not exist"):
            _resolve_refs({"src": "$invert.failure_modes"}, {}, tmp_path)

    def test_missing_field_in_source(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "decompose.json").write_text(json.dumps({"axioms": []}))
        with pytest.raises(ReferenceError_, match="field.*nonexistent.*not found"):
            _resolve_refs({"src": "$decompose.nonexistent"}, {}, state_dir)


# ═══════════════════════════════════════════════════════════════════════
# LIFECYCLE — FSM happy paths
# ═══════════════════════════════════════════════════════════════════════


class TestLifecycle:

    def test_start_creates_session_structure(self, minimal_recipe: Path) -> None:
        sid = _start_session(minimal_recipe)
        d = _session_dir(sid)
        assert d.exists()
        assert (d / "meta.json").exists()
        assert (d / "pending").is_dir()
        assert (d / "state").is_dir()
        assert (d / "recipe.yaml").exists()
        assert (d / "input.json").exists()

    def test_start_meta_initial_state(self, minimal_recipe: Path) -> None:
        sid = _start_session(minimal_recipe)
        meta = _read_meta(sid)
        assert meta["status"] == "running"
        assert meta["current_step"] == "decompose"
        assert meta["budget_used"] == 0
        assert meta["budget_ceiling"] == 7
        for step_info in meta["steps"].values():
            assert step_info["status"] == "pending"

    def test_start_returns_session_id(self, minimal_recipe: Path) -> None:
        sid = _start_session(minimal_recipe)
        assert isinstance(sid, str)
        assert len(sid) > 10

    def test_start_custom_budget(self, minimal_recipe: Path) -> None:
        sid = _start_session(minimal_recipe, budget=3)
        meta = _read_meta(sid)
        assert meta["budget_ceiling"] == 3

    def test_start_runner_cmd_override(self, minimal_recipe: Path) -> None:
        sid = _start_session(minimal_recipe, runner_cmd="custom run cmd")
        meta = _read_meta(sid)
        assert meta["runner_cmd"] == "custom run cmd"

    def test_two_step_complete_flow(
        self,
        minimal_recipe: Path,
        valid_decompose_output: dict,
        valid_synthesize_output: dict,
    ) -> None:
        sid = _session_at(minimal_recipe, completed_steps={
            "decompose": valid_decompose_output,
        })
        _write_pending(sid, "synthesize", valid_synthesize_output)
        meta = _do_submit(sid, "synthesize")

        assert meta["status"] == "completed"
        assert meta["current_step"] is None
        assert meta["budget_used"] == 2
        assert meta["steps"]["decompose"]["status"] == "completed"
        assert meta["steps"]["synthesize"]["status"] == "completed"

    def test_submit_persists_validated_output(
        self,
        minimal_recipe: Path,
        valid_decompose_output: dict,
    ) -> None:
        """State file contains model_dump() output, not raw input (FM-2 fix)."""
        sid = _start_session(minimal_recipe)
        _write_pending(sid, "decompose", valid_decompose_output)
        _do_submit(sid, "decompose")

        state_path = _session_dir(sid) / "state" / "decompose.json"
        assert state_path.exists()
        persisted = json.loads(state_path.read_text())
        expected = DecomposeOutput.model_validate(valid_decompose_output).model_dump()
        assert persisted == expected

    def test_submit_removes_pending_file(
        self,
        minimal_recipe: Path,
        valid_decompose_output: dict,
    ) -> None:
        sid = _start_session(minimal_recipe)
        pending = _write_pending(sid, "decompose", valid_decompose_output)
        assert pending.exists()
        _do_submit(sid, "decompose")
        assert not pending.exists()

    def test_submit_advances_current_step(
        self,
        minimal_recipe: Path,
        valid_decompose_output: dict,
    ) -> None:
        sid = _start_session(minimal_recipe)
        _write_pending(sid, "decompose", valid_decompose_output)
        _do_submit(sid, "decompose")
        meta = _read_meta(sid)
        assert meta["current_step"] == "synthesize"

    def test_submit_records_artifact_id(
        self,
        minimal_recipe: Path,
        valid_decompose_output: dict,
    ) -> None:
        sid = _start_session(minimal_recipe)
        _write_pending(sid, "decompose", valid_decompose_output)
        _do_submit(sid, "decompose")
        meta = _read_meta(sid)
        step_meta = meta["steps"]["decompose"]
        assert step_meta["artifact_id"] is not None
        assert step_meta["output_path"] == "state/decompose.json"
        assert step_meta["completed_at"] is not None

    def test_three_step_complete_flow(
        self,
        three_step_recipe: Path,
        valid_decompose_output: dict,
        valid_invert_output: dict,
        valid_synthesize_output: dict,
    ) -> None:
        sid = _session_at(three_step_recipe, completed_steps={
            "decompose": valid_decompose_output,
            "invert": valid_invert_output,
        })
        _write_pending(sid, "synthesize", valid_synthesize_output)
        meta = _do_submit(sid, "synthesize")

        assert meta["status"] == "completed"
        assert meta["budget_used"] == 3

    def test_status_reports_running_session(self, minimal_recipe: Path) -> None:
        sid = _start_session(minimal_recipe)
        meta = _do_status(sid, persist=False)
        assert meta["status"] == "running"
        assert meta["current_step"] == "decompose"

    def test_status_persist_flag(self, minimal_recipe: Path) -> None:
        sid = _start_session(minimal_recipe)
        meta = _do_status(sid, persist=True)
        assert meta["persist"] is True
        meta_disk = _read_meta(sid)
        assert meta_disk["persist"] is True


# ═══════════════════════════════════════════════════════════════════════
# FAILURES — every error path
# ═══════════════════════════════════════════════════════════════════════


class TestFailures:

    def test_submit_wrong_step(
        self,
        minimal_recipe: Path,
        valid_synthesize_output: dict,
    ) -> None:
        sid = _start_session(minimal_recipe)
        _write_pending(sid, "synthesize", valid_synthesize_output)
        with pytest.raises(SessionError, match="current step is.*decompose.*not.*synthesize"):
            _do_submit(sid, "synthesize")

    def test_submit_session_not_found(self) -> None:
        with pytest.raises(SessionError, match="not found"):
            _do_submit("bogus-session-id", "decompose")

    def test_submit_session_already_completed(
        self,
        minimal_recipe: Path,
        valid_decompose_output: dict,
        valid_synthesize_output: dict,
    ) -> None:
        sid = _session_at(minimal_recipe, completed_steps={
            "decompose": valid_decompose_output,
            "synthesize": valid_synthesize_output,
        })
        _write_pending(sid, "synthesize", valid_synthesize_output)
        with pytest.raises(SessionError, match="not 'running'"):
            _do_submit(sid, "synthesize")

    def test_submit_no_pending_file(self, minimal_recipe: Path) -> None:
        sid = _start_session(minimal_recipe)
        with pytest.raises(StepError, match="no pending output"):
            _do_submit(sid, "decompose")

    def test_submit_malformed_json(self, minimal_recipe: Path) -> None:
        sid = _start_session(minimal_recipe)
        pending = _session_dir(sid) / "pending" / "decompose.json"
        pending.write_text("{bad json")
        with pytest.raises(StepError, match="invalid JSON"):
            _do_submit(sid, "decompose")

    def test_submit_non_object_json(self, minimal_recipe: Path) -> None:
        sid = _start_session(minimal_recipe)
        pending = _session_dir(sid) / "pending" / "decompose.json"
        pending.write_text("[1, 2, 3]")
        with pytest.raises(StepError, match="expected a JSON object"):
            _do_submit(sid, "decompose")

    def test_validation_failure_attempt_1(self, minimal_recipe: Path) -> None:
        """First validation failure: session stays running, attempt recorded."""
        sid = _start_session(minimal_recipe)
        _write_pending(sid, "decompose", {"bad": "data"})
        with pytest.raises(StepError, match="attempt 1"):
            _do_submit(sid, "decompose")

        meta = _read_meta(sid)
        assert meta["status"] == "running"
        assert meta["steps"]["decompose"]["attempts"] == 1
        assert len(meta["steps"]["decompose"]["errors"]) == 1

    def test_validation_failure_attempt_2_fails_hard(self, minimal_recipe: Path) -> None:
        """Second validation failure: session marked failed."""
        sid = _start_session(minimal_recipe)

        _write_pending(sid, "decompose", {"bad": "data"})
        with pytest.raises(StepError):
            _do_submit(sid, "decompose")

        _write_pending(sid, "decompose", {"still": "bad"})
        with pytest.raises(StepError, match="failed validation after 2 attempts"):
            _do_submit(sid, "decompose")

        meta = _read_meta(sid)
        assert meta["status"] == "failed"

    def test_validation_repair_succeeds(
        self,
        minimal_recipe: Path,
        valid_decompose_output: dict,
    ) -> None:
        """First attempt fails, second with correct data succeeds."""
        sid = _start_session(minimal_recipe)

        _write_pending(sid, "decompose", {"bad": "data"})
        with pytest.raises(StepError):
            _do_submit(sid, "decompose")

        _write_pending(sid, "decompose", valid_decompose_output)
        _do_submit(sid, "decompose")

        meta = _read_meta(sid)
        assert meta["status"] == "running"
        assert meta["steps"]["decompose"]["status"] == "completed"
        assert meta["steps"]["decompose"]["attempts"] == 2

    def test_budget_exhaustion(
        self,
        three_step_recipe: Path,
        valid_decompose_output: dict,
        valid_invert_output: dict,
    ) -> None:
        """Budget=2 on a 3-step recipe: third step never emitted."""
        sid = _session_at(three_step_recipe, completed_steps={
            "decompose": valid_decompose_output,
        }, budget=2)

        _write_pending(sid, "invert", valid_invert_output)
        with pytest.raises(SessionError, match="budget exhausted"):
            _do_submit(sid, "invert")

        meta = _read_meta(sid)
        assert meta["status"] == "budget_exhausted"

    def test_final_step_completes_before_budget_check(
        self,
        minimal_recipe: Path,
        valid_decompose_output: dict,
        valid_synthesize_output: dict,
    ) -> None:
        """Budget=2 on a 2-step recipe: completes normally.

        Final-step check runs before budget check (FM-5 Part B).
        """
        sid = _session_at(minimal_recipe, completed_steps={
            "decompose": valid_decompose_output,
        }, budget=2)

        _write_pending(sid, "synthesize", valid_synthesize_output)
        meta = _do_submit(sid, "synthesize")

        assert meta["status"] == "completed"

    def test_ad_hoc_step_skips_validation(self, tmp_path: Path) -> None:
        """Step with no operator and no output_model accepts any JSON object."""
        data = {
            "name": "ad-hoc-recipe",
            "steps": {
                "custom": {
                    "prompt": "do something custom",
                    "output": {"result": "str"},
                },
            },
            "flow": ["custom"],
        }
        recipe_path = tmp_path / "adhoc.yaml"
        recipe_path.write_text(yaml.dump(data))

        sid = _start_session(recipe_path)
        _write_pending(sid, "custom", {"anything": "goes", "nested": {"ok": True}})
        meta = _do_submit(sid, "custom")

        assert meta["status"] == "completed"

    def test_status_session_not_found(self) -> None:
        with pytest.raises(SessionError, match="not found"):
            _do_status("nonexistent-session", persist=False)


# ═══════════════════════════════════════════════════════════════════════
# GC — stale session cleanup
# ═══════════════════════════════════════════════════════════════════════


class TestGC:

    def _create_session_dir(
        self,
        state_root: Path,
        name: str,
        *,
        status: str = "running",
        persist: bool = False,
        hours_ago: float = 25.0,
    ) -> Path:
        """Create a session directory with controlled meta.json."""
        d = state_root / name
        d.mkdir(parents=True)
        updated = datetime.now(timezone.utc).timestamp() - (hours_ago * 3600)
        updated_dt = datetime.fromtimestamp(updated, tz=timezone.utc)
        meta = {
            "session_id": name,
            "recipe_name": "test",
            "status": status,
            "current_step": "step1",
            "budget_used": 0,
            "budget_ceiling": 7,
            "persist": persist,
            "created_at": updated_dt.isoformat(),
            "updated_at": updated_dt.isoformat(),
            "steps": {},
        }
        (d / "meta.json").write_text(json.dumps(meta))
        return d

    def test_removes_stale_running_session(self, _isolate_state: Path) -> None:
        d = self._create_session_dir(_isolate_state, "stale-1", hours_ago=25)
        _gc_stale_sessions()
        assert not d.exists()

    def test_preserves_recent_session(self, _isolate_state: Path) -> None:
        d = self._create_session_dir(_isolate_state, "recent-1", hours_ago=23)
        _gc_stale_sessions()
        assert d.exists()

    def test_preserves_completed_session(self, _isolate_state: Path) -> None:
        d = self._create_session_dir(
            _isolate_state, "done-1", status="completed", hours_ago=48,
        )
        _gc_stale_sessions()
        assert d.exists()

    def test_preserves_persisted_session(self, _isolate_state: Path) -> None:
        d = self._create_session_dir(
            _isolate_state, "persist-1", persist=True, hours_ago=48,
        )
        _gc_stale_sessions()
        assert d.exists()

    def test_handles_corrupt_meta(self, _isolate_state: Path) -> None:
        """Corrupt meta.json doesn't crash GC or affect other sessions."""
        corrupt = _isolate_state / "corrupt-1"
        corrupt.mkdir()
        (corrupt / "meta.json").write_text("not json")

        stale = self._create_session_dir(_isolate_state, "stale-2", hours_ago=25)
        _gc_stale_sessions()
        assert corrupt.exists()
        assert not stale.exists()

    def test_handles_missing_state_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """GC with nonexistent STATE_ROOT doesn't crash."""
        monkeypatch.setattr(fsm_runner, "STATE_ROOT", tmp_path / "nonexistent")
        _gc_stale_sessions()

    def test_gc_boundary_just_under_24h(self, _isolate_state: Path) -> None:
        """Session just under 24h is NOT removed (> not >=)."""
        d = self._create_session_dir(_isolate_state, "boundary-1", hours_ago=23.9)
        _gc_stale_sessions()
        assert d.exists()


# ═══════════════════════════════════════════════════════════════════════
# CLI — Click surface smoke tests (AS4, AS5)
# ═══════════════════════════════════════════════════════════════════════


class TestCLI:
    """Minimal smoke tests for the Click CLI surface.

    Core logic is tested via _do_* functions above. These verify
    the Click wrappers don't crash and expose basic functionality.
    """

    def test_start_prints_session_id(self, minimal_recipe: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, [
            "start",
            "--recipe", str(minimal_recipe),
            "--input", '{"problem": "test"}',
        ])
        assert result.exit_code == 0
        assert "Session:" in result.output

    def test_start_missing_recipe_fails(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, [
            "start",
            "--recipe", "/nonexistent/recipe.yaml",
            "--input", "{}",
        ])
        assert result.exit_code != 0

    def test_list_empty(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["list"])
        assert result.exit_code == 0

    def test_list_shows_sessions(self, minimal_recipe: Path) -> None:
        _start_session(minimal_recipe)
        _start_session(minimal_recipe)
        runner = CliRunner()
        result = runner.invoke(cli, ["list"])
        assert result.exit_code == 0
        assert "test-recipe" in result.output
