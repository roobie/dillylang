"""FSM recipe runner — enforces step boundaries via schema validation.

Three commands:
  start   — parse recipe, create session, emit first step
  submit  — validate pending output, persist, emit next step (or complete)
  status  — show session state

The runner never calls an LLM. The agent LLM in-session is the executor.
Enforcement comes from the emit/submit/validate handshake: step N+1 is
not emitted until step N's output validates against the canonical Pydantic
model from dillylang.vocab.schemas.

Session state lives in ~/.local/state/dillylang/sessions/<id>/.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click
import yaml
from pydantic import BaseModel, ValidationError


# ── Runner exceptions ──────────────────────────────────────────────────
# Domain logic raises these; click commands catch at top level.


class RunnerError(Exception):
    """Base for all runner errors."""


class RecipeError(RunnerError):
    """Recipe parsing or structural validation failed."""


class ReferenceError_(RunnerError):
    """Step or input reference could not be resolved."""


class SessionError(RunnerError):
    """Session not found or in wrong state."""


class StepError(RunnerError):
    """Step validation or submission failed."""

# ── Operator output model registry ──────────────────────────────────────
# Maps operator names from recipe YAML to canonical Pydantic output models.
# The runner imports these lazily to avoid breaking if vocab evolves.

_OPERATOR_OUTPUT_MODELS: dict[str, type[BaseModel]] | None = None


def _load_operator_registry() -> dict[str, type[BaseModel]]:
    global _OPERATOR_OUTPUT_MODELS
    if _OPERATOR_OUTPUT_MODELS is not None:
        return _OPERATOR_OUTPUT_MODELS

    from dillylang.vocab.schemas import (
        AbstractOutput,
        AnalogizeOutput,
        ClassifyOutput,
        CompareOutput,
        ConcretizeOutput,
        ConstrainOutput,
        DecomposeOutput,
        DesignSynthesizeOutput,
        EvaluateOutput,
        ImproveOutput,
        ImproveSynthesizeOutput,
        InvertOutput,
        RankOutput,
        RelaxOutput,
        RotateOutput,
        SynthesizeOutput,
        TranslateSynthesizeOutput,
    )

    _OPERATOR_OUTPUT_MODELS = {
        "decompose": DecomposeOutput,
        "synthesize": SynthesizeOutput,
        "invert": InvertOutput,
        "rotate": RotateOutput,
        "analogize": AnalogizeOutput,
        "evaluate": EvaluateOutput,
        "rank": RankOutput,
        "classify": ClassifyOutput,
        "abstract": AbstractOutput,
        "concretize": ConcretizeOutput,
        "constrain": ConstrainOutput,
        "relax": RelaxOutput,
        "compare": CompareOutput,
        # Extended models for specific recipes
        "translate_synthesize": TranslateSynthesizeOutput,
        "design_synthesize": DesignSynthesizeOutput,
        "improve_synthesize": ImproveSynthesizeOutput,
        "improve": ImproveOutput,
    }
    return _OPERATOR_OUTPUT_MODELS


# ── Session paths ───────────────────────────────────────────────────────

STATE_ROOT = Path(
    os.environ.get(
        "DILLYLANG_STATE_DIR",
        Path.home() / ".local" / "state" / "dillylang" / "sessions",
    )
)


def _session_dir(session_id: str) -> Path:
    return STATE_ROOT / session_id


# ── Recipe parsing ──────────────────────────────────────────────────────


class RecipeStep:
    """Parsed recipe step with resolved metadata."""

    def __init__(self, name: str, raw: dict[str, Any]) -> None:
        self.name = name
        self.operator: str | None = raw.get("operator")
        self.params: dict[str, Any] = raw.get("params", {})
        self.input_refs: dict[str, str] = raw.get("input", {})
        self.prompt: str = raw.get("prompt", "")
        self.output_doc: dict[str, Any] = raw.get("output", {})
        # Allow per-step override of the validation model name
        self.output_model_key: str | None = raw.get("output_model")


class Recipe:
    """Parsed YAML recipe."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.name: str = data["name"]
        self.description: str = data.get("description", "")
        self.input_spec: dict[str, str] = data.get("input", {})
        self.steps: dict[str, RecipeStep] = {}
        self.flow: list[str] = data.get("flow", [])

        for step_name, step_data in data.get("steps", {}).items():
            self.steps[step_name] = RecipeStep(step_name, step_data)

    def validate_structure(self) -> list[str]:
        """Check recipe internal consistency. Returns list of errors."""
        errors: list[str] = []

        if not self.flow:
            errors.append("recipe has no flow: key")

        for step_name in self.flow:
            if step_name not in self.steps:
                errors.append(f"flow references undefined step '{step_name}'")

        # Check $references resolve against earlier steps in flow
        seen: set[str] = set()
        for step_name in self.flow:
            step = self.steps.get(step_name)
            if step is None:
                continue
            for _ref_key, ref_value in step.input_refs.items():
                if not isinstance(ref_value, str) or not ref_value.startswith("$"):
                    continue
                target = ref_value.lstrip("$").split(".")[0]
                if target == "input":
                    continue
                if target not in seen:
                    errors.append(
                        f"step '{step_name}' references '${ target}' "
                        f"which hasn't completed yet in flow order"
                    )
            seen.add(step_name)

        return errors


def _load_recipe(path: Path) -> Recipe:
    """Parse and validate a YAML recipe file."""
    text = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RecipeError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RecipeError(f"recipe file is not a YAML mapping: {path}")
    recipe = Recipe(data)
    errors = recipe.validate_structure()
    if errors:
        detail = "; ".join(errors)
        raise RecipeError(f"recipe validation failed: {detail}")
    return recipe


# ── Reference resolution ────────────────────────────────────────────────


def _resolve_refs(
    input_refs: dict[str, str],
    recipe_input: dict[str, Any],
    state_dir: Path,
) -> dict[str, Any]:
    """Resolve $input and $step references to actual data."""
    resolved: dict[str, Any] = {}

    for key, ref in input_refs.items():
        if not isinstance(ref, str) or not ref.startswith("$"):
            resolved[key] = ref
            continue

        parts = ref.lstrip("$").split(".", 1)
        source_name = parts[0]

        if source_name == "input":
            data = recipe_input
        else:
            state_file = state_dir / f"{source_name}.json"
            if not state_file.exists():
                raise ReferenceError_(
                    f"reference '{ref}' resolves to {state_file} which does not exist"
                )
            data = json.loads(state_file.read_text())

        # Optionally resolve a top-level field
        if len(parts) == 2:
            field = parts[1]
            if isinstance(data, dict) and field in data:
                data = data[field]
            else:
                raise ReferenceError_(
                    f"reference '{ref}' — field '{field}' not found in source data"
                )

        resolved[key] = data

    return resolved


# ── Step emission ───────────────────────────────────────────────────────


def _emit_step(
    step: RecipeStep,
    resolved_inputs: dict[str, Any],
    session_id: str,
    session_dir: Path,
    step_index: int,
    total_steps: int,
    meta: dict[str, Any] | None = None,
) -> None:
    """Print the step prompt and submit instructions to stdout."""
    click.echo(f"\n{'='*60}")
    click.echo(f"STEP {step_index + 1}/{total_steps} — {step.name}")
    if step.operator:
        click.echo(f"Operator: {step.operator}")
    click.echo(f"{'='*60}\n")

    # Show params if any
    if step.params:
        click.echo("Parameters:")
        for k, v in step.params.items():
            if isinstance(v, str) and "\n" in v:
                click.echo(f"  {k}: |")
                for line in v.rstrip("\n").split("\n"):
                    click.echo(f"    {line}")
            else:
                click.echo(f"  {k}: {json.dumps(v) if not isinstance(v, str) else v}")
        click.echo()

    # Show resolved inputs
    if resolved_inputs:
        click.echo("Resolved inputs:")
        for k, v in resolved_inputs.items():
            serialized = json.dumps(v, indent=2) if not isinstance(v, str) else v
            click.echo(f"  {k}:")
            for line in serialized.split("\n"):
                click.echo(f"    {line}")
        click.echo()

    # Show prompt
    click.echo("Prompt:")
    click.echo(step.prompt)

    # Show expected output shape (documentary)
    if step.output_doc:
        click.echo("Expected output shape:")
        for field, ftype in step.output_doc.items():
            click.echo(f"  {field}: {ftype}")
        click.echo()

    # Submit instructions
    pending_path = session_dir / "pending" / f"{step.name}.json"
    click.echo(f"Write your JSON output to:\n  {pending_path}\n")
    cmd = _runner_cmd(meta) if meta else _self_cmd()
    click.echo(f"Then run:\n  {cmd} submit --session {session_id} --step {step.name}")
    click.echo()


_DEFAULT_RUNNER_CMD = "mise x -- uv run -m dillylang.agent_skills.fsm_runner"


def _self_cmd() -> str:
    """Return the command to invoke this module (legacy fallback)."""
    return "mise x -- uv run -m dillylang.agent_skills.fsm_runner"


def _runner_cmd(meta: dict[str, Any]) -> str:
    """Return the configured runner command, or the default."""
    return meta.get("runner_cmd", _DEFAULT_RUNNER_CMD)


# ── Validation ──────────────────────────────────────────────────────────


def _get_output_model(step: RecipeStep) -> type[BaseModel] | None:
    """Resolve the Pydantic model for validating this step's output."""
    # Per-step override first
    model_key = step.output_model_key or step.operator
    if model_key is None:
        return None

    registry = _load_operator_registry()
    return registry.get(model_key)


def _validate_output(step: RecipeStep, data: dict[str, Any]) -> BaseModel | None:
    """Validate step output against canonical schema. Returns model instance or None."""
    model_cls = _get_output_model(step)
    if model_cls is None:
        # Ad-hoc step — no canonical model, accept any valid JSON object
        return None
    return model_cls.model_validate(data)


# ── Meta management ─────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _init_meta(session_id: str, recipe: Recipe) -> dict[str, Any]:
    """Create initial meta.json content."""
    steps_meta: dict[str, Any] = {}
    for step_name in recipe.flow:
        steps_meta[step_name] = {
            "status": "pending",
            "artifact_id": None,
            "output_path": None,
            "attempts": 0,
            "completed_at": None,
            "errors": [],
        }

    first_step = recipe.flow[0] if recipe.flow else None

    return {
        "meta_version": 1,
        "session_id": session_id,
        "recipe_name": recipe.name,
        "runner": "fsm_runner",
        "status": "running",
        "current_step": first_step,
        "budget_used": 0,
        "budget_ceiling": 7,
        "persist": False,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "steps": steps_meta,
    }


def _read_meta(session_dir: Path) -> dict[str, Any]:
    return json.loads((session_dir / "meta.json").read_text())


def _write_meta(session_dir: Path, meta: dict[str, Any]) -> None:
    meta["updated_at"] = _now_iso()
    (session_dir / "meta.json").write_text(json.dumps(meta, indent=2))


# ── GC ──────────────────────────────────────────────────────────────────


_GC_WINDOW_HOURS = 24


def _gc_stale_sessions() -> None:
    """Remove FSM runner sessions stale for >24h that are still 'running'."""
    if not STATE_ROOT.exists():
        return
    now = datetime.now(timezone.utc)
    for d in STATE_ROOT.iterdir():
        if not d.is_dir():
            continue
        meta_path = d / "meta.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        # Only GC sessions owned by this runner (legacy sessions default to fsm_runner)
        if meta.get("runner", "fsm_runner") != "fsm_runner":
            continue
        if meta.get("status") != "running":
            continue
        if meta.get("persist"):
            continue
        updated = meta.get("updated_at", "")
        try:
            updated_dt = datetime.fromisoformat(updated)
        except (ValueError, TypeError):
            continue
        age_hours = (now - updated_dt).total_seconds() / 3600
        if age_hours > _GC_WINDOW_HOURS:
            shutil.rmtree(d, ignore_errors=True)


# ── CLI commands ────────────────────────────────────────────────────────


@click.group()
def cli() -> None:
    """Dillylang FSM recipe runner."""


@cli.command()
@click.option("--recipe", "-r", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--input", "-i", "input_json", required=True, help="JSON string or @file path")
@click.option("--budget", "-b", default=7, type=int, help="Max step count (default: 7)")
@click.option("--persist", is_flag=True, help="Preserve session beyond GC window")
@click.option("--runner-cmd", default=None, help="Override runner invocation command in emitted instructions")
def start(recipe: Path, input_json: str, budget: int, persist: bool, runner_cmd: str | None) -> None:
    """Parse recipe, create session, emit first step."""
    try:
        _do_start(recipe, input_json, budget, persist, runner_cmd=runner_cmd)
    except RunnerError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


def _parse_input(input_json: str) -> dict[str, Any]:
    """Parse input from JSON string or @file reference."""
    if input_json.startswith("@"):
        input_path = Path(input_json[1:])
        if not input_path.exists():
            raise RecipeError(f"input file not found: {input_path}")
        return json.loads(input_path.read_text())
    try:
        return json.loads(input_json)
    except json.JSONDecodeError as exc:
        raise RecipeError(f"invalid input JSON: {exc}") from exc


def _do_start(
    recipe: Path, input_json: str, budget: int, persist: bool,
    *, runner_cmd: str | None = None,
) -> str:
    """Core start logic. Returns session_id."""
    _gc_stale_sessions()
    raw_input = _parse_input(input_json)
    parsed_recipe = _load_recipe(recipe)

    # Create session
    session_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    session_dir = _session_dir(session_id)
    session_dir.mkdir(parents=True, mode=0o700)
    (session_dir / "pending").mkdir(mode=0o700)
    (session_dir / "state").mkdir(mode=0o700)

    # Persist recipe and input
    shutil.copy2(recipe, session_dir / "recipe.yaml")
    (session_dir / "input.json").write_text(json.dumps(raw_input, indent=2))
    os.chmod(session_dir / "input.json", 0o600)

    # Init meta
    meta = _init_meta(session_id, parsed_recipe)
    meta["budget_ceiling"] = budget
    meta["persist"] = persist
    if runner_cmd:
        meta["runner_cmd"] = runner_cmd
    _write_meta(session_dir, meta)

    click.echo(f"Session: {session_id}")
    click.echo(f"Recipe:  {parsed_recipe.name}")
    click.echo(f"Steps:   {' → '.join(parsed_recipe.flow)}")
    click.echo(f"Budget:  0/{budget}")

    # Emit first step
    first_step_name = parsed_recipe.flow[0]
    first_step = parsed_recipe.steps[first_step_name]
    resolved = _resolve_refs(first_step.input_refs, raw_input, session_dir / "state")
    _emit_step(first_step, resolved, session_id, session_dir, 0, len(parsed_recipe.flow), meta=meta)
    return session_id


@cli.command()
@click.option("--session", "-s", required=True, help="Session ID")
@click.option("--step", required=True, help="Step name to submit output for")
def submit(session: str, step: str) -> None:
    """Validate pending output, persist to state, emit next step."""
    try:
        _do_submit(session, step)
    except RunnerError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


def _do_submit(session: str, step: str) -> dict[str, Any]:
    """Core submit logic. Returns final meta state."""
    session_dir = _session_dir(session)
    if not session_dir.exists():
        raise SessionError(f"session not found: {session}")

    meta = _read_meta(session_dir)

    if meta["status"] != "running":
        raise SessionError(f"session status is '{meta['status']}', not 'running'")

    if meta["current_step"] != step:
        raise SessionError(
            f"current step is '{meta['current_step']}', not '{step}'"
        )

    # Load recipe
    parsed_recipe = _load_recipe(session_dir / "recipe.yaml")
    recipe_step = parsed_recipe.steps.get(step)
    if recipe_step is None:
        raise StepError(f"step '{step}' not found in recipe")

    # Read pending output
    pending_path = session_dir / "pending" / f"{step}.json"
    if not pending_path.exists():
        raise StepError(
            f"no pending output at {pending_path} — "
            f"write your JSON output there, then re-run this command"
        )

    try:
        raw_data = json.loads(pending_path.read_text())
    except json.JSONDecodeError as exc:
        raise StepError(f"invalid JSON in {pending_path}: {exc}") from exc

    if not isinstance(raw_data, dict):
        raise StepError(f"expected a JSON object, got {type(raw_data).__name__}")

    # Track attempt
    step_meta = meta["steps"][step]
    step_meta["attempts"] += 1

    # Validate
    try:
        validated = _validate_output(recipe_step, raw_data)
    except ValidationError as exc:
        step_meta["errors"].append(str(exc))
        _write_meta(session_dir, meta)

        max_attempts = 2  # repair-once-then-fail
        if step_meta["attempts"] >= max_attempts:
            meta["status"] = "failed"
            _write_meta(session_dir, meta)
            raise StepError(
                f"step '{step}' failed validation after {max_attempts} attempts:\n{exc}"
            ) from exc

        click.echo(f"\nValidation error (attempt {step_meta['attempts']}/{max_attempts}):", err=True)
        click.echo(f"{exc}", err=True)
        cmd = _runner_cmd(meta)
        click.echo(f"\nFix the output and resubmit:\n  {cmd} submit --session {session} --step {step}")
        raise StepError(
            f"validation failed on attempt {step_meta['attempts']}/{max_attempts}"
        ) from exc

    # Persist validated output to state (FM-2: use model_dump for normalized data)
    persisted_data = validated.model_dump() if validated is not None else raw_data
    state_path = session_dir / "state" / f"{step}.json"
    state_path.write_text(json.dumps(persisted_data, indent=2))
    os.chmod(state_path, 0o600)
    pending_path.unlink()

    # Update meta
    step_meta["status"] = "completed"
    step_meta["artifact_id"] = str(uuid.uuid4())
    step_meta["output_path"] = f"state/{step}.json"
    step_meta["completed_at"] = _now_iso()
    meta["budget_used"] += 1
    _write_meta(session_dir, meta)

    click.echo(f"\n✓ Step '{step}' validated and persisted.")
    click.echo(f"  Budget: {meta['budget_used']}/{meta['budget_ceiling']}")

    # Find and emit next step
    flow = parsed_recipe.flow
    current_index = flow.index(step)

    if current_index + 1 >= len(flow):
        # Final step — session complete (checked before budget: FM-5 Part B)
        meta["status"] = "completed"
        meta["current_step"] = None
        _write_meta(session_dir, meta)

        click.echo(f"\n{'='*60}")
        click.echo("WORKFLOW COMPLETE")
        click.echo(f"{'='*60}")
        click.echo(f"\nSession: {session}")
        click.echo(f"Steps completed: {meta['budget_used']}")

        # Print final step output
        click.echo(f"\nFinal output ({step}):")
        click.echo(state_path.read_text())
        return meta

    # Budget check (after final-step check: FM-5 Part B)
    if meta["budget_used"] >= meta["budget_ceiling"]:
        meta["status"] = "budget_exhausted"
        _write_meta(session_dir, meta)
        click.echo("\nBudget exhausted — no further steps will be emitted.", err=True)
        raise SessionError("budget exhausted")

    # Advance to next step
    next_step_name = flow[current_index + 1]
    meta["current_step"] = next_step_name
    _write_meta(session_dir, meta)

    next_step = parsed_recipe.steps[next_step_name]
    recipe_input = json.loads((session_dir / "input.json").read_text())
    resolved = _resolve_refs(next_step.input_refs, recipe_input, session_dir / "state")
    _emit_step(
        next_step, resolved, session, session_dir,
        current_index + 1, len(flow), meta=meta,
    )
    return meta


@cli.command()
@click.option("--session", "-s", required=True, help="Session ID")
@click.option("--persist", is_flag=True, help="Mark session for preservation")
def status(session: str, persist: bool) -> None:
    """Show session state."""
    try:
        _do_status(session, persist)
    except RunnerError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


def _do_status(session: str, persist: bool) -> dict[str, Any]:
    """Core status logic. Returns meta dict."""
    session_dir = _session_dir(session)
    if not session_dir.exists():
        raise SessionError(f"session not found: {session}")

    meta = _read_meta(session_dir)

    if persist and not meta.get("persist"):
        meta["persist"] = True
        _write_meta(session_dir, meta)
        click.echo("Session marked for persistence.")

    click.echo(f"Session:  {meta['session_id']}")
    click.echo(f"Recipe:   {meta['recipe_name']}")
    click.echo(f"Status:   {meta['status']}")
    click.echo(f"Step:     {meta['current_step'] or '(done)'}")
    click.echo(f"Budget:   {meta['budget_used']}/{meta['budget_ceiling']}")
    click.echo(f"Persist:  {meta.get('persist', False)}")
    click.echo(f"Created:  {meta['created_at']}")
    click.echo(f"Updated:  {meta['updated_at']}")
    click.echo()

    for step_name, step_info in meta["steps"].items():
        marker = "✓" if step_info["status"] == "completed" else "○"
        if step_info["status"] == "pending" and step_name == meta["current_step"]:
            marker = "→"
        attempts = f" ({step_info['attempts']} attempts)" if step_info["attempts"] > 1 else ""
        click.echo(f"  {marker} {step_name}: {step_info['status']}{attempts}")

    return meta


@cli.command(name="list")
def list_sessions() -> None:
    """List all sessions."""
    if not STATE_ROOT.exists():
        click.echo("No sessions.")
        return

    sessions: list[tuple[str, dict[str, Any]]] = []
    for d in sorted(STATE_ROOT.iterdir()):
        if not d.is_dir():
            continue
        meta_path = d / "meta.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        # Only show sessions owned by this runner (legacy sessions default to fsm_runner)
        if meta.get("runner", "fsm_runner") != "fsm_runner":
            continue
        sessions.append((d.name, meta))

    if not sessions:
        click.echo("No sessions.")
        return

    for sid, meta in sessions:
        status_str = meta.get("status", "?")
        recipe = meta.get("recipe_name", "?")
        budget = f"{meta.get('budget_used', '?')}/{meta.get('budget_ceiling', '?')}"
        click.echo(f"  {sid}  {status_str:<10}  {recipe:<20}  budget: {budget}")


if __name__ == "__main__":
    cli()
