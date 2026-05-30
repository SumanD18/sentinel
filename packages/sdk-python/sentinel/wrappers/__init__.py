"""Provider detection and dispatch for ``sentinel.wrap``."""

from __future__ import annotations

from typing import Any

from ..tracer import Tracer


def _provider_of(client: Any) -> str | None:
    """Identify the provider from the client's class, without importing the
    provider libraries (they may not be installed)."""
    module = type(client).__module__ or ""
    name = type(client).__name__
    root = module.split(".")[0]
    if root == "openai" or name in {"OpenAI", "AsyncOpenAI"}:
        return "openai"
    if root == "anthropic" or name in {"Anthropic", "AsyncAnthropic"}:
        return "anthropic"
    return None


def wrap_client(client: Any, tracer: Tracer, **kwargs: Any) -> Any:
    provider = _provider_of(client)
    if provider == "openai":
        from . import openai as openai_wrapper

        return openai_wrapper.instrument(client, tracer)
    if provider == "anthropic":
        from . import anthropic as anthropic_wrapper

        return anthropic_wrapper.instrument(client, tracer)

    raise TypeError(
        f"sentinel.wrap does not support {type(client).__module__}."
        f"{type(client).__name__!r}. Supported: OpenAI, Anthropic. "
        "For other frameworks, use @sentinel.trace or sentinel.span()."
    )
