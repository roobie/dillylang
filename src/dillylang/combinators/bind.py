"""Bind combinator: compile-time typed currying of steering parameters.

bind is a compile-time transform per spec section 5: it does NOT appear
in runtime traces. A bound operator traces as its underlying operator.

Bind validates parameter names against the operator's input_model at
bind time (fail early, not at LLM call time). Bound parameters are
stored immutably -- mutating the original dict after bind has no effect.
"""

from __future__ import annotations

from copy import deepcopy
from types import MappingProxyType
from typing import Any

from dillylang.vocab.types import Context, RunResult


class BoundOperator:
    """Wrapper that pre-fills steering parameters on an operator.

    Compile-time transform: name delegates to the underlying operator,
    no trace entry emitted, is_combinator preserved from the wrapped operator.
    """

    def __init__(self, operator: Any, params: dict[str, Any]) -> None:
        self._operator = operator
        # Freeze: deep-copy then wrap as immutable mapping
        self._bound_params: MappingProxyType[str, Any] = MappingProxyType(deepcopy(params))

    @property
    def name(self) -> str:
        """Delegate to underlying operator -- bind is invisible."""
        return self._operator.name

    @property
    def is_combinator(self) -> bool:
        """Preserve routing behavior of the wrapped operator."""
        return getattr(self._operator, "is_combinator", False)

    @property
    def input_model(self) -> Any:
        """Expose underlying operator's input_model if available."""
        return getattr(self._operator, "_input_model", None)

    def run(self, input: Any, ctx: Context) -> RunResult:
        """Execute with bound params merged.

        For BaseDSPyOperator: uses with_bound_params() for substrate-level merging.
        For generic OperatorProtocol: enriches the input with bound params.
        """
        params = dict(self._bound_params)

        # Substrate-aware path: BaseDSPyOperator.with_bound_params
        if hasattr(self._operator, "with_bound_params"):
            copy = self._operator.with_bound_params(**params)
            return copy.run(input, ctx)

        # Generic path: merge params into input
        if isinstance(input, dict):
            enriched = {**input, **params}
        else:
            # Wrap non-dict input alongside params
            enriched = {"_input": input, **params}
        return self._operator.run(enriched, ctx)


def bind(operator: Any, **params: Any) -> BoundOperator:
    """Pre-fill steering parameters on an operator (compile-time currying).

    Validates that every param key is a valid field of the operator's
    input_model (if available). Raises ValueError at bind time for
    unknown params -- fail early, not at LLM call time.

    Per spec section 5: bind does not appear in runtime traces.
    The bound operator traces as its underlying operator.
    """
    if not params:
        raise ValueError("bind requires at least one parameter")

    # Bind-time validation: check param names against input_model
    input_model = getattr(operator, "_input_model", None)
    if input_model is not None:
        valid_fields = set(input_model.model_fields.keys())
        invalid = set(params.keys()) - valid_fields
        if invalid:
            raise ValueError(
                f"Unknown parameters for {operator.name}: {sorted(invalid)}. "
                f"Valid parameters: {sorted(valid_fields)}"
            )

    return BoundOperator(operator, params)
