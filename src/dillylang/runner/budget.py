"""Budget checking and accounting functions.

Budget is per-pipeline. The runner calls check_budget before each operator
execution and deduct_budget after. Operators cannot override the global budget.

deduct_budget returns a NEW Budget (immutable pattern) -- the runner reassigns
ctx.budget to accumulate across pipeline steps.
"""

from __future__ import annotations

from dillylang.vocab.types import Budget


def check_budget(budget: Budget) -> bool:
    """Return True if budget allows another LLM call.

    All three limits must pass: call count, token count, wall time.
    """
    return (
        budget.llm_calls_used < budget.max_llm_calls
        and budget.tokens_used < budget.max_tokens
        and budget.elapsed_ms < budget.max_wall_time_ms
    )


def deduct_budget(
    budget: Budget,
    tokens: int = 0,
    elapsed_ms: int = 0,
) -> Budget:
    """Return a new Budget with one LLM call deducted plus token/time costs.

    Does NOT mutate the input budget. The runner assigns the returned value
    back to ctx.budget to accumulate across pipeline steps.
    """
    return Budget(
        max_llm_calls=budget.max_llm_calls,
        max_tokens=budget.max_tokens,
        max_wall_time_ms=budget.max_wall_time_ms,
        llm_calls_used=budget.llm_calls_used + 1,
        tokens_used=budget.tokens_used + tokens,
        elapsed_ms=budget.elapsed_ms + elapsed_ms,
    )
