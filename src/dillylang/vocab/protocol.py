"""Operator protocol: the contract any substrate must implement.

This is the vocabulary-level interface. Substrate implementations
(e.g. DSPy modules in dillylang.operators) implement this protocol.
The vocabulary layer never imports substrate code.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from dillylang.vocab.types import Context, RunResult


@runtime_checkable
class OperatorProtocol(Protocol):
    """Contract that any substrate must implement.

    An operator has a name and can run on an input within a context,
    producing a RunResult containing the output artifact(s) and trace.
    """

    @property
    def name(self) -> str: ...

    def run(self, input: Any, ctx: Context) -> RunResult: ...
