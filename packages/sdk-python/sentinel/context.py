"""Context propagation for nested spans.

Uses :mod:`contextvars` so that span nesting works correctly under threads,
asyncio tasks, and concurrent agent steps without callers having to thread a
context object through every function.
"""

from __future__ import annotations

import contextvars

from .types import Span

# The span currently "in scope". Child spans read this to set their parent.
_current_span: contextvars.ContextVar[Span | None] = contextvars.ContextVar(
    "sentinel_current_span", default=None
)


def get_current_span() -> Span | None:
    return _current_span.get()


def set_current_span(span: Span | None) -> contextvars.Token:
    """Set the active span, returning a token usable to restore the previous one."""
    return _current_span.set(span)


def reset_current_span(token: contextvars.Token) -> None:
    _current_span.reset(token)


def current_trace_id() -> str | None:
    span = _current_span.get()
    return span.trace_id if span else None
