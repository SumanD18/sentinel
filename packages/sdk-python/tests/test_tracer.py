"""Tracer, context propagation, and span lifecycle tests."""

from __future__ import annotations

import pytest

from sentinel.types import SpanKind, SpanStatus


def test_span_records_timing_and_status(tracer, exporter):
    with tracer.span("work", SpanKind.FUNCTION) as span:
        span.set_attribute("k", "v")
    assert len(exporter.spans) == 1
    out = exporter.spans[0]
    assert out.status is SpanStatus.OK
    assert out.duration_ms is not None and out.duration_ms >= 0
    assert out.attributes["k"] == "v"


def test_nested_spans_share_trace_and_link_parent(tracer, exporter):
    with tracer.span("parent", SpanKind.AGENT) as parent:
        with tracer.span("child", SpanKind.TOOL) as child:
            assert child.trace_id == parent.trace_id
            assert child.parent_span_id == parent.span_id
    # Children export before parents (closed inner-first).
    names = [s.name for s in exporter.spans]
    assert names == ["child", "parent"]


def test_exception_is_recorded_and_reraised(tracer, exporter):
    with pytest.raises(ValueError):
        with tracer.span("boom", SpanKind.FUNCTION):
            raise ValueError("nope")
    span = exporter.spans[0]
    assert span.status is SpanStatus.ERROR
    assert "ValueError" in span.status_message
    assert any(e.name == "exception" for e in span.events)


def test_sampling_zero_drops_all(exporter):
    from sentinel.config import SentinelConfig
    from sentinel.tracer import Tracer

    tracer = Tracer(SentinelConfig(sample_rate=0.0), exporter=exporter)
    with tracer.span("x"):
        pass
    assert exporter.spans == []


def test_decorator_traces_sync_function(tracer, exporter, monkeypatch):
    import sentinel

    monkeypatch.setattr(sentinel, "_default_tracer", tracer)

    @sentinel.trace(kind="tool", name="add")
    def add(a, b):
        return a + b

    assert add(2, 3) == 5
    span = exporter.by_name("add")[0]
    assert span.kind is SpanKind.TOOL
    assert span.output == 5


@pytest.mark.asyncio
async def test_decorator_traces_async_function(tracer, exporter, monkeypatch):
    import sentinel

    monkeypatch.setattr(sentinel, "_default_tracer", tracer)

    @sentinel.trace(name="fetch")
    async def fetch():
        return "ok"

    assert await fetch() == "ok"
    assert exporter.by_name("fetch")[0].output == "ok"
