"""ORM models for traces, spans, alerts, and the prompt registry."""

from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Trace(Base):
    """A complete agent/pipeline run: the root of a span tree."""

    __tablename__ = "traces"

    trace_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    service_name: Mapped[str] = mapped_column(String(128), index=True, default="default")
    environment: Mapped[str] = mapped_column(String(64), default="development")
    root_name: Mapped[Optional[str]] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(16), default="ok", index=True)

    start_time_ns: Mapped[int] = mapped_column(Integer)
    end_time_ns: Mapped[Optional[int]] = mapped_column(Integer)
    duration_ms: Mapped[Optional[float]] = mapped_column(Float)

    span_count: Mapped[int] = mapped_column(Integer, default=0)
    llm_call_count: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    # Lowest trust score across the trace's evaluated spans (1.0 = clean).
    min_trust_score: Mapped[float] = mapped_column(Float, default=1.0)
    has_alert: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    spans: Mapped[list["Span"]] = relationship(
        back_populates="trace", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="trace", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_traces_created", "created_at"),)


class Span(Base):
    """A single node in a trace (LLM call, tool, retrieval, etc.)."""

    __tablename__ = "spans"

    span_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trace_id: Mapped[str] = mapped_column(
        ForeignKey("traces.trace_id", ondelete="CASCADE"), index=True
    )
    parent_span_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)

    name: Mapped[str] = mapped_column(String(256))
    kind: Mapped[str] = mapped_column(String(32), default="unknown", index=True)
    status: Mapped[str] = mapped_column(String(16), default="ok")
    status_message: Mapped[Optional[str]] = mapped_column(Text)

    start_time_ns: Mapped[int] = mapped_column(Integer)
    end_time_ns: Mapped[Optional[int]] = mapped_column(Integer)
    duration_ms: Mapped[Optional[float]] = mapped_column(Float)

    model: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    provider: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Optional[float]] = mapped_column(Float)

    input: Mapped[Optional[Any]] = mapped_column(JSON)
    output: Mapped[Optional[Any]] = mapped_column(JSON)
    attributes: Mapped[Optional[Any]] = mapped_column(JSON, default=dict)
    events: Mapped[Optional[Any]] = mapped_column(JSON, default=list)

    # Evaluator output for this span (list of EvalResult dicts) + trust score.
    eval_results: Mapped[Optional[Any]] = mapped_column(JSON)
    trust_score: Mapped[Optional[float]] = mapped_column(Float, index=True)

    trace: Mapped["Trace"] = relationship(back_populates="spans")

    __table_args__ = (Index("ix_spans_trace_start", "trace_id", "start_time_ns"),)


class Alert(Base):
    """A flagged condition: low trust score, guardrail trip, error, runaway loop."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(
        ForeignKey("traces.trace_id", ondelete="CASCADE"), index=True
    )
    span_id: Mapped[Optional[str]] = mapped_column(String(64))
    rule: Mapped[str] = mapped_column(String(128), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="warning", index=True)
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[Optional[Any]] = mapped_column(JSON)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    trace: Mapped["Trace"] = relationship(back_populates="alerts")


class PromptVersion(Base):
    """Git-like versioning for prompts, with per-version aggregate metrics."""

    __tablename__ = "prompt_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    version: Mapped[int] = mapped_column(Integer)
    template: Mapped[str] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    variables: Mapped[Optional[Any]] = mapped_column(JSON, default=list)
    meta: Mapped[Optional[Any]] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_prompt_name_version"),
    )
