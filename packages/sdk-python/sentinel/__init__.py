"""Sentinel SDK - drop-in observability and trust layer for AI pipelines.

Quickstart::

    import sentinel
    from openai import OpenAI

    sentinel.init(service_name="my-agent")
    client = sentinel.wrap(OpenAI())

    # use `client` exactly as before - every call is now traced
    client.chat.completions.create(model="gpt-4o", messages=[...])

Everything is safe to call before :func:`init`; until then the SDK behaves as a
no-op so importing it never changes application behaviour.
"""

from __future__ import annotations

import atexit
import logging
import threading
from typing import Any

from .config import SentinelConfig
from .decorators import trace
from .tracer import Tracer
from .types import Event, Span, SpanKind, SpanStatus, TokenUsage

__all__ = [
    "init",
    "get_tracer",
    "wrap",
    "span",
    "trace",
    "flush",
    "shutdown",
    "SentinelConfig",
    "Tracer",
    "Span",
    "SpanKind",
    "SpanStatus",
    "TokenUsage",
    "Event",
]

__version__ = "0.1.0"

logger = logging.getLogger("sentinel")

_default_tracer: Tracer | None = None
_lock = threading.Lock()


def init(
    config: SentinelConfig | None = None,
    **kwargs: Any,
) -> Tracer:
    """Initialise the process-global tracer.

    Pass a :class:`SentinelConfig` or individual keyword overrides (e.g.
    ``endpoint``, ``service_name``, ``api_key``). Safe to call more than once;
    the previous tracer is shut down cleanly first.
    """
    global _default_tracer
    with _lock:
        if config is None:
            config = SentinelConfig.from_env(**kwargs)
        elif kwargs:
            for key, value in kwargs.items():
                setattr(config, key, value)

        if _default_tracer is not None:
            _default_tracer.shutdown()
        _default_tracer = Tracer(config)
        logger.debug(
            "sentinel initialised: service=%s endpoint=%s enabled=%s",
            config.service_name,
            config.endpoint,
            config.enabled,
        )
        return _default_tracer


def get_tracer() -> Tracer:
    """Return the global tracer, lazily creating a default one if needed."""
    global _default_tracer
    if _default_tracer is None:
        with _lock:
            if _default_tracer is None:
                _default_tracer = Tracer()
    return _default_tracer


def span(name: str, kind: Any = SpanKind.UNKNOWN, **kwargs: Any):
    """Open a span on the global tracer (context manager)."""
    resolved = kind if isinstance(kind, SpanKind) else SpanKind(str(kind).lower())
    return get_tracer().span(name, resolved, **kwargs)


def wrap(client: Any, **kwargs: Any) -> Any:
    """Instrument a supported LLM client in place and return it.

    The concrete provider is detected from the client's type so callers don't
    have to import provider-specific helpers. Supported today: OpenAI (sync &
    async) and Anthropic (sync & async). Unsupported clients raise
    :class:`TypeError` so misuse is caught early.
    """
    from .wrappers import wrap_client

    return wrap_client(client, get_tracer(), **kwargs)


def flush(timeout: float | None = None) -> bool:
    """Block until queued spans are exported (or timeout elapses)."""
    return get_tracer().flush(timeout)


def shutdown() -> None:
    """Flush and tear down the global tracer."""
    global _default_tracer
    if _default_tracer is not None:
        _default_tracer.shutdown()
        _default_tracer = None


@atexit.register
def _shutdown_at_exit() -> None:  # pragma: no cover - exercised at interpreter exit
    try:
        shutdown()
    except Exception:
        pass
