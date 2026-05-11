"""Tests for dillylang.vocab.protocol -- OperatorProtocol interface."""

from __future__ import annotations

from tests.conftest import MockOperator

from dillylang.vocab.protocol import OperatorProtocol


def test_protocol_is_runtime_checkable(mock_operator: MockOperator) -> None:
    """MockOperator implementing run() and name passes isinstance check."""
    assert isinstance(mock_operator, OperatorProtocol)


def test_protocol_rejects_non_conforming() -> None:
    """A class without run() method fails isinstance check."""

    class NoRun:
        @property
        def name(self) -> str:
            return "no_run"

    assert not isinstance(NoRun(), OperatorProtocol)


def test_protocol_rejects_no_name() -> None:
    """A class with run() but no name fails isinstance check."""

    class NoName:
        def run(self, input, ctx):
            pass

    assert not isinstance(NoName(), OperatorProtocol)


def test_protocol_name_attribute(mock_operator: MockOperator) -> None:
    """Mock operator exposes name attribute via property."""
    assert mock_operator.name == "mock_op"


def test_protocol_custom_name() -> None:
    """MockOperator accepts custom name at construction."""
    op = MockOperator(op_name="evaluate")
    assert op.name == "evaluate"
    assert isinstance(op, OperatorProtocol)
