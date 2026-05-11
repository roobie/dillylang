"""Substrate layer -- DSPy operator implementations.

Converts between vocabulary Pydantic schemas and DSPy Signature fields.
The vocabulary layer (dillylang.vocab) has zero DSPy imports; this package
is where the adapter boundary lives.

All 13 operators are exported here:
  Transformers: decompose, synthesize, invert, rotate, analogize, abstract, concretize, constrain, relax
  Judges: evaluate, rank, classify, compare
"""

from __future__ import annotations

from dillylang.operators.abstract_op import AbstractOperator
from dillylang.operators.adapter import prediction_to_vocab_output, vocab_schema_to_signature
from dillylang.operators.analogize import AnalogizeOperator
from dillylang.operators.base import BaseDSPyOperator
from dillylang.operators.classify import ClassifyOperator
from dillylang.operators.compare import CompareOperator
from dillylang.operators.concretize import ConcretizeOperator
from dillylang.operators.constrain import ConstrainOperator
from dillylang.operators.decompose import DecomposeOperator
from dillylang.operators.evaluate import EvaluateOperator
from dillylang.operators.invert import InvertOperator
from dillylang.operators.rank import RankOperator
from dillylang.operators.relax import RelaxOperator
from dillylang.operators.rotate import RotateOperator
from dillylang.operators.synthesize import SynthesizeOperator

__all__ = [
    "AbstractOperator",
    "AnalogizeOperator",
    "BaseDSPyOperator",
    "ClassifyOperator",
    "CompareOperator",
    "ConcretizeOperator",
    "ConstrainOperator",
    "DecomposeOperator",
    "EvaluateOperator",
    "InvertOperator",
    "RankOperator",
    "RelaxOperator",
    "RotateOperator",
    "SynthesizeOperator",
    "prediction_to_vocab_output",
    "vocab_schema_to_signature",
]
