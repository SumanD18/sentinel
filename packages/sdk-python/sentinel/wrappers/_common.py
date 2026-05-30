"""Shared helpers for provider wrappers.

The wrappers patch *bound methods on a client instance* rather than monkey-
patching the provider library globally. That keeps instrumentation scoped to the
client the user explicitly wrapped and makes it trivial to run instrumented and
uninstrumented clients side by side.
"""

from __future__ import annotations

import functools
from typing import Any, Callable


def patch_method(obj: Any, attr_path: str, factory: Callable[[Callable], Callable]) -> bool:
    """Replace ``obj.<attr_path>`` with ``factory(original)``.

    ``attr_path`` may be dotted (e.g. ``"chat.completions.create"``). Returns
    True if the patch was applied, False if the attribute didn't exist (so the
    wrapper degrades gracefully across provider library versions).

    A sentinel flag prevents double-wrapping if ``wrap`` is called twice.
    """
    parts = attr_path.split(".")
    target = obj
    for part in parts[:-1]:
        target = getattr(target, part, None)
        if target is None:
            return False
    leaf = parts[-1]
    original = getattr(target, leaf, None)
    if original is None:
        return False
    if getattr(original, "__sentinel_wrapped__", False):
        return True

    wrapped = factory(original)
    functools.update_wrapper(wrapped, original)
    wrapped.__sentinel_wrapped__ = True  # type: ignore[attr-defined]
    setattr(target, leaf, wrapped)
    return True


def safe_getattr(obj: Any, *names: str, default: Any = None) -> Any:
    """Return the first attribute or mapping key found among ``names``."""
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def to_serializable(value: Any) -> Any:
    """Best-effort conversion of provider SDK objects to JSON-able structures."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {k: to_serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_serializable(v) for v in value]
    # Pydantic v2 / v1 models, and OpenAI/Anthropic response objects.
    for method in ("model_dump", "dict", "to_dict"):
        fn = getattr(value, method, None)
        if callable(fn):
            try:
                return to_serializable(fn())
            except Exception:
                pass
    if hasattr(value, "__dict__"):
        return {
            k: to_serializable(v)
            for k, v in vars(value).items()
            if not k.startswith("_")
        }
    return str(value)
