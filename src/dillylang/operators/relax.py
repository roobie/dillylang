"""RelaxOperator: loosen constraints to widen the solution space.

Wraps BaseDSPyOperator with the relax-specific prompt and schema.
The prompt focuses on identifying which constraints are conventional
rather than load-bearing, and what possibilities open when they are
removed -- while honestly surfacing the risks.

Spec reference: INDEX.md section 6 (relax schema).
No steering parameters per ADR-007 (no empirical demand yet).
"""

from __future__ import annotations

from dillylang.operators.base import BaseDSPyOperator
from dillylang.vocab.schemas import RelaxOutput

# Independent prompt for relaxation (D-02: not a mirrored skeleton of constrain).
# Focuses on the widening direction: questioning whether existing constraints
# are truly necessary, distinguishing load-bearing from conventional limits,
# and exploring what becomes possible when constraints are loosened.
_RELAX_DOCSTRING = (
    "Examine the constraints -- explicit and implicit -- that bound the current "
    "problem and determine which ones can be loosened without breaking the "
    "solution. Distinguish between load-bearing constraints (relaxing them "
    "causes structural failure) and conventional constraints (they exist by "
    "habit, precedent, or unexamined assumption). For each constraint you "
    "loosen, describe the original form, what you changed, and why the "
    "relaxation is acceptable. Enumerate the new possibilities that open up: "
    "what solutions, approaches, or design choices become available that were "
    "previously ruled out? Be honest about risks -- every relaxation trades "
    "safety for freedom. Trace interdependencies: loosening one constraint "
    "may automatically loosen or tighten others."
)


class RelaxOperator(BaseDSPyOperator):
    """Feasibility axis widening operator.

    Loosens constraints on a problem to widen the solution space,
    distinguishing load-bearing from conventional constraints, enumerating
    new possibilities that relaxation enables, and surfacing the risks
    introduced by each loosening.
    """

    def __init__(self) -> None:
        super().__init__(
            name="relax",
            docstring=_RELAX_DOCSTRING,
            input_model=None,  # D-07: no steering params yet
            output_model=RelaxOutput,
        )
