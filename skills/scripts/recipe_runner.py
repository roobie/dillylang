"""Lite recipe runner — prompt-session helper with Dillylang operator lineage.

Stdlib-only. No dillylang imports. The runner never calls an LLM; the agent
in-session is the executor. Enforcement comes from the emit/submit handshake.

Deletion criteria: If this gains more than 3 optional step fields or requires
dillylang imports, delete it and extend the FSM runner instead.

Commands:
  start   — load recipe, create session, emit first step(s)
  submit  — parse pending JSON, persist, advance
  status  — show session state
  list    — show recipe_runner sessions
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

STATE_ROOT = Path(os.environ.get(
    "DILLYLANG_STATE_ROOT",
    Path.home() / ".local" / "state" / "dillylang" / "sessions",
))
_GC_WINDOW_HOURS = 24
_STEP_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_DEFAULT_RUNNER_CMD = "python3 -m skills.scripts.recipe_runner"


# ── Helpers ───────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_identity(step: dict[str, Any]) -> bool:
    return step.get("operator") == "identity"


def _parse_input(raw: str | None) -> Any:
    """Parse JSON from string or @file. Returns {} if None."""
    if raw is None:
        return {}
    if raw.startswith("@"):
        p = Path(raw[1:])
        if not p.exists():
            _die(f"input file not found: {p}")
        return json.loads(p.read_text())
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        _die(f"invalid input JSON: {exc}")


def _die(msg: str) -> NoReturn:
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def _session_dir(session_id: str) -> Path:
    return STATE_ROOT / session_id


def _read_meta(session_dir: Path) -> dict[str, Any]:
    return json.loads((session_dir / "meta.json").read_text())


def _write_meta(session_dir: Path, meta: dict[str, Any]) -> None:
    meta["updated_at"] = _now_iso()
    (session_dir / "meta.json").write_text(json.dumps(meta, indent=2))


# ── Recipe loading ────────────────────────────────────────────────────────


def _load_recipe(path: Path) -> dict[str, Any]:
    """Import a .py file and return its `recipe` dict."""
    spec = importlib.util.spec_from_file_location("_recipe_module", path)
    if spec is None or spec.loader is None:
        _die(f"cannot load module from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    recipe = getattr(mod, "recipe", None)
    if not isinstance(recipe, dict):
        _die(f"{path} must export a `recipe` dict")
    return recipe


# ── Structural validation ─────────────────────────────────────────────────


def _validate_recipe(recipe: dict[str, Any]) -> list[str]:
    """Return list of error strings. Empty means valid."""
    errors: list[str] = []

    # Required top-level keys
    for key in ("name", "version", "steps", "flow"):
        if key not in recipe:
            errors.append(f"missing required key: {key}")
    if errors:
        return errors

    if not isinstance(recipe["name"], str) or not recipe["name"]:
        errors.append("'name' must be a non-empty string")
    if recipe.get("version") != 1:
        errors.append("'version' must be 1")
    if not isinstance(recipe["steps"], dict):
        errors.append("'steps' must be a dict")
        return errors
    if not isinstance(recipe["flow"], list) or not recipe["flow"]:
        errors.append("'flow' must be a non-empty list")
        return errors

    steps = recipe["steps"]
    flow = recipe["flow"]

    # Flatten flow for uniqueness check
    seen_in_flow: list[str] = []
    for item in flow:
        if isinstance(item, str):
            seen_in_flow.append(item)
        elif isinstance(item, list):
            if len(item) < 2:
                errors.append(f"parallel group must have >= 2 members: {item}")
            seen_in_flow.extend(item)
        else:
            errors.append(f"flow item must be str or list, got {type(item).__name__}")

    # Duplicate check
    names_seen: set[str] = set()
    for name in seen_in_flow:
        if name in names_seen:
            errors.append(f"duplicate step in flow: {name}")
        names_seen.add(name)

    # Step validation
    for name in seen_in_flow:
        if not _STEP_NAME_RE.match(name):
            errors.append(f"invalid step name: {name!r} (must match [a-z][a-z0-9_]*)")
        if name not in steps:
            errors.append(f"step '{name}' in flow but not in steps dict")
            continue
        step = steps[name]
        if not isinstance(step, dict):
            errors.append(f"step '{name}' must be a dict")
            continue
        if "operator" not in step or not step["operator"]:
            errors.append(f"step '{name}': missing or empty 'operator'")
        if _is_identity(step):
            if "prompt" in step:
                errors.append(f"step '{name}': identity step must NOT have 'prompt'")
        else:
            if "prompt" not in step or not step.get("prompt"):
                errors.append(f"step '{name}': non-identity step requires 'prompt'")

    return errors


# ── GC ────────────────────────────────────────────────────────────────────


def _gc_stale_sessions() -> None:
    """Remove recipe_runner sessions stale for >24h that are still 'running'."""
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
        if meta.get("runner") != "recipe_runner":
            continue
        if meta.get("status") != "running":
            continue
        updated = meta.get("updated_at", "")
        try:
            updated_dt = datetime.fromisoformat(updated)
        except (ValueError, TypeError):
            continue
        age_hours = (now - updated_dt).total_seconds() / 3600
        if age_hours > _GC_WINDOW_HOURS:
            shutil.rmtree(d, ignore_errors=True)


# ── Session creation ──────────────────────────────────────────────────────


def _init_meta(session_id: str, recipe: dict[str, Any], budget: int, runner_cmd: str) -> dict[str, Any]:
    steps_meta: dict[str, Any] = {}
    for item in recipe["flow"]:
        names = item if isinstance(item, list) else [item]
        for name in names:
            steps_meta[name] = {"status": "pending"}

    return {
        "meta_version": 1,
        "session_id": session_id,
        "recipe_name": recipe["name"],
        "runner": "recipe_runner",
        "runner_cmd": runner_cmd,
        "status": "running",
        "current_step": None,
        "budget_used": 0,
        "budget_ceiling": budget,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "steps": steps_meta,
    }


# ── Emission ──────────────────────────────────────────────────────────────


def _count_llm_steps(recipe: dict[str, Any]) -> int:
    """Count steps that require LLM interaction (non-identity)."""
    count = 0
    for item in recipe["flow"]:
        names = item if isinstance(item, list) else [item]
        for name in names:
            if not _is_identity(recipe["steps"][name]):
                count += 1
    return count


def _emit_step(
    name: str,
    step: dict[str, Any],
    input_data: Any,
    session_id: str,
    session_dir: Path,
    step_number: int,
    total_llm_steps: int,
    runner_cmd: str,
) -> None:
    """Print step prompt and submit instructions."""
    print(f"\n{'='*60}")
    print(f"STEP {step_number}/{total_llm_steps} — {name}")
    print(f"Operator: {step['operator']}")
    print(f"{'='*60}")

    print(f"\nInput:")
    print(f"  {json.dumps(input_data, indent=2).replace(chr(10), chr(10) + '  ')}")

    print(f"\nPrompt:")
    print(f"  {step['prompt']}")

    pending_path = session_dir / "pending" / f"{name}.json"
    print(f"\nWrite your JSON output to:")
    print(f"  {pending_path}")
    print(f"\nThen run:")
    print(f"  {runner_cmd} submit --session {session_id} --step {name}")
    print()


# ── Identity ──────────────────────────────────────────────────────────────


def _auto_complete_identity(name: str, input_data: Any, session_dir: Path, meta: dict[str, Any]) -> None:
    state_path = session_dir / "state" / f"{name}.json"
    state_path.write_text(json.dumps(input_data, indent=2))
    meta["steps"][name] = {"status": "completed", "completed_at": _now_iso(), "identity": True}


# ── Parallel helpers ──────────────────────────────────────────────────────


def _combined_output(group: list[str], session_dir: Path) -> dict[str, Any]:
    """Build fan-in output from all group members' state files."""
    combined: dict[str, Any] = {}
    for name in group:
        state_path = session_dir / "state" / f"{name}.json"
        combined[name] = json.loads(state_path.read_text())
    return combined


# ── Advancement ───────────────────────────────────────────────────────────


def _llm_step_number_at(recipe: dict[str, Any], flow_index: int, step_name: str) -> int:
    """Compute the LLM-facing step number for a step (1-based)."""
    count = 0
    for i, item in enumerate(recipe["flow"]):
        names = item if isinstance(item, list) else [item]
        for name in names:
            if not _is_identity(recipe["steps"][name]):
                count += 1
                if i == flow_index and name == step_name:
                    return count
                if i > flow_index:
                    return count
    return count


def _advance(session_dir: Path, meta: dict[str, Any], recipe: dict[str, Any], flow_index: int, last_output: Any) -> None:
    """Advance from flow_index forward. Iterative."""
    pos = flow_index + 1
    total_llm = _count_llm_steps(recipe)
    runner_cmd = meta.get("runner_cmd", _DEFAULT_RUNNER_CMD)
    session_id = meta["session_id"]

    while pos < len(recipe["flow"]):
        item = recipe["flow"][pos]

        if isinstance(item, str):
            step = recipe["steps"][item]
            if _is_identity(step):
                _auto_complete_identity(item, last_output, session_dir, meta)
                pos += 1
                continue
            else:
                # Budget check (after final-step priority)
                is_final = (pos == len(recipe["flow"]) - 1)
                if not is_final and meta["budget_used"] >= meta["budget_ceiling"]:
                    meta["status"] = "budget_exhausted"
                    _write_meta(session_dir, meta)
                    print("\nBudget exhausted — no further steps will be emitted.", file=sys.stderr)
                    return

                step_num = _llm_step_number_at(recipe, pos, item)
                _emit_step(item, step, last_output, session_id, session_dir, step_num, total_llm, runner_cmd)
                meta["current_step"] = item
                _write_meta(session_dir, meta)
                return

        elif isinstance(item, list):
            identity_members = [s for s in item if _is_identity(recipe["steps"][s])]
            non_identity = [s for s in item if not _is_identity(recipe["steps"][s])]

            for name in identity_members:
                _auto_complete_identity(name, last_output, session_dir, meta)

            if non_identity:
                # Budget preflight
                is_final = (pos == len(recipe["flow"]) - 1)
                required = len(non_identity)
                if not is_final and meta["budget_used"] + required > meta["budget_ceiling"]:
                    meta["status"] = "budget_exhausted"
                    _write_meta(session_dir, meta)
                    print("\nBudget exhausted — insufficient budget for parallel group.", file=sys.stderr)
                    return

                meta["current_step"] = None
                meta["parallel_group"] = item
                meta["parallel_pending"] = list(non_identity)
                _write_meta(session_dir, meta)

                for name in non_identity:
                    step = recipe["steps"][name]
                    step_num = _llm_step_number_at(recipe, pos, name)
                    _emit_step(name, step, last_output, session_id, session_dir, step_num, total_llm, runner_cmd)
                return
            else:
                # All identity — compute combined, continue
                last_output = _combined_output(item, session_dir)
                pos += 1
                continue

    # Flow exhausted
    meta["status"] = "completed"
    meta["current_step"] = None
    _write_meta(session_dir, meta)
    print(f"\n{'='*60}")
    print("WORKFLOW COMPLETE")
    print(f"{'='*60}")
    print(f"\nSession: {session_id}")
    print(f"Steps completed: {meta['budget_used']}")
    print(f"\nFinal output:")
    print(f"  {json.dumps(last_output, indent=2).replace(chr(10), chr(10) + '  ')}")


# ── Commands ──────────────────────────────────────────────────────────────


def cmd_start(args: argparse.Namespace) -> None:
    _gc_stale_sessions()

    recipe_path = Path(args.recipe)
    if not recipe_path.exists():
        _die(f"recipe not found: {recipe_path}")

    recipe = _load_recipe(recipe_path)
    errors = _validate_recipe(recipe)
    if errors:
        print("Recipe validation failed:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    raw_input = _parse_input(args.input)
    budget = args.budget
    runner_cmd = args.runner_cmd or _DEFAULT_RUNNER_CMD

    # Create session
    session_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    session_dir = _session_dir(session_id)
    session_dir.mkdir(parents=True, mode=0o700)
    (session_dir / "pending").mkdir(mode=0o700)
    (session_dir / "state").mkdir(mode=0o700)

    # Persist recipe and input
    (session_dir / "recipe.json").write_text(json.dumps(recipe, indent=2))
    (session_dir / "input.json").write_text(json.dumps(raw_input, indent=2))

    meta = _init_meta(session_id, recipe, budget, runner_cmd)
    _write_meta(session_dir, meta)

    print(f"Session: {session_id}")
    print(f"Recipe:  {recipe['name']}")
    flow_names = []
    for item in recipe["flow"]:
        if isinstance(item, list):
            flow_names.append(f"[{' | '.join(item)}]")
        else:
            flow_names.append(item)
    print(f"Steps:   {' → '.join(flow_names)}")
    print(f"Budget:  0/{budget}")

    # Advance from position -1 (before first)
    _advance(session_dir, meta, recipe, -1, raw_input)


def cmd_submit(args: argparse.Namespace) -> None:
    session_dir = _session_dir(args.session)
    if not session_dir.exists():
        _die(f"session not found: {args.session}")

    meta = _read_meta(session_dir)
    step_name = args.step

    if meta["status"] != "running":
        _die(f"session status is '{meta['status']}', not 'running'")

    recipe = json.loads((session_dir / "recipe.json").read_text())

    # Parallel or sequential submission
    parallel_pending = meta.get("parallel_pending")
    if parallel_pending is not None:
        if step_name not in parallel_pending:
            _die(f"step '{step_name}' is not in parallel_pending: {parallel_pending}")
    else:
        if meta["current_step"] != step_name:
            _die(f"current step is '{meta['current_step']}', not '{step_name}'")

    # Read and parse pending output
    pending_path = session_dir / "pending" / f"{step_name}.json"
    if not pending_path.exists():
        _die(f"no pending output at {pending_path} — write your JSON output there, then re-run")

    try:
        output = json.loads(pending_path.read_text())
    except json.JSONDecodeError as exc:
        _die(f"invalid JSON in {pending_path}: {exc}")

    # Persist to state
    state_path = session_dir / "state" / f"{step_name}.json"
    state_path.write_text(json.dumps(output, indent=2))
    pending_path.unlink()

    # Update meta
    meta["steps"][step_name] = {"status": "completed", "completed_at": _now_iso()}
    meta["budget_used"] += 1

    print(f"\n✓ Step '{step_name}' persisted.")
    print(f"  Budget: {meta['budget_used']}/{meta['budget_ceiling']}")

    # Parallel group handling
    if parallel_pending is not None:
        parallel_pending.remove(step_name)
        meta["parallel_pending"] = parallel_pending

        if parallel_pending:
            _write_meta(session_dir, meta)
            done = len(meta["parallel_group"]) - len(parallel_pending)
            total = len(meta["parallel_group"])
            print(f"\n  {done}/{total} parallel steps complete. Remaining: {parallel_pending}")
            return

        # Group complete — compute combined output and advance
        group = meta["parallel_group"]
        del meta["parallel_group"]
        del meta["parallel_pending"]
        combined = _combined_output(group, session_dir)
        _write_meta(session_dir, meta)

        # Find flow index of this parallel group
        flow_index = _find_flow_index_for_group(recipe, group)
        _advance(session_dir, meta, recipe, flow_index, combined)
    else:
        _write_meta(session_dir, meta)
        # Find flow index of this step
        flow_index = _find_flow_index_for_step(recipe, step_name)
        last_output = output
        _advance(session_dir, meta, recipe, flow_index, last_output)


def _find_flow_index_for_step(recipe: dict[str, Any], step_name: str) -> int:
    for i, item in enumerate(recipe["flow"]):
        if item == step_name:
            return i
    return -1


def _find_flow_index_for_group(recipe: dict[str, Any], group: list[str]) -> int:
    for i, item in enumerate(recipe["flow"]):
        if isinstance(item, list) and set(item) == set(group):
            return i
    return -1


def cmd_status(args: argparse.Namespace) -> None:
    session_dir = _session_dir(args.session)
    if not session_dir.exists():
        _die(f"session not found: {args.session}")

    meta = _read_meta(session_dir)

    print(f"Session:  {meta['session_id']}")
    print(f"Recipe:   {meta['recipe_name']}")
    print(f"Status:   {meta['status']}")
    print(f"Step:     {meta.get('current_step') or '(done)'}")
    print(f"Budget:   {meta['budget_used']}/{meta['budget_ceiling']}")
    print(f"Created:  {meta['created_at']}")
    print(f"Updated:  {meta['updated_at']}")

    if meta.get("parallel_pending"):
        print(f"Parallel: waiting on {meta['parallel_pending']}")

    print()
    for step_name, step_info in meta["steps"].items():
        if step_info.get("identity"):
            marker = "≡"
        elif step_info["status"] == "completed":
            marker = "✓"
        elif step_name == meta.get("current_step"):
            marker = "→"
        else:
            marker = "○"
        print(f"  {marker} {step_name}: {step_info['status']}")


def cmd_list(_args: argparse.Namespace) -> None:
    if not STATE_ROOT.exists():
        print("No sessions.")
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
        if meta.get("runner") != "recipe_runner":
            continue
        sessions.append((d.name, meta))

    if not sessions:
        print("No sessions.")
        return

    for sid, meta in sessions:
        status = meta.get("status", "?")
        recipe = meta.get("recipe_name", "?")
        budget = f"{meta.get('budget_used', '?')}/{meta.get('budget_ceiling', '?')}"
        print(f"  {sid}  {status:<16}  {recipe:<20}  budget: {budget}")


# ── Entry point ───────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(prog="recipe_runner", description="Lite recipe runner")
    sub = parser.add_subparsers(dest="command")

    p_start = sub.add_parser("start", help="Start a new session")
    p_start.add_argument("--recipe", "-r", required=True, help="Path to recipe .py file")
    p_start.add_argument("--input", "-i", default=None, help="JSON string or @file")
    p_start.add_argument("--budget", "-b", type=int, default=10, help="Max LLM steps (default: 10)")
    p_start.add_argument("--runner-cmd", default=None, help="Override runner command in emissions")

    p_submit = sub.add_parser("submit", help="Submit step output")
    p_submit.add_argument("--session", "-s", required=True, help="Session ID")
    p_submit.add_argument("--step", required=True, help="Step name")

    p_status = sub.add_parser("status", help="Show session state")
    p_status.add_argument("--session", "-s", required=True, help="Session ID")

    sub.add_parser("list", help="List recipe_runner sessions")

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    dispatch = {"start": cmd_start, "submit": cmd_submit, "status": cmd_status, "list": cmd_list}
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
