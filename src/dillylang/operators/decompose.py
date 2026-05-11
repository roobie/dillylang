"""DecomposeOperator: structural decomposition into axioms, derivations, assumptions.

Wraps BaseDSPyOperator with the decompose-specific prompt and schema.
The docstring is the highest-signal element -- it becomes the DSPy Signature's
task description, which is rendered into every LLM call.

Spec reference: INDEX.md section 4 (decompose schema).
Steering parameter: focus (optional, via ADR-007).
"""

from __future__ import annotations

from dillylang.operators.base import BaseDSPyOperator
from dillylang.vocab.schemas import DecomposeInput, DecomposeOutput

# The decompose docstring from spec section 4, extended with the full
# anti-generic-outline instruction. This is what the LLM sees.
_DECOMPOSE_DOCSTRING = (
    "Separate what's load-bearing from what's assumed. Not a generic outline "
    "-- a search for axioms. Identify axioms (foundational, not derivable), "
    "derivations (follow from axioms, with dependency list), and assumptions "
    "(treated as true without justification). Be ruthless. Three sharp axioms "
    "beat ten soft ones."
)


class DecomposeOperator(BaseDSPyOperator):
    """Structural decomposition operator.

    Decomposes a problem into its load-bearing structure: axioms (foundational
    statements), derivations (claims that follow), and assumptions (unverified
    premises). The focus steering parameter narrows decomposition when bound.
    """

    def __init__(self) -> None:
        super().__init__(
            name="decompose",
            docstring=_DECOMPOSE_DOCSTRING,
            input_model=DecomposeInput,
            output_model=DecomposeOutput,
        )
