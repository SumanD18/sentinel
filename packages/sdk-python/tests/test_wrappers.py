"""Provider wrapper tests against fake OpenAI clients."""

from __future__ import annotations

from sentinel.types import SpanKind, SpanStatus
from sentinel.wrappers import openai as openai_wrapper


def test_wrap_chat_completion_captures_usage_and_cost(tracer, exporter, fake_openai):
    client = openai_wrapper.instrument(fake_openai, tracer)
    resp = client.chat.completions.create(
        model="gpt-4o", messages=[{"role": "user", "content": "hi"}]
    )
    assert resp is not None
    span = exporter.by_name("openai.chat.completions")[0]
    assert span.kind is SpanKind.LLM
    assert span.model == "gpt-4o"
    assert span.usage.total_tokens == 15
    # gpt-4o priced at 0.0025/0.01 per 1k -> 10/1000*.0025 + 5/1000*.01
    assert span.cost_usd is not None and span.cost_usd > 0
    assert span.status is SpanStatus.OK


def test_wrap_streaming_accumulates_content(tracer, exporter, fake_openai):
    client = openai_wrapper.instrument(fake_openai, tracer)
    stream = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "hi"}],
        stream=True,
    )
    chunks = list(stream)
    assert len(chunks) > 0
    span = exporter.by_name("openai.chat.completions")[0]
    assert span.output == "hi"
    assert span.attributes["stream"] is True
    assert span.attributes["finish_reason"] == "stop"
    assert span.usage.completion_tokens == 2


def test_wrap_embeddings(tracer, exporter, fake_openai):
    client = openai_wrapper.instrument(fake_openai, tracer)
    client.embeddings.create(model="text-embedding-3-small", input="hello")
    span = exporter.by_name("openai.embeddings")[0]
    assert span.kind is SpanKind.EMBEDDING
    assert span.attributes["vector_count"] == 1


def test_double_wrap_is_idempotent(tracer, fake_openai):
    once = openai_wrapper.instrument(fake_openai, tracer)
    twice = openai_wrapper.instrument(once, tracer)
    create = twice.chat.completions.create
    assert getattr(create, "__sentinel_wrapped__", False) is True


def test_dispatch_rejects_unknown_client(tracer):
    from sentinel.wrappers import wrap_client

    class WeirdClient:
        pass

    try:
        wrap_client(WeirdClient(), tracer)
    except TypeError as exc:
        assert "does not support" in str(exc)
    else:
        raise AssertionError("expected TypeError")
