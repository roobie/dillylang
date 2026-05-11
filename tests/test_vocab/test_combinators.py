"""Tests for dillylang.vocab.combinators -- declarative composition nodes."""

from __future__ import annotations

from tests.conftest import MockOperator

from dillylang.vocab.combinators import (
    BindNode,
    FilterNode,
    MapNode,
    ParallelNode,
    PipeNode,
)


def test_pipe_node_holds_operators() -> None:
    """PipeNode stores operators in order."""
    op_a = MockOperator("op_a")
    op_b = MockOperator("op_b")
    pipe = PipeNode(op_a, op_b)
    assert pipe.operators == (op_a, op_b)


def test_pipe_node_has_no_run() -> None:
    """PipeNode is declarative -- no run() method."""
    op = MockOperator()
    pipe = PipeNode(op)
    assert not hasattr(pipe, "run")


def test_parallel_node_holds_operators() -> None:
    """ParallelNode stores operators for fan-out."""
    op_a = MockOperator("invert")
    op_b = MockOperator("rotate")
    par = ParallelNode(op_a, op_b)
    assert par.operators == (op_a, op_b)


def test_bind_node_name_is_underlying() -> None:
    """BindNode.name delegates to the underlying operator's name."""
    op = MockOperator("evaluate")
    bound = BindNode(operator=op, params={"criterion": "load_bearing"})
    assert bound.name == "evaluate"


def test_bind_node_stores_params() -> None:
    """BindNode stores the parameters to be pre-filled."""
    op = MockOperator("decompose")
    bound = BindNode(operator=op, params={"focus": "requirements"})
    assert bound.params == {"focus": "requirements"}


def test_map_node_holds_operator() -> None:
    """MapNode stores the operator to apply over a collection."""
    op = MockOperator("invert")
    m = MapNode(op)
    assert m.operator is op


def test_filter_node_defaults() -> None:
    """FilterNode defaults: keep_partial=True, fail_on_predicate_error=False."""
    pred = MockOperator("evaluate")
    f = FilterNode(predicate_op=pred)
    assert f.keep_partial is True
    assert f.fail_on_predicate_error is False


def test_filter_node_configurable() -> None:
    """FilterNode accepts non-default keep_partial and fail_on_predicate_error."""
    pred = MockOperator("evaluate")
    f = FilterNode(predicate_op=pred, keep_partial=False, fail_on_predicate_error=True)
    assert f.keep_partial is False
    assert f.fail_on_predicate_error is True


def test_all_nodes_are_declarative() -> None:
    """None of the combinator node classes have a run() method."""
    op = MockOperator()
    nodes = [
        PipeNode(op),
        ParallelNode(op),
        BindNode(operator=op, params={}),
        MapNode(op),
        FilterNode(predicate_op=op),
    ]
    for node in nodes:
        assert not hasattr(node, "run"), (
            f"{type(node).__name__} should not have run() -- "
            f"execution is in Plan 06"
        )
