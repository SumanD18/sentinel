"""Pydantic request/response schemas for the API."""

from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# --- Ingestion (matches the SDK exporter payload) ---------------------------


class UsageIn(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class EventIn(BaseModel):
    name: str
    timestamp_ns: int = 0
    attributes: dict[str, Any] = Field(default_factory=dict)


class SpanIn(BaseModel):
    name: str
    kind: str = "unknown"
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    start_time_ns: int
    end_time_ns: Optional[int] = None
    duration_ms: Optional[float] = None
    status: str = "ok"
    status_message: Optional[str] = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    events: list[EventIn] = Field(default_factory=list)
    model: Optional[str] = None
    provider: Optional[str] = None
    usage: Optional[UsageIn] = None
    cost_usd: Optional[float] = None
    input: Any = None
    output: Any = None


class TraceIngest(BaseModel):
    service_name: str = "default"
    environment: str = "development"
    resource_attributes: dict[str, Any] = Field(default_factory=dict)
    spans: list[SpanIn]


class IngestResponse(BaseModel):
    accepted: int
    traces_touched: int
    alerts_created: int


# --- Retrieval --------------------------------------------------------------


class SpanOut(BaseModel):
    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    name: str
    kind: str
    status: str
    status_message: Optional[str]
    start_time_ns: int
    end_time_ns: Optional[int]
    duration_ms: Optional[float]
    model: Optional[str]
    provider: Optional[str]
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: Optional[float]
    input: Any = None
    output: Any = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    events: list[Any] = Field(default_factory=list)
    eval_results: Optional[Any] = None
    trust_score: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class TraceSummary(BaseModel):
    trace_id: str
    service_name: str
    environment: str
    root_name: Optional[str]
    status: str
    duration_ms: Optional[float]
    span_count: int
    llm_call_count: int
    total_tokens: int
    total_cost_usd: float
    min_trust_score: float
    has_alert: bool
    created_at: dt.datetime

    model_config = ConfigDict(from_attributes=True)


class TraceDetail(TraceSummary):
    spans: list[SpanOut] = Field(default_factory=list)


class AlertOut(BaseModel):
    id: int
    trace_id: str
    span_id: Optional[str]
    rule: str
    severity: str
    message: str
    details: Optional[Any]
    resolved: bool
    created_at: dt.datetime

    model_config = ConfigDict(from_attributes=True)


# --- Prompt registry --------------------------------------------------------


class PromptCreate(BaseModel):
    name: str
    template: str
    description: Optional[str] = None
    variables: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
    activate: bool = True


class PromptOut(BaseModel):
    id: int
    name: str
    version: int
    template: str
    description: Optional[str]
    variables: list[str]
    meta: dict[str, Any]
    is_active: bool
    created_at: dt.datetime

    model_config = ConfigDict(from_attributes=True)


# --- Stats ------------------------------------------------------------------


class StatsOverview(BaseModel):
    total_traces: int
    total_spans: int
    total_llm_calls: int
    total_tokens: int
    total_cost_usd: float
    open_alerts: int
    mean_trust_score: float
    p50_latency_ms: Optional[float]
    p95_latency_ms: Optional[float]
    cost_by_model: dict[str, float]
    calls_by_provider: dict[str, int]
