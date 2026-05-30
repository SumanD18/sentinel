"""Prometheus metrics.

A handful of counters/histograms exported at ``/metrics`` so Sentinel itself is
observable and can feed Grafana dashboards alongside your app metrics.
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

SPANS_INGESTED = Counter(
    "sentinel_spans_ingested_total",
    "Total spans ingested.",
    ["kind", "provider"],
)
LLM_TOKENS = Counter(
    "sentinel_llm_tokens_total",
    "Total LLM tokens observed.",
    ["model", "type"],  # type = prompt | completion
)
ALERTS = Counter(
    "sentinel_alerts_total",
    "Alerts raised.",
    ["severity"],
)
TRUST_SCORE = Histogram(
    "sentinel_trust_score",
    "Distribution of computed trust scores.",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)
SPAN_LATENCY = Histogram(
    "sentinel_span_latency_ms",
    "Span durations in milliseconds.",
    ["kind"],
    buckets=(10, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000),
)


def record_span(span_in) -> None:
    provider = span_in.provider or "none"
    SPANS_INGESTED.labels(kind=span_in.kind, provider=provider).inc()
    if span_in.duration_ms is not None:
        SPAN_LATENCY.labels(kind=span_in.kind).observe(span_in.duration_ms)
    if span_in.usage and span_in.model:
        LLM_TOKENS.labels(model=span_in.model, type="prompt").inc(
            span_in.usage.prompt_tokens
        )
        LLM_TOKENS.labels(model=span_in.model, type="completion").inc(
            span_in.usage.completion_tokens
        )


def record_alert(severity: str) -> None:
    ALERTS.labels(severity=severity).inc()


def record_trust(score: float) -> None:
    TRUST_SCORE.observe(score)


def render() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
