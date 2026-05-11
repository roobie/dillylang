"""ClassifyOperator: assign structured labels from provided taxonomies.

Wraps BaseDSPyOperator with the classify-specific prompt and schema.
The key constraint: taxonomies is REQUIRED -- classify without a
taxonomy is invalid. This is enforced by Pydantic validation on
ClassifyInput (no default for taxonomies).

ADR-005: closed-set labels, single-label per taxonomy, rationale required.
Runtime post-validation (B2) checks that LLM output conforms.

Spec reference: INDEX.md section 6 (classify schema), ADR-005.
Steering parameter: taxonomies (required, via ADR-007).
"""

from __future__ import annotations

from typing import Any

from dillylang.operators.base import BaseDSPyOperator
from dillylang.vocab.schemas import ClassifyInput, ClassifyOutput
from dillylang.vocab.types import (
    Artifact,
    ArtifactStatus,
    Context,
    ItemError,
    RunResult,
    RunResultStatus,
)

# ADR-005 docstring. Instructs the LLM for closed-set classification.
_CLASSIFY_DOCSTRING = (
    "Assign structured labels from provided taxonomies. For each taxonomy, "
    "assign exactly one label from its label list. Use only labels from the "
    "provided set -- this is closed-set classification. Do not invent new "
    "labels. If no label fits well, assign the best available label from "
    "the taxonomy (the taxonomy designer should include an escape label like "
    "'other' or 'unknown' for ambiguous cases). Provide independent rationale "
    "for each classification explaining why this label was chosen over "
    "alternatives. Rate confidence for each classification."
)


class ClassifyOperator(BaseDSPyOperator):
    """Judge operator: classify an artifact using provided taxonomies.

    Produces one Classification per taxonomy, each with label, rationale,
    and confidence. The taxonomies steering parameter is required -- it has
    no default and must be provided via bind or direct input.

    ADR-005 constraints enforced at runtime (B2):
      - Closed-set labels: each label must be in its taxonomy's label list
      - Uniqueness: at most one classification per taxonomy
    """

    def __init__(self) -> None:
        super().__init__(
            name="classify",
            docstring=_CLASSIFY_DOCSTRING,
            input_model=ClassifyInput,  # D-08: taxonomies is required steering param
            output_model=ClassifyOutput,
        )

    def run(self, input: Any, ctx: Context) -> RunResult:
        """Execute classify with ADR-005 post-validation (B2).

        Calls the base run() for LLM prediction, then validates that
        the output conforms to closed-set and uniqueness constraints.
        Violations produce PARTIAL status with details in call_metadata.
        """
        result = super().run(input, ctx)

        # Post-validate classify-specific constraints (B2 / ADR-005)
        if result.status == RunResultStatus.SUCCESS and isinstance(result.output, Artifact):
            taxonomies = self._get_bound_taxonomies(input)
            if taxonomies:
                violations = self._validate_classifications(result.output.data, taxonomies)
                if violations:
                    # Structurally valid (passed Pydantic) but semantically wrong.
                    # Demote to PARTIAL with violation details in call_metadata.
                    meta = result.call_metadata or {}
                    meta["classify_validation_violations"] = violations
                    result = RunResult(
                        output=result.output,
                        trace=result.trace,
                        status=RunResultStatus.PARTIAL,
                        call_metadata=meta,
                        errors=[ItemError(
                            item_id=f"{self._name}_validation",
                            error_kind="classify_validation",
                            message="; ".join(violations),
                        )],
                    )
        return result

    def _get_bound_taxonomies(self, input: Any) -> dict[str, list[str]] | None:
        """Extract taxonomies from bound params or input artifact."""
        if "taxonomies" in self._bound_params:
            return self._bound_params["taxonomies"]
        # If input is an Artifact with taxonomies in data, extract it
        if isinstance(input, Artifact) and isinstance(input.data, dict):
            return input.data.get("taxonomies")
        return None

    def _validate_classifications(
        self, data: dict[str, Any], taxonomies: dict[str, list[str]]
    ) -> list[str]:
        """Validate classify output against ADR-005 constraints.

        Returns list of violation description strings (empty if valid).

        Checks:
          1. Uniqueness: at most one classification per taxonomy name
          2. Closed-set: each label must be in the taxonomy's label list
        """
        violations: list[str] = []
        classifications = data.get("classifications", [])

        # Check uniqueness by taxonomy
        seen_taxonomies: set[str] = set()
        for cls in classifications:
            tax_name = cls.get("taxonomy", "")
            if tax_name in seen_taxonomies:
                violations.append(f"Duplicate taxonomy '{tax_name}' in classifications")
            seen_taxonomies.add(tax_name)

        # Check closed-set labels
        for cls in classifications:
            tax_name = cls.get("taxonomy", "")
            label = cls.get("label", "")
            if tax_name in taxonomies:
                valid_labels = taxonomies[tax_name]
                if label not in valid_labels:
                    violations.append(
                        f"Label '{label}' not in taxonomy '{tax_name}' "
                        f"(valid: {valid_labels})"
                    )

        return violations
