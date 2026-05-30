"""Sentinel evaluators - local-first hallucination & anomaly detection.

The default suite runs without any external model or network call, so it is safe
to execute inline during trace ingestion. Heavier, model-based evaluators
(semantic similarity via sentence-transformers) are used automatically when the
optional dependency is installed.
"""

from __future__ import annotations

from .base import EvalInput, EvalResult, Evaluator, Verdict
from .registry import (
    DEFAULT_INLINE_SUITE,
    aggregate_score,
    available,
    create,
    register,
    run_suite,
)
from .runner import EvalReport, CaseResult, run_eval, load_dataset

__all__ = [
    "EvalInput",
    "EvalResult",
    "Evaluator",
    "Verdict",
    "run_suite",
    "aggregate_score",
    "available",
    "create",
    "register",
    "DEFAULT_INLINE_SUITE",
    "EvalReport",
    "CaseResult",
    "run_eval",
    "load_dataset",
]

__version__ = "0.1.0"
