"""Anthropic client instrumentation (sync + async, streaming + non-streaming).

Wraps ``messages.create`` on an Anthropic client instance. Handles the
``stream=True`` iterator form; the higher-level ``messages.stream()`` context
manager is left untouched (it already yields a fully-materialised final message
that users typically log themselves).
"""

from __future__ import annotations

import inspect
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
    inp = safe_getattr(usage, "input_tokens", default=0) or 0
    out = safe_getattr(usage, "output_tokens", default=0) or 0
    return TokenUsage(prompt_tokens=inp, completion_tokens=out)


def _stamp_request(span, kwargs: dict) -> None:
    span.model = kwargs.get("model")
    span.provider = "anthropic"
    span.set_attribute("stream", bool(kwargs.get("stream")))
    for key in ("temperature", "top_p", "max_tokens", "system", "tools", "tool_choice"):
        if key in kwargs and kwargs[key] is not None:
            span.set_attribute(key, to_serializable(kwargs[key]))
    span.input = to_serializable(kwargs.get("messages"))


def _finalize(response: Any, span, tracer: Tracer) -> None:
    span.usage = _extract_usage(response)
    span.set_attribute("stop_reason", safe_getattr(response, "stop_reason"))
    content = safe_getattr(response, "content")
    tracer.set_output(span, to_serializable(content))


class _StreamAccumulator:
    def __init__(self) -> None:
        self.text_parts: list[str] = []
        self.input_tokens = 0
        self.output_tokens = 0
        self.stop_reason: str | None = None
        self.events = 0

    def add(self, event: Any) -> None:
        self.events += 1
        etype = safe_getattr(event, "type")
        if etype == "content_block_delta":
            delta = safe_getattr(event, "delta")
            text = safe_getattr(delta, "text")
            if text:
                self.text_parts.append(text)
        elif etype == "message_start":
            message = safe_getattr(event, "message")
            usage = _extract_usage(message)
            if usage:
                self.input_tokens = usage.prompt_tokens
        elif etype == "message_delta":
            usage = safe_getattr(event, "usage")
            if usage is not None:
                self.output_tokens = safe_getattr(usage, "output_tokens", default=0) or 0
            delta = safe_getattr(event, "delta")
            reason = safe_getattr(delta, "stop_reason")
            if reason:
                self.stop_reason = reason

    def finalize(self, span, tracer: Tracer) -> None:
        span.set_attribute("stream_events", self.events)
        if self.stop_reason:
            span.set_attribute("stop_reason", self.stop_reason)
        span.usage = TokenUsage(
            prompt_tokens=self.input_tokens, completion_tokens=self.output_tokens
        )
        tracer.set_output(span, "".join(self.text_parts))


def _wrap_sync_stream(stream: Any, span, tracer: Tracer):
    acc = _StreamAccumulator()

    def generator():
        try:
            for event in stream:
                acc.add(event)
                yield event
        except BaseException as exc:
            span.record_exception(exc)
            raise
        finally:
            acc.finalize(span, tracer)
            tracer.end_span(span)

    return generator()


def _wrap_async_stream(stream: Any, span, tracer: Tracer):
    acc = _StreamAccumulator()

    async def generator():
        try:
            async for event in stream:
                acc.add(event)
                yield event
        except BaseException as exc:
            span.record_exception(exc)
            raise
        finally:
            acc.finalize(span, tracer)
            tracer.end_span(span)

    return generator()


def _instrument_messages_create(tracer: Tracer, original):
    is_async = inspect.iscoroutinefunction(original)

    if is_async:

        async def async_create(*args: Any, **kwargs: Any):
            span = tracer.start_span("anthropic.messages", SpanKind.LLM)
            _stamp_request(span, kwargs)
            try:
                result = await original(*args, **kwargs)
            except BaseException as exc:
                span.record_exception(exc)
                tracer.end_span(span)
                raise
            if kwargs.get("stream"):
                return _wrap_async_stream(result, span, tracer)
            _finalize(result, span, tracer)
            tracer.end_span(span)
            return result

        return async_create

    def sync_create(*args: Any, **kwargs: Any):
        span = tracer.start_span("anthropic.messages", SpanKind.LLM)
        _stamp_request(span, kwargs)
        try:
            result = original(*args, **kwargs)
        except BaseException as exc:
            span.record_exception(exc)
            tracer.end_span(span)
            raise
        if kwargs.get("stream"):
            return _wrap_sync_stream(result, span, tracer)
        _finalize(result, span, tracer)
        tracer.end_span(span)
        return result

    return sync_create


def instrument(client: Any, tracer: Tracer) -> Any:
    """Patch a sync or async Anthropic client in place."""
    ok = patch_method(
        client,
        "messages.create",
        lambda original: _instrument_messages_create(tracer, original),
    )
    if not ok:
        logger.warning(
            "sentinel: could not find messages.create on Anthropic client; "
            "is this a supported client version?"
        )
    return client
