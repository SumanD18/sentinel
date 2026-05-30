"""Lightweight, dependency-free PII redaction for trace payloads.

This runs *before* data leaves the process, so sensitive values never reach the
collector or logs. It is regex-based and deliberately conservative - it favours
not corrupting payloads over catching every possible PII shape. For stronger
guarantees, plug a custom redactor via the SDK config.
"""

from __future__ import annotations

import re
from re import Pattern
from typing import Any, Callable

# (label, compiled pattern) pairs. Order matters: more specific first.
_PATTERNS: list[tuple[str, Pattern[str]]] = [
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")),
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ \-]*?){13,19}\b")),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    (
        "PHONE",
        re.compile(r"\b(?:\+?\d{1,3}[ \-.]?)?(?:\(?\d{3}\)?[ \-.]?)\d{3}[ \-.]?\d{4}\b"),
    ),
    ("IPV4", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    # Common secret shapes: provider API keys / bearer tokens.
    ("API_KEY", re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9]{16,}\b")),
    ("BEARER", re.compile(r"Bearer\s+[A-Za-z0-9._\-]{12,}")),
]

Redactor = Callable[[str], str]


def redact_text(text: str) -> str:
    """Replace recognised PII spans in a string with ``[REDACTED:LABEL]``."""
    for label, pattern in _PATTERNS:
        text = pattern.sub(f"[REDACTED:{label}]", text)
    return text


def redact_value(value: Any, redactor: Redactor = redact_text) -> Any:
    """Recursively redact strings inside arbitrary JSON-like structures.

    Non-string scalars are returned untouched. The structure is never mutated in
    place; a redacted copy is returned.
    """
    if isinstance(value, str):
        return redactor(value)
    if isinstance(value, dict):
        return {k: redact_value(v, redactor) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_value(v, redactor) for v in value]
    return value
