"""Branch combinator: conditional dispatch based on classify labels.

branch(taxonomy_name, routes, default) creates a combinator that reads
a classify label from the upstream Artifact.data and dispatches to the
matching sub-pipeline. Same coupling pattern as filter reading evaluate's
verdict (D-06).

M2 note: Branch passes its INPUT (the classify artifact) to the selected
route. In pipe(classify, branch(...)), the input to branch IS the classify
output artifact. The classify artifact's .data contains classifications
metadata + the original problem_text (which the LLM received). Routes
receive the full upstream state -- they do NOT receive the pre-classify
original artifact. If a recipe needs the original, use a different
composition pattern (e.g. parallel(classify, identity) followed by
branch reading from the classify result).
"""

from __future__ import annotations

from typing import Any

from dillylang.combinators._routing import execute_node
from dillylang.trace.emit import emit_combinator_end, emit_combinator_start
from dillylang.vocab.types import (
    Artifact,
    ArtifactStatus,
    Context,
    RunResult,
    RunResultStatus,
    TraceEntry,
)


def _extract_label(output: Any, taxonomy_name: str) -> str | None:
    """Extract classify label for a taxonomy from Artifact.data.

    Navigates the ClassifyOutput structure: data["classifications"] is a list
    of dicts with "taxonomy" and "label" keys. Returns the label for the
    specified taxonomy, or None if not found.
    """
    if isinstance(output, Artifact) and isinstance(output.data, dict):
        classifications = output.data.get("classifications", [])
        for cls in classifications:
            if isinstance(cls, dict) and cls.get("taxonomy") == taxonomy_name:
                return cls.get("label")
    return None


class BranchOperator:
    """Conditional dispatch based on classify label.

    Routes an artifact to a sub-pipeline based on its classification
    for the specified taxonomy. Requires a default pipeline (D-05).

    M2: Branch passes its input (the classify artifact) directly to the
    selected route. Classify is a judge (produces meta-information), and
    the classify output artifact contains the classifications metadata.
    Routes receive this full upstream artifact -- they do NOT receive the
    pre-classify original artifact. The classify artifact IS the branch's
    input, and that's what gets routed.
    """

    is_combinator = True

    def __init__(
        self,
        taxonomy_name: str,
        routes: dict[str, Any],  # label -> pipeline node (operator or combinator)
        default: Any,  # default pipeline node (required per D-05)
    ) -> None:
        if not taxonomy_name:
            raise ValueError("taxonomy_name must be non-empty")
        if not isinstance(routes, dict):
            raise TypeError(f"routes must be a dict, got {type(routes).__name__}")
        self._taxonomy_name = taxonomy_name
        self._routes = routes
        self._default = default

    @property
    def name(self) -> str:
        return "branch"

    def run(self, input: Any, ctx: Context) -> RunResult:
        step_index = len(ctx.trace)
        start_entry = emit_combinator_start("branch", step_index)
        all_trace: list[TraceEntry] = [start_entry]

        # Validate input type -- branch expects an Artifact (typically from classify).
        # Silently routing non-Artifact input to the default would mask composition errors.
        if not isinstance(input, Artifact):
            raise TypeError(
                f"branch expects an Artifact (typically from classify), "
                f"got {type(input).__name__}"
            )

        # Extract label from upstream classify output (D-06)
        label = _extract_label(input, self._taxonomy_name)

        # Select pipeline: match label to route, or use default
        if label is not None and label in self._routes:
            selected = self._routes[label]
        else:
            selected = self._default

        # Execute the selected sub-pipeline via execute_node.
        # M2: input (the classify artifact) is passed directly to the route.
        result = execute_node(selected, input, ctx)
        all_trace.extend(result.trace)

        end_status = (
            ArtifactStatus.SUCCESS if result.status == RunResultStatus.SUCCESS
            else ArtifactStatus.FAILED if result.status == RunResultStatus.FAILED
            else ArtifactStatus.PARTIAL
        )
        end_entry = emit_combinator_end("branch", step_index, end_status)
        all_trace.append(end_entry)

        return RunResult(
            output=result.output,
            trace=all_trace,
            status=result.status,
            errors=result.errors,
            call_metadata=result.call_metadata,
        )


def branch(
    taxonomy_name: str,
    routes: dict[str, Any],
    default: Any,
) -> BranchOperator:
    """Create a conditional dispatch combinator.

    Routes artifacts to sub-pipelines based on a classify label.
    The default pipeline is required (D-05) -- it fires when the
    label doesn't match any route or when classifications are missing.

    M2: The route receives the classify artifact (branch's input),
    not the pre-classify original. Classify is a judge; its output
    contains classification metadata. See BranchOperator docstring.
    """
    return BranchOperator(taxonomy_name, routes, default)
