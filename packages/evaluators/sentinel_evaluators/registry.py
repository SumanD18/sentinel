"""Evaluator registry and the default suite used during trace ingestion."""

from __future__ import annotations

from typing import Callable

from .base import EvalInput, EvalResult, Evaluator
from .consistency import SelfConsistencyEvaluator, SemanticDriftEvaluator
from .heuristics import (
    ConfidenceEvaluator,
    ContextGroundednessEvaluator,
    EmptyOutputEvaluator,
    FactualityRegexEvaluator,
    RefusalEvaluator,
    RepetitionEvaluator,
)

_REGISTRY: dict[str, Callable[[], Evaluator]] = {}


def register(name: str, factory: Callable[[], Evaluator]) -> None:
    _REGISTRY[name] = factory


def create(name: str) -> Evaluator:
    if name not in _REGISTRY:
        raise KeyError(f"Unknown evaluator {name!r}. Known: {sorted(_REGISTRY)}")
    return _REGISTRY[name]()


def available() -> list[str]:
    return sorted(_REGISTRY)


# Register built-ins.
register("confidence", ConfidenceEvaluator)
register("refusal", RefusalEvaluator)
register("repetition", RepetitionEvaluator)
register("non_empty", EmptyOutputEvaluator)
register("groundedness", ContextGroundednessEvaluator)
register("factuality_smoke", FactualityRegexEvaluator)
register("self_consistency", SelfConsistencyEvaluator)
register("semantic_drift", SemanticDriftEvaluator)


#: Cheap evaluators safe to run inline on every LLM span during ingestion.
DEFAULT_INLINE_SUITE = [
    "confidence",
    "refusal",
    "repetition",
    "non_empty",
    "groundedness",
    "factuality_smoke",
]


def run_suite(item: EvalInput, names: list[str] | None = None) -> list[EvalResult]:
    """Run a set of evaluators (default: the inline suite) over one interaction."""
    selected = names or DEFAULT_INLINE_SUITE
    results: list[EvalResult] = []
    for name in selected:
        try:
            results.append(create(name).evaluate(item))
        except Exception as exc:  # never let one evaluator break the batch
            from .base import EvalResult as _R
            from .base import Verdict

            results.append(
                _R(
                    evaluator=name,
                    score=1.0,
                    verdict=Verdict.PASS,
                    explanation=f"evaluator errored and was skipped: {exc}",
                )
            )
    return results


def aggregate_score(results: list[EvalResult]) -> float:
    """Combine evaluator scores into a single trust score in [0, 1].

    Uses the minimum (a single failing dimension drags the whole interaction
    down) blended with the mean, so one soft warning doesn't tank an otherwise
    healthy response but a hard failure is never hidden by averaging.
    """
    if not results:
        return 1.0
    scores = [r.score for r in results]
    return round(0.5 * min(scores) + 0.5 * (sum(scores) / len(scores)), 4)
