"""Click CLI entry point: trace inspection and pipeline execution.

Commands:
  dillylang trace --file result.json [--verbose]  — inspect a saved RunResult
  dillylang run --recipe refine --problem "..."    — execute a pipeline live
  dillylang design --goal "..."                    — design a new recipe
  dillylang improve --translate-json ... --analyze-json ...  — improve a skill
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import click
from pydantic import ValidationError

from dillylang.trace.viewer import render_run_result
from dillylang.vocab.types import Budget, RunResult


def _configure_lm() -> None:
    """Bootstrap DSPy LM from DILLYLANG_LM* environment variables.

    Required: DILLYLANG_LM (model identifier, e.g. "ollama/gemma2:9b").
    Optional: DILLYLANG_LM_BASE (API base URL), DILLYLANG_LM_API_KEY (default "ollama"),
              DILLYLANG_LM_MAX_TOKENS (default 16384).
    """
    import dspy

    lm_model = os.environ.get("DILLYLANG_LM")
    if not lm_model:
        click.echo("Error: DILLYLANG_LM not set (e.g. 'openai/granite4.1:8B')", err=True)
        sys.exit(1)
    lm_kwargs: dict[str, Any] = {}
    lm_base = os.environ.get("DILLYLANG_LM_BASE")
    if lm_base:
        lm_kwargs["api_base"] = lm_base
    lm_key = os.environ.get("DILLYLANG_LM_API_KEY", "ollama")
    lm_kwargs["api_key"] = lm_key
    if max_tokens := os.environ.get("DILLYLANG_LM_MAX_TOKENS", "16384"):
        lm_kwargs["max_tokens"] = int(max_tokens)
    dspy.configure(lm=dspy.LM(lm_model, **lm_kwargs))


@click.group()
def cli() -> None:
    """Dillylang: composable thinking-move pipelines."""


@cli.command()
@click.option(
    "--file", "-f",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to a JSON file containing a serialized RunResult.",
)
@click.option("--verbose", "-v", is_flag=True, help="Show full prompts and raw responses.")
def trace(file: Path, verbose: bool) -> None:
    """Inspect a saved pipeline trace from a JSON file.

    The JSON file should contain the output of RunResult.model_dump().
    Pydantic validates the file on load; malformed JSON raises a clear error.
    """
    try:
        data = json.loads(file.read_text())
    except json.JSONDecodeError as exc:
        click.echo(f"Error: invalid JSON in {file}: {exc}", err=True)
        sys.exit(1)

    try:
        result = RunResult.model_validate(data)
    except ValidationError as exc:
        click.echo(f"Error: JSON does not match RunResult schema:\n{exc}", err=True)
        sys.exit(1)

    render_run_result(result, verbose=verbose)


@cli.command()
@click.option("--recipe", "-r", required=True, help="Recipe name (e.g. 'refine').")
@click.option("--problem", "-p", required=True, help="Problem statement text.")
@click.option("--budget", "-b", default=7, type=int, help="Max LLM calls (default: 7).")
@click.option("--timeout", "-t", default=120, type=int, help="Wall-time budget in seconds (default: 120).")
@click.option("--save", "-s", type=click.Path(path_type=Path), help="Save RunResult JSON to file.")
@click.option("--verbose", "-v", is_flag=True, help="Show full prompts and raw responses.")
def run(recipe: str, problem: str, budget: int, timeout: int, save: Path | None, verbose: bool) -> None:
    """Execute a named pipeline recipe against a problem.

    Currently supports: 'refine' (pipe(decompose, parallel(invert, rotate), synthesize)).
    """
    from dillylang.combinators import parallel, pipe
    from dillylang.operators import (
        DecomposeOperator,
        InvertOperator,
        RotateOperator,
        SynthesizeOperator,
    )
    from dillylang.runner.runner import PipelineRunner

    _configure_lm()

    recipes = {
        "refine": lambda: pipe(
            DecomposeOperator(),
            parallel(InvertOperator(), RotateOperator()),
            SynthesizeOperator(),
        ),
    }

    if recipe not in recipes:
        click.echo(f"Error: unknown recipe '{recipe}'. Available: {', '.join(recipes)}", err=True)
        sys.exit(1)

    pipeline = recipes[recipe]()
    runner = PipelineRunner(budget=Budget(max_llm_calls=budget, max_wall_time_ms=timeout * 1000))
    result = runner.run(pipeline, problem)

    render_run_result(result, verbose=verbose)

    if save:
        save.write_text(result.model_dump_json(indent=2))
        click.echo(f"\nSaved RunResult to {save}")


@cli.command("design")
@click.option("--goal", "-g", required=True, help="Goal specification text for the recipe to design.")
@click.option("--budget", "-b", default=7, type=int, help="Max LLM calls (default: 7).")
@click.option("--save", "-s", type=click.Path(path_type=Path), help="Save RunResult JSON to file.")
@click.option("--verbose", "-v", is_flag=True, help="Show full prompts and raw responses.")
def design_cmd(goal: str, budget: int, save: Path | None, verbose: bool) -> None:
    """Design a new Dillylang recipe from a goal specification."""
    from dillylang.skills.design import design as design_skill

    _configure_lm()
    result = design_skill(goal, budget=Budget(max_llm_calls=budget))

    # Display RecipeDefinition summary
    d = result.definition
    click.echo(f"\n--- Recipe: {d.recipe_name} ---")
    click.echo(f"Purpose: {d.recipe_purpose}")
    click.echo(f"Shape: {d.recipe_shape}")
    click.echo(f"Pipeline: {d.pipeline_definition}")
    click.echo(f"Cost: {d.metrics_cost}, Depth: {d.metrics_depth}")
    click.echo(f"Coverage: {d.metrics_coverage}, Efficiency: {d.metrics_efficiency:.2f}")
    click.echo(f"Axes: {d.metrics_axes}")
    click.echo(f"Confidence: {d.confidence}")
    if d.existing_recipe_fit_verdict != "fail":
        click.echo(
            f"Existing recipe: {d.existing_recipe_fit_closest} "
            f"({d.existing_recipe_fit_verdict})"
        )

    if verbose:
        render_run_result(result.run_result, verbose=True)

    if save:
        save.write_text(result.run_result.model_dump_json(indent=2))
        click.echo(f"\nRunResult saved to {save}")


@cli.command("improve")
@click.option(
    "--translate-json", "-t", required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to translate RunResult JSON (contains artifacts for DillylangSkillDescription).",
)
@click.option(
    "--analyze-json", "-a", required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to analyze RunResult JSON (contains artifacts for AnalysisReport).",
)
@click.option(
    "--skill-name", "-n", default=None, type=str,
    help="Skill name for rendering. Defaults to translate JSON filename stem.",
)
@click.option("--budget", "-b", default=5, type=int, help="Max LLM calls (default: 5).")
@click.option("--save", "-s", type=click.Path(path_type=Path), help="Save RunResult JSON to file.")
@click.option("--verbose", "-v", is_flag=True, help="Show full prompts and raw responses.")
def improve_cmd(
    translate_json: Path,
    analyze_json: Path,
    skill_name: str | None,
    budget: int,
    save: Path | None,
    verbose: bool,
) -> None:
    """Improve a skill based on translate + analyze output.

    Loads saved RunResult JSONs from translate and analyze, reconstructs
    DillylangSkillDescription and AnalysisReport via their deterministic
    renderers, then runs the improve pipeline.
    """
    from dillylang.skills.analyze import render_analysis_report
    from dillylang.skills.improve import improve as improve_skill
    from dillylang.skills.metrics import compute_metrics
    from dillylang.skills.translate import render_dillylang_skill_description

    _configure_lm()

    # Reconstruct DillylangSkillDescription from translate RunResult
    translate_result = RunResult.model_validate_json(translate_json.read_text())
    name = skill_name or translate_json.stem
    description = render_dillylang_skill_description(translate_result, name)

    # Reconstruct AnalysisReport from analyze RunResult
    analyze_result = RunResult.model_validate_json(analyze_json.read_text())
    metrics = compute_metrics(description)
    report = render_analysis_report(analyze_result, name, metrics)

    result = improve_skill(description, report, budget=Budget(max_llm_calls=budget))

    click.echo(f"\n--- Improved: {result.output.revised_description.skill_name} ---")
    click.echo(f"Changes: {len(result.output.change_log)}")
    for entry in result.output.change_log:
        click.echo(f"  - {entry.field_changed}: {entry.rationale}")

    if verbose:
        render_run_result(result.run_result, verbose=True)

    if save:
        save.write_text(result.run_result.model_dump_json(indent=2))
        click.echo(f"\nRunResult saved to {save}")
