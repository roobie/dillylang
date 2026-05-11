"""EvaluateOperator: criterion-based judgment of an artifact.

Wraps BaseDSPyOperator with the evaluate-specific prompt and schema.
The key constraint: criterion is REQUIRED -- evaluate without a
criterion is invalid. This is enforced by Pydantic validation on
EvaluateInput (no default for criterion).

Spec reference: INDEX.md section 6 (evaluate schema).
Steering parameter: criterion (required, via ADR-007).
"""

from __future__ import annotations

from dillylang.operators.base import BaseDSPyOperator
from dillylang.vocab.schemas import EvaluateInput, EvaluateOutput

# Spec section 6 docstring. The "criterion must be bound" instruction
# is the key quality gate for this judge operator.
_EVALUATE_DOCSTRING = (
    "Judge an artifact against an explicit criterion. The criterion must "
    "be bound before execution -- evaluate without a criterion is invalid. "
    "Produce a verdict of pass, partial, or fail with supporting evidence "
    "and rationale. Evidence must cite specific aspects of the artifact, "
    "not generic observations."
)


class EvaluateOperator(BaseDSPyOperator):
    """Judge operator: evaluate an artifact against a single criterion.

    Produces a verdict (pass/partial/fail), evidence, rationale, and
    confidence. The criterion steering parameter is required -- it has
    no default and must be provided via bind or direct input.

    Verdict semantics (spec section 7): pass=keep, partial=keep, fail=drop.
    """

    def __init__(self) -> None:
        super().__init__(
            name="evaluate",
            docstring=_EVALUATE_DOCSTRING,
            input_model=EvaluateInput,
            output_model=EvaluateOutput,
        )
