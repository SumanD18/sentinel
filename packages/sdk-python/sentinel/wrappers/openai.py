"""OpenAI client instrumentation (sync + async, streaming + non-streaming).

Wraps ``chat.completions.create`` and ``embeddings.create`` on an OpenAI client
instance. Streaming responses are wrapped so token deltas are accumulated and
the span is closed only when the stream is fully consumed.
"""

from __future__ import annotations

import logging
from typing import Any

from ..tracer import Tracer
from ..types import SpanKind, TokenUsage
from ._common import patch_method, safe_getattr, to_serializable

logger = logging.getLogger("sentinel")


def _extract_usage(response: Any) -> TokenUsage | None:
    usage = safe_getattr(response, "usage")
    if usage is None:
        return None
    return TokenUsage(
        prompt_tokens=safe_getattr(usage, "prompt_tokens", default=0) or 0,
        completion_tokens=safe_getattr(usage, "completion_tokens", default=0) or 0,
        total_tokens=safe_getattr(usage, "total_tokens", default=0) or 0,
    )


def _stamp_chat_request(span, kwargs: dict) -> None:
    span.model = kwargs.get("model")
    span.provider = "openai"
    span.set_attribute("stream", bool(kwargs.get("stream")))
    for key in ("temperature", "top_p", "max_tokens", "tools", "tool_choice"):
        if key in kwargs and kwargs[key] is not None:
            span.set_attribute(key, to_serializable(kwargs[key]))
    span.input = to_serializable(kwargs.get("messages"))


class _StreamAccumulator:
    """Collects streamed chat chunks into a final text + tool-call summary."""

    def __init__(self) -> None:
        self.content_parts: list[str] = []
        self.usage: TokenUsage | None = None
        self.finish_reason: str | None = None
        self.chunks = 0

    def add(self, chunk: Any) -> None:
        self.chunks += 1
        choices = safe_getattr(chunk, "choices", default=[]) or []
        for choice in choices:
            delta = safe_getattr(choice, "delta")
            if delta is not None:
                piece = safe_getattr(delta, "content")
                if piece:
                    self.content_parts.append(piece)
            reason = safe_getattr(choice, "finish_reason")
            if reason:
                self.finish_reason = reason
        # Newer OpenAI streams include usage on the final chunk.
        usage = _extract_usage(chunk)
        if usage is not None:
            self.usage = usage

    def finalize(self, span, tracer: Tracer) -> None:
        span.set_attribute("stream_chunks", self.chunks)
        if self.finish_reason:
            span.set_attribute("finish_reason", self.finish_reason)
        if self.usage:
            span.usage = self.usage
        tracer.set_output(span, "".join(self.content_parts))


def _instrument_chat_create(tracer: Tracer, original):
    is_async = _looks_async(original)

    if is_async:

        async def async_create(*args: Any, **kwargs: Any):
            span = tracer.start_span("openai.chat.completions", SpanKind.LLM)
            _stamp_chat_request(span, kwargs)
            try:
                result = await original(*args, **kwargs)
            except BaseException as exc:
                span.record_exception(exc)
                tracer.end_span(span)
                raise
            if kwargs.get("stream"):
                return _wrap_async_stream(result, span, tracer)
            _finalize_chat(result, span, tracer)
            tracer.end_span(span)
            return result

        return async_create

    def sync_create(*args: Any, **kwargs: Any):
        span = tracer.start_span("openai.chat.completions", SpanKind.LLM)
        _stamp_chat_request(span, kwargs)
        try:
            result = original(*args, **kwargs)
        except BaseException as exc:
            span.record_exception(exc)
            tracer.end_span(span)
            raise
        if kwargs.get("stream"):
            return _wrap_sync_stream(result, span, tracer)
        _finalize_chat(result, span, tracer)
        tracer.end_span(span)
        return result

    return sync_create


def _finalize_chat(response: Any, span, tracer: Tracer) -> None:
    span.usage = _extract_usage(response)
    choices = safe_getattr(response, "choices", default=[]) or []
    if choices:
        message = safe_getattr(choices[0], "message")
        span.set_attribute(
            "finish_reason", safe_getattr(choices[0], "finish_reason")
        )
        tracer.set_output(span, to_serializable(message))


def _wrap_sync_stream(stream: Any, span, tracer: Tracer):
    acc = _StreamAccumulator()

    def generator():
        try:
            for chunk in stream:
                acc.add(chunk)
                yield chunk
        except BaseException as exc:
            span.record_exception(exc)
            raise
        finally:
            # Finalization must never prevent the span from being closed and
            # exported, so guard the accumulator step separately.
            try:
                acc.finalize(span, tracer)
            except Exception:  # pragma: no cover - defensive
                logger.exception("sentinel: stream finalize failed")
            tracer.end_span(span)

    return generator()


def _wrap_async_stream(stream: Any, span, tracer: Tracer):
    acc = _StreamAccumulator()

    async def generator():
        try:
            async for chunk in stream:
                acc.add(chunk)
                yield chunk
        except BaseException as exc:
            span.record_exception(exc)
            raise
        finally:
            try:
                acc.finalize(span, tracer)
            except Exception:  # pragma: no cover - defensive
                logger.exception("sentinel: stream finalize failed")
            tracer.end_span(span)

    return generator()


def _instrument_embeddings(tracer: Tracer, original):
    is_async = _looks_async(original)

    def _stamp(span, kwargs):
        span.model = kwargs.get("model")
        span.provider = "openai"
        span.input = to_serializable(kwargs.get("input"))

    if is_async:

        async def async_create(*args: Any, **kwargs: Any):
            with tracer.span("openai.embeddings", SpanKind.EMBEDDING) as span:
                _stamp(span, kwargs)
                result = await original(*args, **kwargs)
                span.usage = _extract_usage(result)
                span.set_attribute(
                    "vector_count", len(safe_getattr(result, "data", default=[]) or [])
                )
                return result

        return async_create

    def sync_create(*args: Any, **kwargs: Any):
        with tracer.span("openai.embeddings", SpanKind.EMBEDDING) as span:
            _stamp(span, kwargs)
            result = original(*args, **kwargs)
            span.usage = _extract_usage(result)
            span.set_attribute(
                "vector_count", len(safe_getattr(result, "data", default=[]) or [])
            )
            return result

    return sync_create


def _looks_async(fn: Any) -> bool:
    import inspect

    return inspect.iscoroutinefunction(fn) or inspect.iscoroutinefunction(
        getattr(fn, "__wrapped__", None)
    )


def instrument(client: Any, tracer: Tracer) -> Any:
    """Patch a sync or async OpenAI client in place."""
    patched_chat = patch_method(
        client,
        "chat.completions.create",
        lambda original: _instrument_chat_create(tracer, original),
    )
    patch_method(
        client,
        "embeddings.create",
        lambda original: _instrument_embeddings(tracer, original),
    )
    if not patched_chat:
        logger.warning(
            "sentinel: could not find chat.completions.create on OpenAI client; "
            "is this a supported client version?"
        )
    return client
