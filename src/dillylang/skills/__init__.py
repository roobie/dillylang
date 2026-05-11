"""Application layer -- meta-skill pipelines composing vocabulary operators.

This package contains the four meta-skills (translate, analyze, design, improve)
plus their deterministic boundary adapters (ingestion, metrics, renderers).

Dependency direction: skills -> operators/combinators/runner -> vocab.
"""

from __future__ import annotations

from dillylang.skills.analyze import AnalyzeResult, ComputeMetricsNode, analyze, render_analysis_report
from dillylang.skills.ingest import ingest_skill_directory
from dillylang.skills.metrics import compute_metrics
from dillylang.skills.translate import TranslateResult, render_dillylang_skill_description, translate

__all__ = [
    "AnalyzeResult",
    "ComputeMetricsNode",
    "TranslateResult",
    "analyze",
    "compute_metrics",
    "ingest_skill_directory",
    "render_analysis_report",
    "render_dillylang_skill_description",
    "translate",
]
