"""AnalogizeOperator: cross-domain structural mapping with stowaway detection.

Wraps BaseDSPyOperator with the analogize-specific prompt and schema.
The key quality gate: every analogy must name its stowaways -- aspects
of the source domain that do NOT transfer cleanly.

Spec reference: INDEX.md section 6 (analogize schema).
Steering parameter: domains (optional, formalized per ADR-007).
"""

from __future__ import annotations

from dillylang.operators.base import BaseDSPyOperator
from dillylang.vocab.schemas import AnalogizeInput, AnalogizeOutput

# Spec section 6 docstring with the stowaways guard.
_ANALOGIZE_DOCSTRING = (
    "Map the problem to another domain that shares structural relationships. "
    "Import mechanism, not metaphor. For each analogy, identify the structural "
    "mechanism that transfers and explicitly name the stowaways -- aspects of "
    "the target domain that do NOT transfer cleanly. Without stowaways, "
    "analogy defaults to celebrating mappings and ignoring their limits. "
    "The stowaways field is critical."
)


class AnalogizeOperator(BaseDSPyOperator):
    """Cross-domain analogy operator: find structural parallels with limits.

    Produces a problem_signature (structural fingerprint) and a list of
    analogies, each with mechanism_mapping, transferable_insight, and
    stowaways (the critical anti-pattern guard).
    """

    def __init__(self) -> None:
        super().__init__(
            name="analogize",
            docstring=_ANALOGIZE_DOCSTRING,
            input_model=AnalogizeInput,
            output_model=AnalogizeOutput,
        )
