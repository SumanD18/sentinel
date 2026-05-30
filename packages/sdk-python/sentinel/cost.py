"""Token cost estimation.

Prices are expressed in USD per 1,000 tokens and are best-effort defaults. They
can be overridden at runtime via :func:`register_pricing` or by passing a custom
table to the SDK config, because provider prices change frequently.

The table is intentionally conservative: when a model is unknown we return
``None`` rather than guessing, so the dashboard can show "unknown" instead of a
misleading number.
"""

from __future__ import annotations

from dataclasses import dataclass

from .types import TokenUsage


@dataclass(frozen=True)
class ModelPrice:
    """Per-1K-token pricing for a model."""

    prompt: float
    completion: float


# Snapshot of common public list prices (USD / 1K tokens). Override as needed.
_DEFAULT_PRICING: dict[str, ModelPrice] = {
    # OpenAI
    "gpt-4o": ModelPrice(0.0025, 0.01),
    "gpt-4o-mini": ModelPrice(0.00015, 0.0006),
    "gpt-4-turbo": ModelPrice(0.01, 0.03),
    "gpt-4": ModelPrice(0.03, 0.06),
    "gpt-3.5-turbo": ModelPrice(0.0005, 0.0015),
    "o1": ModelPrice(0.015, 0.06),
    "o1-mini": ModelPrice(0.003, 0.012),
    "text-embedding-3-small": ModelPrice(0.00002, 0.0),
    "text-embedding-3-large": ModelPrice(0.00013, 0.0),
    # Anthropic
    "claude-3-5-sonnet": ModelPrice(0.003, 0.015),
    "claude-3-5-haiku": ModelPrice(0.0008, 0.004),
    "claude-3-opus": ModelPrice(0.015, 0.075),
    "claude-3-sonnet": ModelPrice(0.003, 0.015),
    "claude-3-haiku": ModelPrice(0.00025, 0.00125),
    # Google
    "gemini-1.5-pro": ModelPrice(0.00125, 0.005),
    "gemini-1.5-flash": ModelPrice(0.000075, 0.0003),
}

_pricing: dict[str, ModelPrice] = dict(_DEFAULT_PRICING)


def register_pricing(model: str, prompt_per_1k: float, completion_per_1k: float) -> None:
    """Add or override pricing for a model (matched by prefix)."""
    _pricing[model] = ModelPrice(prompt_per_1k, completion_per_1k)


def _lookup(model: str) -> ModelPrice | None:
    if model in _pricing:
        return _pricing[model]
    # Fall back to longest matching prefix so dated model ids
    # (e.g. "gpt-4o-2024-08-06") still resolve.
    best: str | None = None
    for known in _pricing:
        if model.startswith(known) and (best is None or len(known) > len(best)):
            best = known
    return _pricing[best] if best else None


def estimate_cost(model: str | None, usage: TokenUsage | None) -> float | None:
    """Estimate USD cost for a call. Returns ``None`` when unknown."""
    if not model or usage is None:
        return None
    price = _lookup(model)
    if price is None:
        return None
    cost = (
        usage.prompt_tokens / 1000.0 * price.prompt
        + usage.completion_tokens / 1000.0 * price.completion
    )
    return round(cost, 8)
