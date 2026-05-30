"""Self-consistency and semantic-drift evaluators.

Self-consistency: sample the same prompt several times; if the model is
confident and grounded, the samples agree. Wide disagreement is a strong
hallucination signal (the SelfCheckGPT intuition, done locally and cheaply).

Semantic drift: compare an output against an expected/reference answer and alert
when similarity falls below a threshold.
"""

from __future__ import annotations

from itertools import combinations

from .base import EvalInput, EvalResult, Evaluator
from .text import cosine_bow


def _embedder():
    """Return a callable similarity(a, b)->float. Uses sentence-transformers when
    available for higher quality, otherwise falls back to bag-of-words cosine."""
    try:  # optional, heavy dependency
        from sentence_transformers import SentenceTransformer, util  # type: ignore

        model = SentenceTransformer("all-MiniLM-L6-v2")

        def sim(a: str, b: str) -> float:
            ea, eb = model.encode([a, b], convert_to_tensor=True)
            return float(util.cos_sim(ea, eb).item())

        return sim
    except Exception:
        return cosine_bow


class SelfConsistencyEvaluator(Evaluator):
    """Scores agreement across ``item.samples``. Requires >= 2 samples."""

    name = "self_consistency"

    def __init__(self) -> None:
        self._sim = _embedder()

    def evaluate(self, item: EvalInput) -> EvalResult:
        samples = item.samples or []
        # The primary output counts as one of the samples.
        if item.output and item.output not in samples:
            samples = [item.output, *samples]
        if len(samples) < 2:
            return self._result(
                1.0, "Not enough samples for a consistency check.", samples=len(samples)
            )
        sims = [self._sim(a, b) for a, b in combinations(samples, 2)]
        mean = sum(sims) / len(sims)
        return self._result(
            mean,
            f"Mean pairwise similarity across {len(samples)} samples: {mean:.2f}.",
            pairwise=[round(s, 4) for s in sims],
        )


class SemanticDriftEvaluator(Evaluator):
    """Compares the output to a reference answer; low similarity == drift."""

    name = "semantic_drift"

    def __init__(self, threshold: float = 0.7) -> None:
        self.warn_threshold = threshold
        self._sim = _embedder()

    def evaluate(self, item: EvalInput) -> EvalResult:
        if not item.reference:
            return self._result(1.0, "No reference provided; drift not applicable.")
        sim = self._sim(item.output, item.reference)
        return self._result(
            sim,
            f"Similarity to reference: {sim:.2f}.",
            similarity=round(sim, 4),
        )
