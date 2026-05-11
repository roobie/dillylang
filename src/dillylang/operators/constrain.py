"""ConstrainOperator: tighten constraints to narrow the solution space.

Wraps BaseDSPyOperator with the constrain-specific prompt and schema.
The prompt focuses on adding well-justified constraints that eliminate
classes of bad solutions while surfacing the tradeoffs of each restriction.

Spec reference: INDEX.md section 6 (constrain schema).
No steering parameters per ADR-007 (no empirical demand yet).
"""

from __future__ import annotations

from dillylang.operators.base import BaseDSPyOperator
from dillylang.vocab.schemas import ConstrainOutput

# Independent prompt for constraining (D-02: not a mirrored skeleton of relax).
# Focuses on the narrowing direction: finding what limits can be productively
# added, making implicit constraints explicit, and assessing the cost of each.
_CONSTRAIN_DOCSTRING = (
    "Identify constraints that narrow the solution space in productive ways. "
    "Start by surfacing implicit constraints already present in the problem "
    "and making them explicit -- hidden assumptions about scope, resources, "
    "or compatibility are constraints whether acknowledged or not. Then add "
    "new constraints that eliminate the largest class of unviable solutions "
    "first. For each constraint, explain WHY it helps: what failure modes it "
    "prevents or what quality it enforces. Assess how constraints interact -- "
    "do they compound to create dead zones, or do they reinforce each other? "
    "Surface the tradeoff for every constraint: what capability or flexibility "
    "is given up in exchange for the narrowing. Prioritize constraints that "
    "are load-bearing over those that are merely conventional."
)


class ConstrainOperator(BaseDSPyOperator):
    """Feasibility axis narrowing operator.

    Tightens constraints on a problem to narrow the solution space,
    surfacing implicit constraints, adding productive new ones, and
    documenting the tradeoffs of each restriction. Reuses the Tradeoff
    model from synthesize for gained/given_up structure.
    """

    def __init__(self) -> None:
        super().__init__(
            name="constrain",
            docstring=_CONSTRAIN_DOCSTRING,
            input_model=None,  # D-07: no steering params yet
            output_model=ConstrainOutput,
        )
