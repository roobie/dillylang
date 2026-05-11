"""Tests for _check_input_quality heuristic in BaseDSPyOperator.

These tests exercise the pure function directly -- no DSPy or LLM setup needed.
The heuristic is a warning-only gate: it never rejects input, only flags
noun-phrase inputs that lack verbs or question marks.
"""

from __future__ import annotations

from dillylang.operators.base import _check_input_quality


class TestNounPhraseWarnings:
    """Inputs that look like noun phrases should produce warnings."""

    def test_single_word_noun_phrase(self) -> None:
        """'clarity' (7 chars, above 5-char cutoff) returns a warning."""
        result = _check_input_quality("clarity")
        assert result is not None
        assert "noun phrase" in result.lower()

    def test_long_noun_phrase(self) -> None:
        """Long noun phrase without verb or question returns warning."""
        result = _check_input_quality(
            "The architecture of microservices in distributed systems"
        )
        assert result is not None
        assert "noun phrase" in result.lower()

    def test_noun_phrase_warning_mentions_input(self) -> None:
        """Warning string includes the input text for diagnostic context."""
        result = _check_input_quality("clarity")
        assert result is not None
        assert "clarity" in result


class TestQuestionInputs:
    """Inputs with question marks should not produce warnings."""

    def test_question_returns_none(self) -> None:
        """Question mark is a strong signal of problem statement."""
        result = _check_input_quality("How can we improve clarity?")
        assert result is None

    def test_question_anywhere(self) -> None:
        """Question mark anywhere in input suppresses warning."""
        result = _check_input_quality("clarity -- is it achievable?")
        assert result is None


class TestVerbInputs:
    """Inputs with verb-like patterns should not produce warnings."""

    def test_imperative_verb(self) -> None:
        """Imperative verb 'Design' returns None."""
        result = _check_input_quality(
            "Design a system that handles high load"
        )
        assert result is None

    def test_action_verb(self) -> None:
        """Action verb 'improve' returns None."""
        result = _check_input_quality("improve the performance of the database")
        assert result is None

    def test_interrogative_word(self) -> None:
        """Interrogative 'How' returns None even without question mark."""
        result = _check_input_quality("How to handle errors gracefully")
        assert result is None

    def test_modal_verb(self) -> None:
        """Modal verb 'should' returns None."""
        result = _check_input_quality("We should reduce latency by 50%")
        assert result is None


class TestShortAndEmptyInputs:
    """Short and empty inputs should not produce warnings (not enough signal)."""

    def test_empty_string(self) -> None:
        """Empty input returns None."""
        result = _check_input_quality("")
        assert result is None

    def test_short_input_3_chars(self) -> None:
        """'abc' (3 chars, below 5-char cutoff) returns None."""
        result = _check_input_quality("abc")
        assert result is None

    def test_short_input_4_chars(self) -> None:
        """'test' (4 chars, below 5-char cutoff) returns None."""
        result = _check_input_quality("test")
        assert result is None

    def test_whitespace_only(self) -> None:
        """Whitespace-only input returns None (stripped length < 5)."""
        result = _check_input_quality("    ")
        assert result is None


class TestWarningFormat:
    """The warning string has a useful diagnostic format."""

    def test_short_input_in_warning(self) -> None:
        """Short noun-phrase inputs appear fully in the warning."""
        result = _check_input_quality("clarity")
        assert result is not None
        assert "Input:" in result or "Input begins with:" in result

    def test_long_input_truncated_in_warning(self) -> None:
        """Inputs longer than 50 chars are truncated in the warning."""
        long_input = "x" * 60  # 60 chars, no verbs, no question
        result = _check_input_quality(long_input)
        assert result is not None
        assert "..." in result
