"""ConcretizeOperator: derive concrete instances from abstract principles.

Wraps BaseDSPyOperator with the concretize-specific prompt and schema.
The key quality gate: each instance must trace its derivation chain back
to the abstract principle and name the domain constraints that shaped it.

Spec reference: INDEX.md section 6 (concretize schema).
No steering parameters per ADR-007 (no empirical demand yet).
"""

from __future__ import annotations

from dillylang.operators.base import BaseDSPyOperator
from dillylang.vocab.schemas import ConcretizeOutput

# Independent prompt for concretization (D-02: not a mirrored skeleton of abstract).
# Focuses on the downward direction: generating actionable, domain-grounded
# instances from principles, with explicit derivation chains and constraints.
_CONCRETIZE_DOCSTRING = (
    "Given abstract principles or general statements, generate specific, actionable "
    "instances grounded in a real or plausible domain. Each instance must trace an "
    "explicit derivation chain from the abstract principle to the concrete result -- "
    "show the reasoning steps, not just the outcome. Name the domain constraints "
    "that shaped each instance: what about the target domain forced this particular "
    "form. Produce instances diverse enough to demonstrate that the principle "
    "generalizes, not just variations of the same example. Identify the target domain "
    "that grounds all instances. Prefer instances that are immediately testable or "
    "observable over those that remain theoretical."
)


class ConcretizeOperator(BaseDSPyOperator):
    """Concretization operator: general-to-concrete transformation.

    Generates concrete instances from abstract principles, grounding
    them in a specific domain with explicit derivation chains and
    domain constraints. Each instance demonstrates how the abstract
    principle manifests in practice.
    """

    def __init__(self) -> None:
        super().__init__(
            name="concretize",
            docstring=_CONCRETIZE_DOCSTRING,
            input_model=None,  # D-07: no steering params yet
            output_model=ConcretizeOutput,
        )
