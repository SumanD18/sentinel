"""Policy & guardrail engine.

Guardrails are pure functions over a span (plus its evaluation results) that
return zero or more :class:`AlertSpec` objects. Built-ins cover the common cases;
projects can register custom guardrails in Python via :func:`register`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .config import get_settings


@dataclass
class AlertSpec:
    rule: str
    severity: str  # "info" | "warning" | "critical"
    message: str
    span_id: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)


# A guardrail sees the span dict and (optional) eval results + trust score.
Guardrail = Callable[[dict, list[dict], Optional[float]], list[AlertSpec]]

_GUARDRAILS: list[tuple[str, Guardrail]] = []


def register(name: str, fn: Guardrail) -> None:
    _GUARDRAILS.append((name, fn))


def _text_of(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


# --- Built-in guardrails ----------------------------------------------------


def _gr_low_trust(span: dict, evals: list[dict], trust: Optional[float]) -> list[AlertSpec]:
    settings = get_settings()
    if trust is not None and trust <= settings.alert_trust_threshold:
        weakest = min(evals, key=lambda e: e.get("score", 1.0), default=None)
        why = (
            f" Weakest dimension: {weakest['evaluator']} "
            f"({weakest['score']:.2f}) - {weakest['explanation']}"
            if weakest
            else ""
        )
        return [
            AlertSpec(
                rule="low_trust_score",
                severity="warning",
                message=f"Output trust score {trust:.2f} below threshold.{why}",
                span_id=span.get("span_id"),
                details={"trust_score": trust, "evaluators": evals},
            )
        ]
    return []


def _gr_error_span(span: dict, evals: list[dict], trust: Optional[float]) -> list[AlertSpec]:
    if span.get("status") == "error":
        return [
            AlertSpec(
                rule="span_error",
                severity="critical",
                message=span.get("status_message") or "Span ended with an error.",
                span_id=span.get("span_id"),
            )
        ]
    return []


_SECRET_PATTERNS = [
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----")),
    ("api_key", re.compile(r"\b(?:sk|pk)-[A-Za-z0-9]{20,}\b")),
]


def _gr_secret_leak(span: dict, evals: list[dict], trust: Optional[float]) -> list[AlertSpec]:
    haystack = _text_of(span.get("output")) + "\n" + _text_of(span.get("input"))
    for label, pattern in _SECRET_PATTERNS:
        if pattern.search(haystack):
            return [
                AlertSpec(
                    rule="possible_secret_leak",
                    severity="critical",
                    message=f"Potential secret of type '{label}' detected in payload.",
                    span_id=span.get("span_id"),
                    details={"secret_type": label},
                )
            ]
    return []


# Cheap prompt-injection tripwire on retrieved/tool content.
_INJECTION = re.compile(
    r"(ignore (?:all |the )?(?:previous|above) instructions"
    r"|disregard (?:your|the) (?:system )?prompt"
    r"|you are now (?:a|an|in) )",
    re.IGNORECASE,
)


def _gr_prompt_injection(span: dict, evals: list[dict], trust: Optional[float]) -> list[AlertSpec]:
    if span.get("kind") not in {"retrieval", "tool"}:
        return []
    haystack = _text_of(span.get("output"))
    if _INJECTION.search(haystack):
        return [
            AlertSpec(
                rule="prompt_injection_suspected",
                severity="critical",
                message="Possible context-poisoning / prompt-injection text in "
                "retrieved or tool content.",
                span_id=span.get("span_id"),
            )
        ]
    return []


register("low_trust_score", _gr_low_trust)
register("span_error", _gr_error_span)
register("possible_secret_leak", _gr_secret_leak)
register("prompt_injection_suspected", _gr_prompt_injection)


def run_guardrails(
    span: dict, evals: list[dict], trust: Optional[float]
) -> list[AlertSpec]:
    alerts: list[AlertSpec] = []
    for _name, fn in _GUARDRAILS:
        try:
            alerts.extend(fn(span, evals, trust))
        except Exception:
            # A broken custom guardrail must never block ingestion.
            continue
    return alerts
