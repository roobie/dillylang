"""Tests for budget checking and accounting functions."""

from __future__ import annotations

from dillylang.runner.budget import check_budget, deduct_budget
from dillylang.vocab.types import Budget


def test_check_budget_allows_when_under_limit() -> None:
    """Default budget allows LLM calls."""
    budget = Budget()
    assert check_budget(budget) is True


def test_check_budget_blocks_when_calls_exhausted() -> None:
    """Budget blocks when LLM call count reaches ceiling."""
    budget = Budget(max_llm_calls=2, llm_calls_used=2)
    assert check_budget(budget) is False


def test_check_budget_blocks_when_tokens_exhausted() -> None:
    """Budget blocks when token count reaches ceiling."""
    budget = Budget(max_tokens=100, tokens_used=100)
    assert check_budget(budget) is False


def test_check_budget_blocks_when_time_exhausted() -> None:
    """Budget blocks when wall time reaches ceiling."""
    budget = Budget(max_wall_time_ms=1000, elapsed_ms=1000)
    assert check_budget(budget) is False


def test_deduct_budget_increments_calls() -> None:
    """Deducting budget increments llm_calls_used and adds token/time costs."""
    budget = Budget()
    result = deduct_budget(budget, tokens=500, elapsed_ms=200)

    assert result.llm_calls_used == 1
    assert result.tokens_used == 500
    assert result.elapsed_ms == 200


def test_deduct_budget_does_not_mutate_original() -> None:
    """Original budget is unchanged after deduct."""
    budget = Budget()
    deduct_budget(budget, tokens=500, elapsed_ms=200)

    assert budget.llm_calls_used == 0
    assert budget.tokens_used == 0
    assert budget.elapsed_ms == 0


def test_deduct_budget_accumulates() -> None:
    """Two sequential deductions accumulate correctly."""
    budget = Budget()
    after_first = deduct_budget(budget, tokens=300, elapsed_ms=100)
    after_second = deduct_budget(after_first, tokens=200, elapsed_ms=150)

    assert after_second.llm_calls_used == 2
    assert after_second.tokens_used == 500
    assert after_second.elapsed_ms == 250
