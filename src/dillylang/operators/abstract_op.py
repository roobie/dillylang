"""AbstractOperator: extract general principles from concrete instances.

Wraps BaseDSPyOperator with the abstract-specific prompt and schema.
The key quality gate: each principle must be grounded in specific concrete
instances and name an abstraction level relative to the input.

Spec reference: INDEX.md section 6 (abstract schema).
No steering parameters per ADR-007 (no empirical demand yet).

Named abstract_op.py to avoid collision with Python's `abstract` keyword.
"""

from __future__ import annotations

from dillylang.operators.base import BaseDSPyOperator
from dillylang.vocab.schemas import AbstractOutput

# Independent prompt for abstraction (D-02: not a mirrored skeleton of concretize).
# Focuses on the upward direction: finding what's structurally shared across
# concrete instances, extracting the governing rules, and naming the pattern.
_ABSTRACT_DOCSTRING = (
    "Given concrete instances, extract the underlying principles that govern them. "
    "Look for structural commonalities, not surface similarities -- two instances "
    "may look different but share the same governing mechanism. For each principle, "
    "explicitly name which concrete instances it was derived from and describe its "
    "abstraction level relative to the input. Distinguish between principles that "
    "are one step above the input (local generalizations) and those that capture "
    "deeper structural invariants. Identify the source pattern -- the structural "
    "thread that connects all the concrete instances. Prefer fewer well-grounded "
    "principles over many shallow ones."
)


class AbstractOperator(BaseDSPyOperator):
    """Abstraction operator: concrete-to-general transformation.

    Extracts general principles from concrete instances, identifying
    structural commonalities and the governing patterns that explain why
    the instances work. Each principle is grounded in the specific
    instances it was derived from.
    """

    def __init__(self) -> None:
        super().__init__(
            name="abstract",
            docstring=_ABSTRACT_DOCSTRING,
            input_model=None,  # D-07: no steering params yet
            output_model=AbstractOutput,
        )
