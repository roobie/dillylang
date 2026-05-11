"""InvertOperator: Munger/Jacobi inversion -- what guarantees failure.

Wraps BaseDSPyOperator with the invert-specific prompt and schema.
The key quality gate: every failure mode must name a concrete causal
mechanism, not a generic risk.

Spec reference: INDEX.md section 6 (invert schema).
No steering parameters in v0.
"""

from __future__ import annotations

from dillylang.operators.base import BaseDSPyOperator
from dillylang.vocab.schemas import InvertOutput

# Spec section 6 docstring with the anti-generic-risk instruction.
# "mechanism" is the critical quality guard word.
_INVERT_DOCSTRING = (
    "Munger/Jacobi inversion. Stop asking 'how succeed' and ask 'what "
    "guarantees failure.' Require concrete mechanism descriptions for each "
    "failure mode. Reject generic risks ('market changes') that lack a "
    "specific causal chain. Each failure mode must name a mechanism -- the "
    "specific process by which this failure occurs."
)


class InvertOperator(BaseDSPyOperator):
    """Inversion operator: enumerate what guarantees failure.

    Produces anti-goals (inverted success criteria), failure modes (each
    with a concrete causal mechanism), and near-misses (boundary conditions
    that almost fail).
    """

    def __init__(self) -> None:
        super().__init__(
            name="invert",
            docstring=_INVERT_DOCSTRING,
            input_model=None,
            output_model=InvertOutput,
        )
