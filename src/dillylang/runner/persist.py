"""Pipeline run persistence -- serialize and write RunResult to disk.

Substrate-level feature: any pipeline run can be persisted with full
per-step I/O (inputs, rendered prompts, raw responses, parsed outputs,
latency, budget state). Timestamped directories prevent clobbering.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dillylang.vocab.types import RunResult


def serialize_run(
    result: RunResult,
    *,
    name: str = "",
    inputs: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Serialize a RunResult into a JSON-friendly dict.

    The trace entries carry per-step I/O: input, rendered_prompt,
    raw_response, parsed_output, latency_ms, tokens_used. The artifacts
    dict carries all intermediate outputs keyed by operator ID.
    """
    record: dict[str, Any] = {
        "name": name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if metadata:
        record["metadata"] = metadata

    if inputs:
        record["inputs"] = inputs

    record["status"] = result.status.value

    if result.budget:
        record["budget"] = result.budget.model_dump()

    # Per-step trace with full I/O
    record["trace"] = [
        entry.model_dump(mode="json") for entry in result.trace
    ]

    # All intermediate artifacts
    if result.artifacts:
        record["artifacts"] = {
            k: v.model_dump(mode="json") for k, v in result.artifacts.items()
        }

    # Final output
    if isinstance(result.output, list):
        record["output"] = [a.model_dump(mode="json") for a in result.output]
    else:
        record["output"] = result.output.model_dump(mode="json")

    if result.errors:
        record["errors"] = [e.model_dump(mode="json") for e in result.errors]

    return record


def persist_run(
    result: RunResult,
    *,
    base_dir: str | Path,
    name: str,
    inputs: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Write a pipeline run to a timestamped directory.

    Creates base_dir/YYYYMMDDTHHMMSS-{name}/ with:
      - run.json: full serialized RunResult (trace, artifacts, budget)
      - inputs.json: caller-provided input data (if given)
      - metadata.json: caller-provided metadata (if given)

    Returns the created directory path.
    """
    base = Path(base_dir)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    run_dir = base / f"{timestamp}-{name}"
    run_dir.mkdir(parents=True, exist_ok=True)

    record = serialize_run(
        result, name=name, inputs=inputs, metadata=metadata
    )

    (run_dir / "run.json").write_text(
        json.dumps(record, indent=2, default=str)
    )

    return run_dir
