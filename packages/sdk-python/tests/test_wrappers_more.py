"""Coverage for the Anthropic wrapper and async OpenAI paths."""

from __future__ import annotations

import pytest

from sentinel.types import SpanKind, SpanStatus
from sentinel.wrappers import anthropic as anthropic_wrapper
from sentinel.wrappers import openai as openai_wrapper

# --- Anthropic --------------------------------------------------------------


def test_anthropic_messages_captures_usage_and_cost(tracer, exporter, fake_anthropic):
    client = anthropic_wrapper.instrument(fake_anthropic, tracer)
    client.messages.create(
        model="claude-3-5-sonnet", max_tokens=64, messages=[{"role": "user", "content": "hi"}]
    )
    span = exporter.by_name("anthropic.messages")[0]
    assert span.kind is SpanKind.LLM
    assert span.provider == "anthropic"
    assert span.usage.prompt_tokens == 12
    assert span.usage.completion_tokens == 7
    assert span.cost_usd is not None and span.cost_usd > 0
    assert span.attributes["stop_reason"] == "end_turn"
    assert span.status is SpanStatus.OK


def test_anthropic_streaming_accumulates_text(tracer, exporter, fake_anthropic):
    client = anthropic_wrapper.instrument(fake_anthropic, tracer)
    stream = client.messages.create(
        model="claude-3-5-haiku",
        max_tokens=64,
        stream=True,
        messages=[{"role": "user", "content": "hi"}],
    )
    events = list(stream)
    assert len(events) > 0
    span = exporter.by_name("anthropic.messages")[0]
    assert span.output == "hi"
    assert span.usage.prompt_tokens == 12
    assert span.usage.completion_tokens == 2
    assert span.attributes["stop_reason"] == "end_turn"


@pytest.mark.asyncio
async def test_anthropic_async_messages(tracer, exporter, fake_async_anthropic):
    client = anthropic_wrapper.instrument(fake_async_anthropic, tracer)
    await client.messages.create(
        model="claude-3-opus", max_tokens=64, messages=[{"role": "user", "content": "hi"}]
    )
    span = exporter.by_name("anthropic.messages")[0]
    assert span.usage.completion_tokens == 7


def test_anthropic_records_exception(tracer, exporter, fake_anthropic):
    def boom(**kwargs):
        raise RuntimeError("api down")

    fake_anthropic.messages.create = boom
    client = anthropic_wrapper.instrument(fake_anthropic, tracer)
    with pytest.raises(RuntimeError):
        client.messages.create(model="claude-3-haiku", messages=[])
    span = exporter.by_name("anthropic.messages")[0]
    assert span.status is SpanStatus.ERROR
    assert "RuntimeError" in span.status_message


# --- Async OpenAI -----------------------------------------------------------


@pytest.mark.asyncio
async def test_openai_async_chat(tracer, exporter, fake_async_openai):
    client = openai_wrapper.instrument(fake_async_openai, tracer)
    await client.chat.completions.create(
        model="gpt-4o", messages=[{"role": "user", "content": "hi"}]
    )
    span = exporter.by_name("openai.chat.completions")[0]
    assert span.usage.total_tokens == 15
    assert span.cost_usd is not None


@pytest.mark.asyncio
async def test_openai_async_streaming(tracer, exporter, fake_async_openai):
    client = openai_wrapper.instrument(fake_async_openai, tracer)
    stream = await client.chat.completions.create(
        model="gpt-4o", stream=True, messages=[{"role": "user", "content": "hi"}]
    )
    chunks = [c async for c in stream]
    assert len(chunks) > 0
    span = exporter.by_name("openai.chat.completions")[0]
    assert span.output == "hi"
    assert span.attributes["finish_reason"] == "stop"
    assert span.usage.completion_tokens == 2


@pytest.mark.asyncio
async def test_openai_async_embeddings(tracer, exporter, fake_async_openai):
    client = openai_wrapper.instrument(fake_async_openai, tracer)
    await client.embeddings.create(model="text-embedding-3-small", input="hello")
    span = exporter.by_name("openai.embeddings")[0]
    assert span.kind is SpanKind.EMBEDDING
    assert span.attributes["vector_count"] == 1
