"""Shared test fixtures: an in-memory exporter and fake provider clients."""

from __future__ import annotations

import types
from typing import Any

import pytest

from sentinel.config import SentinelConfig
from sentinel.exporter import Exporter
from sentinel.tracer import Tracer
from sentinel.types import Span


class MemoryExporter(Exporter):
    """Captures exported spans in a list for assertions."""

    def __init__(self) -> None:
        self.spans: list[Span] = []

    def export(self, span: Span) -> None:
        self.spans.append(span)

    def by_name(self, name: str) -> list[Span]:
        return [s for s in self.spans if s.name == name]


@pytest.fixture
def exporter() -> MemoryExporter:
    return MemoryExporter()


@pytest.fixture
def tracer(exporter: MemoryExporter) -> Tracer:
    cfg = SentinelConfig(enabled=True, redact_pii=False, fail_silently=False)
    return Tracer(cfg, exporter=exporter)


# --- Fake OpenAI client -----------------------------------------------------


class _Obj:
    """Tiny attribute bag that mimics a pydantic-ish response object."""

    def __init__(self, **kw: Any) -> None:
        self.__dict__.update(kw)

    def model_dump(self) -> dict:
        return {k: _dump(v) for k, v in self.__dict__.items()}


def _dump(v: Any) -> Any:
    if isinstance(v, _Obj):
        return v.model_dump()
    if isinstance(v, list):
        return [_dump(x) for x in v]
    return v


def make_chat_response(content: str = "hello") -> _Obj:
    return _Obj(
        choices=[
            _Obj(
                index=0,
                finish_reason="stop",
                message=_Obj(role="assistant", content=content),
            )
        ],
        usage=_Obj(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


def make_chat_stream(text: str = "hello"):
    for ch in text:
        yield _Obj(choices=[_Obj(index=0, delta=_Obj(content=ch), finish_reason=None)])
    yield _Obj(
        choices=[_Obj(index=0, delta=_Obj(content=None), finish_reason="stop")],
        usage=_Obj(prompt_tokens=10, completion_tokens=len(text), total_tokens=10 + len(text)),
    )


class OpenAI:  # name matches real client so provider detection works
    """Minimal fake mirroring the OpenAI v1 client surface used by the wrapper."""

    def __init__(self) -> None:
        def create(**kwargs: Any):
            if kwargs.get("stream"):
                return make_chat_stream("hi")
            return make_chat_response()

        def embed(**kwargs: Any):
            return _Obj(
                data=[_Obj(embedding=[0.1, 0.2, 0.3])],
                usage=_Obj(prompt_tokens=4, completion_tokens=0, total_tokens=4),
            )

        self.chat = types.SimpleNamespace(
            completions=types.SimpleNamespace(create=create)
        )
        self.embeddings = types.SimpleNamespace(create=embed)


@pytest.fixture
def fake_openai() -> OpenAI:
    return OpenAI()


# --- Fake async OpenAI client ----------------------------------------------


async def make_async_chat_stream(text: str = "hi"):
    for ch in text:
        yield _Obj(choices=[_Obj(index=0, delta=_Obj(content=ch), finish_reason=None)])
    yield _Obj(
        choices=[_Obj(index=0, delta=_Obj(content=None), finish_reason="stop")],
        usage=_Obj(prompt_tokens=10, completion_tokens=len(text), total_tokens=10 + len(text)),
    )


class AsyncOpenAI:
    """Minimal fake async OpenAI client."""

    def __init__(self) -> None:
        async def create(**kwargs: Any):
            if kwargs.get("stream"):
                return make_async_chat_stream("hi")
            return make_chat_response()

        async def embed(**kwargs: Any):
            return _Obj(
                data=[_Obj(embedding=[0.1, 0.2])],
                usage=_Obj(prompt_tokens=4, completion_tokens=0, total_tokens=4),
            )

        self.chat = types.SimpleNamespace(
            completions=types.SimpleNamespace(create=create)
        )
        self.embeddings = types.SimpleNamespace(create=embed)


@pytest.fixture
def fake_async_openai() -> AsyncOpenAI:
    return AsyncOpenAI()


# --- Fake Anthropic clients -------------------------------------------------


def make_message(text: str = "Hello there.") -> _Obj:
    return _Obj(
        content=[_Obj(type="text", text=text)],
        usage=_Obj(input_tokens=12, output_tokens=7),
        stop_reason="end_turn",
    )


def make_anthropic_stream(text: str = "hi"):
    yield _Obj(type="message_start", message=_Obj(usage=_Obj(input_tokens=12, output_tokens=0)))
    for ch in text:
        yield _Obj(type="content_block_delta", delta=_Obj(type="text_delta", text=ch))
    yield _Obj(
        type="message_delta",
        delta=_Obj(stop_reason="end_turn"),
        usage=_Obj(output_tokens=len(text)),
    )


async def make_anthropic_astream(text: str = "hi"):
    for event in make_anthropic_stream(text):
        yield event


class Anthropic:  # name matches real client for provider detection
    """Minimal fake mirroring the Anthropic Messages API used by the wrapper."""

    def __init__(self) -> None:
        def create(**kwargs: Any):
            if kwargs.get("stream"):
                return make_anthropic_stream("hi")
            return make_message()

        self.messages = types.SimpleNamespace(create=create)


class AsyncAnthropic:
    def __init__(self) -> None:
        async def create(**kwargs: Any):
            if kwargs.get("stream"):
                return make_anthropic_astream("hi")
            return make_message()

        self.messages = types.SimpleNamespace(create=create)


@pytest.fixture
def fake_anthropic() -> Anthropic:
    return Anthropic()


@pytest.fixture
def fake_async_anthropic() -> AsyncAnthropic:
    return AsyncAnthropic()
