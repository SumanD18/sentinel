"""OpenTelemetry exporter tests (skipped if opentelemetry-sdk isn't installed)."""

from __future__ import annotations

import pytest

pytest.importorskip("opentelemetry.sdk.trace")

from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter,
)
from opentelemetry.trace import SpanKind as OTelSpanKind  # noqa: E402
from opentelemetry.trace.status import StatusCode  # noqa: E402

from sentinel.exporters import OTelExporter  # noqa: E402
from sentinel.types import Span, SpanKind, SpanStatus, TokenUsage  # noqa: E402


def _llm_span() -> Span:
    span = Span(name="openai.chat.completions", kind=SpanKind.LLM)
    span.model = "gpt-4o"
    span.provider = "openai"
    span.usage = TokenUsage(prompt_tokens=10, completion_tokens=5)
    span.cost_usd = 0.001
    span.trust_score = 0.9
    span.set_attribute("stream", True)
    span.end()
    return span


def test_otel_exporter_maps_genai_attributes():
    mem = InMemorySpanExporter()
    exp = OTelExporter(mem, service_name="test-svc")
    span = _llm_span()
    exp.export(span)
    exp.flush()

    finished = mem.get_finished_spans()
    assert len(finished) == 1
    o = finished[0]
    assert o.name == "openai.chat.completions"
    assert o.kind is OTelSpanKind.CLIENT
    assert o.attributes["gen_ai.system"] == "openai"
    assert o.attributes["gen_ai.request.model"] == "gpt-4o"
    assert o.attributes["gen_ai.usage.total_tokens"] == 15
    assert o.attributes["sentinel.cost_usd"] == 0.001
    assert o.attributes["sentinel.trust_score"] == 0.9
    assert o.attributes["sentinel.stream"] is True
    assert o.status.status_code is StatusCode.OK
    # Trace id is preserved (uuid4 hex == 128-bit OTel trace id).
    assert format(o.context.trace_id, "032x") == span.trace_id[:32]


def test_otel_exporter_preserves_parent_and_error():
    mem = InMemorySpanExporter()
    exp = OTelExporter(mem)
    parent = Span(name="agent", kind=SpanKind.AGENT)
    child = Span(name="tool", kind=SpanKind.TOOL)
    child.trace_id = parent.trace_id
    child.parent_span_id = parent.span_id
    child.status = SpanStatus.ERROR
    child.status_message = "boom"
    child.end()
    exp.export(child)
    exp.flush()

    o = mem.get_finished_spans()[0]
    assert o.parent is not None
    assert format(o.parent.span_id, "016x") == parent.span_id[:16]
    assert o.status.status_code is StatusCode.ERROR


def test_multi_exporter_fans_out():
    from sentinel.exporter import MultiExporter

    class _Capture:
        def __init__(self):
            self.spans = []

        def export(self, span):
            self.spans.append(span)

        def flush(self, timeout=None):
            return True

        def shutdown(self):
            pass

    a, b = _Capture(), _Capture()
    multi = MultiExporter(a, b)
    multi.export(_llm_span())
    assert len(a.spans) == 1 and len(b.spans) == 1
