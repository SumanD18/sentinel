"""Core data structures for Sentinel traces and spans.

These types are intentionally dependency-free (stdlib only) so the SDK stays
lightweight and safe to import into any process. Everything serializes to plain
JSON-compatible dicts via ``to_dict`` for transport to the collector.
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


def _new_id() -> str:
    """Generate a compact, URL-safe, time-sortable identifier."""
    return uuid.uuid4().hex


def _now_ns() -> int:
    """Wall-clock timestamp in nanoseconds (epoch)."""
    return time.time_ns()


class SpanKind(str, enum.Enum):
    """The category of work a span represents.

    Mirrors the kinds of nodes you see in an agent run so the dashboard can
    pick the right icon and aggregation strategy.
    """

    LLM = "llm"
    TOOL = "tool"
    RETRIEVAL = "retrieval"
    AGENT = "agent"
    CHAIN = "chain"
    EMBEDDING = "embedding"
    GUARDRAIL = "guardrail"
    FUNCTION = "function"
    UNKNOWN = "unknown"


class SpanStatus(str, enum.Enum):
    """Terminal status of a span."""

    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


@dataclass
class TokenUsage:
    """Token accounting for an LLM call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def __post_init__(self) -> None:
        # Some providers omit the total; derive it when we can.
        if not self.total_tokens:
            self.total_tokens = self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class Event:
    """A point-in-time annotation attached to a span (e.g. a stream chunk,
    a tool retry, a guardrail trip)."""

    name: str
    timestamp_ns: int = field(default_factory=_now_ns)
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "timestamp_ns": self.timestamp_ns,
            "attributes": self.attributes,
        }


@dataclass
class Span:
    """A single unit of work within a trace.

    A span has a start and end, may have a parent span, and carries arbitrary
    attributes. LLM spans additionally carry model/usage/cost information.
    """

    name: str
    kind: SpanKind = SpanKind.UNKNOWN
    trace_id: str = field(default_factory=_new_id)
    span_id: str = field(default_factory=_new_id)
    parent_span_id: str | None = None

    start_time_ns: int = field(default_factory=_now_ns)
    end_time_ns: int | None = None

    status: SpanStatus = SpanStatus.UNSET
    status_message: str | None = None

    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)

    # LLM-specific (populated by wrappers when kind == LLM)
    model: str | None = None
    provider: str | None = None
    usage: TokenUsage | None = None
    cost_usd: float | None = None

    # Free-form input/output payloads (prompt/response/tool args/results).
    input: Any = None
    output: Any = None

    def add_event(self, name: str, **attributes: Any) -> None:
        self.events.append(Event(name=name, attributes=attributes))

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def record_exception(self, exc: BaseException) -> None:
        self.status = SpanStatus.ERROR
        self.status_message = f"{type(exc).__name__}: {exc}"
        self.add_event(
            "exception",
            exception_type=type(exc).__name__,
            exception_message=str(exc),
        )

    def end(self) -> None:
        if self.end_time_ns is None:
            self.end_time_ns = _now_ns()
        if self.status is SpanStatus.UNSET:
            self.status = SpanStatus.OK

    @property
    def duration_ms(self) -> float | None:
        if self.end_time_ns is None:
            return None
        return (self.end_time_ns - self.start_time_ns) / 1_000_000

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind.value,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "start_time_ns": self.start_time_ns,
            "end_time_ns": self.end_time_ns,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "status_message": self.status_message,
            "attributes": self.attributes,
            "events": [e.to_dict() for e in self.events],
            "model": self.model,
            "provider": self.provider,
            "usage": self.usage.to_dict() if self.usage else None,
            "cost_usd": self.cost_usd,
            "input": self.input,
            "output": self.output,
        }
