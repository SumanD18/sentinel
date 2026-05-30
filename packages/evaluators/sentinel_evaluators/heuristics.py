"""Heuristic, local-first evaluators.

None of these call an external model. They are fast enough to run inline during
trace ingestion and catch a surprising fraction of real problems: hedging /
low-confidence answers, refusals, degenerate repetition, and answers that ignore
their retrieved context (a strong hallucination signal in RAG).
"""

from __future__ import annotations

import re

from .base import EvalInput, EvalResult, Evaluator
from .text import cosine_bow, repetition_ratio, tokenize

# Phrases that correlate with hedging / fabricated confidence.
_HEDGES = [
    "i'm not sure",
    "i am not sure",
    "i cannot verify",
    "i can't verify",
    "as an ai",
    "i do not have access",
    "i don't have access",
    "to the best of my knowledge",
    "i might be wrong",
    "i'm not certain",
    "it is possible that",
    "i could be mistaken",
]

_REFUSALS = [
    "i cannot help with that",
    "i can't help with that",
    "i'm unable to",
    "i am unable to",
    "i won't be able to",
    "i cannot provide",
]


class ConfidenceEvaluator(Evaluator):
    """Scores linguistic confidence of the answer. Lots of hedging -> low score."""

    name = "confidence"

    def evaluate(self, item: EvalInput) -> EvalResult:
        text = item.output.lower()
        hits = [h for h in _HEDGES if h in text]
        # Each hedge phrase costs confidence, with diminishing returns.
        penalty = 1.0 - 0.85 ** len(hits)
        score = 1.0 - penalty
        if hits:
            return self._result(
                score,
                f"Found {len(hits)} hedging phrase(s) suggesting low confidence.",
                hedges=hits,
            )
        return self._result(1.0, "No hedging detected.")


class RefusalEvaluator(Evaluator):
    """Flags refusals. A refusal is not always bad, but it is worth surfacing."""

    name = "refusal"
    fail_threshold = 0.5

    def evaluate(self, item: EvalInput) -> EvalResult:
        text = item.output.lower()
        for phrase in _REFUSALS:
            if phrase in text:
                return self._result(
                    0.0, "Response appears to be a refusal.", phrase=phrase
                )
        return self._result(1.0, "No refusal detected.")


class RepetitionEvaluator(Evaluator):
    """Catches degenerate, looping output (a common failure of runaway agents)."""

    name = "repetition"

    def evaluate(self, item: EvalInput) -> EvalResult:
        ratio = repetition_ratio(item.output)
        score = 1.0 - ratio
        return self._result(
            score,
            f"Token repetition ratio {ratio:.2f}.",
            repetition_ratio=round(ratio, 4),
        )


class EmptyOutputEvaluator(Evaluator):
    """Flags empty or near-empty completions."""

    name = "non_empty"
    fail_threshold = 0.5

    def evaluate(self, item: EvalInput) -> EvalResult:
        n = len(tokenize(item.output))
        if n == 0:
            return self._result(0.0, "Output is empty.")
        if n < 3:
            return self._result(0.3, "Output is suspiciously short.", tokens=n)
        return self._result(1.0, "Output has substantive content.", tokens=n)


class ContextGroundednessEvaluator(Evaluator):
    """For RAG: measures how much of the answer is supported by retrieved context.

    Low overlap between answer and provided context is a strong, cheap signal of
    hallucination. Only meaningful when ``item.context`` is provided.
    """

    name = "groundedness"

    def evaluate(self, item: EvalInput) -> EvalResult:
        if not item.context:
            return self._result(
                1.0, "No context provided; groundedness not applicable."
            )
        joined = "\n".join(item.context)
        overlap = cosine_bow(item.output, joined)
        return self._result(
            overlap,
            f"Answer/context bag-of-words similarity {overlap:.2f}.",
            similarity=round(overlap, 4),
        )


class FactualityRegexEvaluator(Evaluator):
    """Very light factuality smell-test: flags fabricated-looking citations and
    impossible dates. Not a replacement for a real fact checker - a tripwire."""

    name = "factuality_smoke"
    fail_threshold = 0.3
    _FAKE_URL = re.compile(r"https?://(?:example\.com|fake|placeholder)")
    _BAD_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")

    def evaluate(self, item: EvalInput) -> EvalResult:
        problems = []
        if self._FAKE_URL.search(item.output):
            problems.append("placeholder/fabricated URL")
        for match in self._BAD_YEAR.findall(item.output):
            if int(match) > 2100:
                problems.append(f"implausible year {match}")
        score = 1.0 if not problems else max(0.0, 1.0 - 0.5 * len(problems))
        explanation = (
            "No obvious fabrications." if not problems else "; ".join(problems)
        )
        return self._result(score, explanation, problems=problems)
