"""Decorators for instrumenting plain functions and tools.

These let users trace business logic and custom tools without manually opening
spans::

    @sentinel.trace(kind="tool", name="search_web")
    def search_web(query: str) -> list[str]:
        ...
"""

from __future__ import annotations

import functools
import inspect
from typing import Any, Callable, TypeVar

from .types import SpanKind

F = TypeVar("F", bound=Callable[..., Any])


def _coerce_kind(kind: Any) -> SpanKind:
    if isinstance(kind, SpanKind):
        return kind
    try:
        return SpanKind(str(kind).lower())
    except ValueError:
        return SpanKind.FUNCTION


def trace(
    _fn: F | None = None,
    *,
    name: str | None = None,
    kind: Any = SpanKind.FUNCTION,
    capture_args: bool = True,
) -> Any:
    """Wrap a sync or async function in a span.

    Works as ``@trace`` or ``@trace(name=..., kind=...)``. Arguments and the
    return value are captured as the span input/output unless ``capture_args``
    is False.
    """
    span_kind = _coerce_kind(kind)

    def decorator(fn: F) -> F:
        span_name = name or fn.__qualname__

        def _build_input(args: tuple, kwargs: dict) -> Any:
            if not capture_args:
                return None
            return {"args": list(args), "kwargs": kwargs}

        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                from . import get_tracer

                tracer = get_tracer()
                with tracer.span(
                    span_name, span_kind, input=_build_input(args, kwargs)
                ) as span:
                    result = await fn(*args, **kwargs)
                    tracer.set_output(span, result)
                    return result

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            from . import get_tracer

            tracer = get_tracer()
            with tracer.span(
                span_name, span_kind, input=_build_input(args, kwargs)
            ) as span:
                result = fn(*args, **kwargs)
                tracer.set_output(span, result)
                return result

        return sync_wrapper  # type: ignore[return-value]

    if _fn is not None:
        return decorator(_fn)
    return decorator
