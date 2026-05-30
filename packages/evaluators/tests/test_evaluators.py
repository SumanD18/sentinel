from __future__ import annotations

from sentinel_evaluators import EvalInput, aggregate_score, run_suite
from sentinel_evaluators.base import Verdict
from sentinel_evaluators.consistency import SelfConsistencyEvaluator
from sentinel_evaluators.heuristics import (
    ConfidenceEvaluator,
    ContextGroundednessEvaluator,
    EmptyOutputEvaluator,
    FactualityRegexEvaluator,
    RefusalEvaluator,
    RepetitionEvaluator,
)


def test_confidence_flags_hedging():
    r = ConfidenceEvaluator().evaluate(
        EvalInput(output="I'm not sure, but as an AI I might be wrong.")
    )
    assert r.score < 0.7
    assert r.details["hedges"]


def test_confidence_clean_answer():
    r = ConfidenceEvaluator().evaluate(EvalInput(output="The capital of France is Paris."))
    assert r.verdict is Verdict.PASS


def test_refusal_detected():
    r = RefusalEvaluator().evaluate(EvalInput(output="I cannot help with that request."))
    assert r.verdict is Verdict.FAIL


def test_empty_output():
    assert EmptyOutputEvaluator().evaluate(EvalInput(output="")).score == 0.0


def test_groundedness_low_when_answer_ignores_context():
    r = ContextGroundednessEvaluator().evaluate(
        EvalInput(
            output="The Eiffel Tower is in Berlin.",
            context=["Paris is the capital of France and home to the Louvre."],
        )
    )
    assert r.score < 0.5


def test_self_consistency_high_for_agreeing_samples():
    r = SelfConsistencyEvaluator().evaluate(
        EvalInput(
            output="The answer is 42.",
            samples=["The answer is 42.", "It is 42."],
        )
    )
    assert r.score > 0.3


def test_repetition_detects_looping():
    r = RepetitionEvaluator().evaluate(
        EvalInput(output="go go go go go go go go go go")
    )
    assert r.score < 0.5
    assert r.details["repetition_ratio"] > 0.5


def test_repetition_clean_text():
    r = RepetitionEvaluator().evaluate(
        EvalInput(output="The quick brown fox jumps over the lazy dog easily.")
    )
    assert r.score > 0.7


def test_factuality_flags_fabricated_url_and_year():
    r = FactualityRegexEvaluator().evaluate(
        EvalInput(output="See https://example.com/source published in 2750.")
    )
    assert r.score < 1.0
    assert any("URL" in p or "year" in p for p in r.details["problems"])


def test_factuality_clean():
    r = FactualityRegexEvaluator().evaluate(
        EvalInput(output="Water boils at 100 degrees Celsius at sea level.")
    )
    assert r.score == 1.0
    assert r.details["problems"] == []


def test_run_suite_and_aggregate():
    results = run_suite(EvalInput(output="Paris is the capital of France."))
    assert len(results) == len(__import__("sentinel_evaluators").DEFAULT_INLINE_SUITE)
    score = aggregate_score(results)
    assert 0.0 <= score <= 1.0
    assert score > 0.7
