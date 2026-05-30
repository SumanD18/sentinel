"""Evaluator interface and result types.

An evaluator inspects a single LLM interaction (prompt + response, optionally
with context/reference) and returns a normalised score in ``[0, 1]`` plus a
verdict. Higher score == more trustworthy. Evaluators are deliberately cheap and
local-first: the defaults use only the standard library so they can run inline
during trace ingestion without calling out to an external model.
"""

from __future__ import annotations

import abc
import enum
from dataclasses import dataclass, field
from typing import Any, Optional


class Verdict(str, enum.Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class EvalInput:
    """Everything an evaluator may look at for one interaction."""

    output: str
    prompt: Optional[str] = None
    context: Optional[list[str]] = None  # retrieved docs, etc.
    reference: Optional[str] = None  # gold answer, when known
    samples: Optional[list[str]] = None  # alternative completions for consistency
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalResult:
    """Outcome of running one evaluator."""

    evaluator: str
    score: float  # 0..1, higher = more trustworthy
    verdict: Verdict
    explanation: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluator": self.evaluator,
            "score": round(self.score, 4),
            "verdict": self.verdict.value,
            "explanation": self.explanation,
            "details": self.details,
        }


class Evaluator(abc.ABC):
    """Base class. Subclasses implement :meth:`evaluate`."""

    name: str = "evaluator"
    #: Scores at or below this fail; between this and ``warn_threshold`` warn.
    fail_threshold: float = 0.4
    warn_threshold: float = 0.7

    def _verdict(self, score: float) -> Verdict:
        if score <= self.fail_threshold:
            return Verdict.FAIL
        if score < self.warn_threshold:
            return Verdict.WARN
        return Verdict.PASS

    def _result(self, score: float, explanation: str, **details: Any) -> EvalResult:
        score = max(0.0, min(1.0, score))
        return EvalResult(
            evaluator=self.name,
            score=score,
            verdict=self._verdict(score),
            explanation=explanation,
            details=details,
        )

    @abc.abstractmethod
    def evaluate(self, item: EvalInput) -> EvalResult:
        """Score a single interaction."""
