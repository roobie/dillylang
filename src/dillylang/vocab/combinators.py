"""Declarative combinator definitions over OperatorProtocol.

These are composition NODES -- they define pipeline structure but do NOT
implement execution. No run() methods. The executable implementations
live in dillylang.combinators (Plan 06). This preserves the pure-vocabulary
boundary: vocab defines shapes, substrate executes them.

Nodes can be introspected, serialized, and analyzed without execution.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from dillylang.vocab.protocol import OperatorProtocol


class PipeNode(BaseModel):
    """Declares sequential composition: op1 -> op2 -> ... -> opN.

    Each operator's output is fed to the next as input.
    """

    model_config = {"arbitrary_types_allowed": True}

    operators: tuple[OperatorProtocol, ...] = Field(
        description="operators in execution order"
    )

    def __init__(self, *ops: OperatorProtocol) -> None:
        super().__init__(operators=ops)


class ParallelNode(BaseModel):
    """Declares fan-out composition: same input to all operators.

    All operators run on the same input; outputs collected as a list.
    """

    model_config = {"arbitrary_types_allowed": True}

    operators: tuple[OperatorProtocol, ...] = Field(
        description="operators to run in parallel"
    )

    def __init__(self, *ops: OperatorProtocol) -> None:
        super().__init__(operators=ops)


class BindNode(BaseModel):
    """Declares parameter pre-filling (currying).

    bind is compile-time per spec section 5: it does not appear in
    runtime traces. A bound operator traces as its underlying operator.
    """

    model_config = {"arbitrary_types_allowed": True}

    operator: OperatorProtocol = Field(description="the operator to bind params to")
    params: dict[str, Any] = Field(description="parameters to pre-fill")

    @property
    def name(self) -> str:
        """A bound operator's name is its underlying operator's name."""
        return self.operator.name


class MapNode(BaseModel):
    """Declares collection application: apply op to each element.

    Concurrent by default at execution time (Plan 06).
    """

    model_config = {"arbitrary_types_allowed": True}

    operator: OperatorProtocol = Field(description="operator to map over collection")

    def __init__(self, op: OperatorProtocol) -> None:
        super().__init__(operator=op)


class FilterNode(BaseModel):
    """Declares verdict-based filtering over a collection.

    The predicate is itself an operator (often bind(evaluate, criterion="X")).
    Verdict mapping per spec section 7:
      pass => keep, partial => keep (default), fail => drop.
    """

    model_config = {"arbitrary_types_allowed": True}

    predicate_op: OperatorProtocol = Field(description="judge operator used as predicate")
    keep_partial: bool = Field(
        default=True,
        description="if True, 'partial' verdict keeps the item (default per spec)",
    )
    fail_on_predicate_error: bool = Field(
        default=False,
        description="if True, predicate LLM/API errors promote to combinator failure",
    )


class BranchNode(BaseModel):
    """Declares conditional dispatch based on classify labels.

    Routes to sub-pipelines based on a taxonomy classification.
    Default pipeline is required (D-05).
    """

    model_config = {"arbitrary_types_allowed": True}

    taxonomy_name: str = Field(description="which taxonomy to read the label from")
    routes: dict[str, Any] = Field(description="mapping from label to pipeline node")
    default: Any = Field(description="pipeline node for unmatched labels (required)")
