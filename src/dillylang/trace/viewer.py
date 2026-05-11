"""CLI trace viewer: renders pipeline execution as a rich terminal tree.

The trace viewer is the primary debugging tool for dillylang pipelines.
It renders TraceEntry lists as nested trees showing operator composition,
with color-coded status and optional verbose mode for prompt inspection.

Tree structure logic:
  - combinator_start pushes a new branch onto a stack
  - llm_call/selector entries attach as leaves to the current branch
  - combinator_end pops the stack and closes the branch
  - Flat traces (no combinator wrapping) attach directly to root
"""

from __future__ import annotations

from io import StringIO
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from dillylang.vocab.types import (
    ArtifactStatus,
    Budget,
    ItemError,
    RunResult,
    RunResultStatus,
    TraceEntry,
    TraceEventType,
)

# Status -> color mapping for consistent visual encoding
_STATUS_COLORS: dict[ArtifactStatus, str] = {
    ArtifactStatus.SUCCESS: "green",
    ArtifactStatus.REPAIR_SUCCEEDED: "yellow",
    ArtifactStatus.FAILED: "red",
    ArtifactStatus.PARTIAL: "yellow",
}


def _status_color(status: ArtifactStatus) -> str:
    return _STATUS_COLORS.get(status, "white")


def _truncate(text: str, max_len: int = 200) -> str:
    """Truncate text with ellipsis if over max_len."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def format_trace_summary(entry: TraceEntry) -> str:
    """One-line summary of a trace entry for compact display.

    LLM calls: "{operator_name} [{status}] tokens={tokens_used} latency={latency_ms}ms"
    Combinator events: "{operator_name} [{event_type}]"
    Selector events: "{operator_name} [selector] field={field} selected={selected_count}"
    """
    if entry.event_type == TraceEventType.LLM_CALL:
        tokens = entry.tokens_used or 0
        latency = entry.latency_ms or 0
        return (
            f"{entry.operator_name} [{entry.status.value}] "
            f"tokens={tokens} latency={latency}ms"
        )
    if entry.event_type == TraceEventType.SELECTOR:
        return (
            f"{entry.operator_name} [selector] "
            f"field={entry.field} selected={entry.selected_count}"
        )
    # combinator_start or combinator_end
    return f"{entry.operator_name} [{entry.event_type.value}]"


def _build_llm_node_label(entry: TraceEntry) -> Text:
    """Build a rich Text label for an LLM call node."""
    color = _status_color(entry.status)
    label = Text()
    label.append(entry.operator_name, style=f"bold {color}")
    label.append(f" [{entry.status.value}]", style=color)

    # Parsed output summary
    if entry.parsed_output is not None:
        output_str = str(entry.parsed_output)
        label.append(f"  {_truncate(output_str)}", style="dim")

    # Budget stats
    tokens = entry.tokens_used or 0
    latency = entry.latency_ms or 0
    label.append(f"  [tokens={tokens} latency={latency}ms]", style="dim cyan")

    return label


def _build_selector_label(entry: TraceEntry) -> Text:
    """Build a rich Text label for a selector event."""
    label = Text()
    label.append(f"select({entry.field})", style="dim")
    label.append(f" => {entry.selected_count} items", style="dim")
    return label


def render_trace(
    trace: list[TraceEntry],
    verbose: bool = False,
    console: Console | None = None,
) -> None:
    """Render a pipeline trace as a rich terminal tree.

    Args:
        trace: List of TraceEntry from a RunResult.
        verbose: If True, show rendered prompts and raw LLM responses.
        console: Rich Console to print to (default: new Console to stdout).
    """
    console = console or Console()

    if verbose:
        console.print(
            "[bold yellow]Warning:[/] Verbose traces may contain sensitive data",
            style="yellow",
        )

    root = Tree("[bold]Pipeline Trace[/]")
    # Stack tracks current tree node for nesting.
    # combinator_start pushes, combinator_end pops.
    stack: list[Tree] = [root]

    for entry in trace:
        current = stack[-1]

        if entry.event_type == TraceEventType.COMBINATOR_START:
            # New branch for combinator scope
            branch_label = Text()
            branch_label.append(entry.operator_name, style="bold cyan")
            children_info = ""
            if entry.children:
                children_info = f" ({len(entry.children)} branches)"
            branch_label.append(children_info, style="dim")
            branch = current.add(branch_label)
            stack.append(branch)

        elif entry.event_type == TraceEventType.COMBINATOR_END:
            # Close combinator scope: annotate with aggregate status
            color = _status_color(entry.status)
            end_label = Text()
            end_label.append(f"end {entry.operator_name}", style=f"dim {color}")
            end_label.append(f" [{entry.status.value}]", style=f"dim {color}")
            current.add(end_label)
            # Pop back to parent (but never pop root)
            if len(stack) > 1:
                stack.pop()

        elif entry.event_type == TraceEventType.LLM_CALL:
            node_label = _build_llm_node_label(entry)
            leaf = current.add(node_label)

            if verbose:
                # Full rendered prompt
                if entry.rendered_prompt:
                    leaf.add(
                        Panel(
                            entry.rendered_prompt,
                            title="Rendered Prompt",
                            border_style="blue",
                        )
                    )
                # Raw LLM response
                if entry.raw_response:
                    leaf.add(
                        Panel(
                            entry.raw_response,
                            title="Raw Response",
                            border_style="green",
                        )
                    )

        elif entry.event_type == TraceEventType.SELECTOR:
            current.add(_build_selector_label(entry))

    console.print(root)


def render_run_result(
    result: RunResult,
    verbose: bool = False,
    console: Console | None = None,
) -> None:
    """Render a complete RunResult: status header, errors, trace, budget.

    Args:
        result: The pipeline RunResult to display.
        verbose: If True, show full prompts and raw responses.
        console: Rich Console to print to (default: new Console to stdout).
    """
    console = console or Console()

    # Status header
    status_colors: dict[RunResultStatus, str] = {
        RunResultStatus.SUCCESS: "green",
        RunResultStatus.PARTIAL: "yellow",
        RunResultStatus.FAILED: "red",
        RunResultStatus.BUDGET_EXHAUSTED: "red",
    }
    color = status_colors.get(result.status, "white")
    console.print(f"\n[bold]Pipeline result:[/] [{color}]{result.status.value}[/{color}]")

    # Error summary table
    if result.errors:
        table = Table(title="Errors", show_lines=True)
        table.add_column("Item", style="red")
        table.add_column("Kind")
        table.add_column("Message")
        for err in result.errors:
            table.add_row(err.item_id, err.error_kind, err.message)
        console.print(table)

    # Trace tree
    if result.trace:
        render_trace(result.trace, verbose=verbose, console=console)

    # Budget summary (only if budget was populated by runner)
    if result.budget is not None:
        b = result.budget
        console.print(
            f"\n[bold]Budget:[/] "
            f"{b.llm_calls_used}/{b.max_llm_calls} LLM calls, "
            f"{b.tokens_used}/{b.max_tokens} tokens"
        )
