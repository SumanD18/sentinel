"""Trace ingestion pipeline.

Persists incoming spans, runs the inline evaluator suite over LLM outputs,
applies guardrails, raises alerts, and (re)computes per-trace aggregates. The
pipeline is idempotent and tolerant of out-of-order / multi-batch delivery,
which is what the streaming SDK exporter produces.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import metrics
from .config import get_settings
from .guardrails import run_guardrails
from .models import Alert, Span, Trace
from .schemas import IngestResponse, SpanIn, TraceIngest

logger = logging.getLogger("sentinel.server")

# Evaluators are an optional but recommended dependency. Degrade gracefully.
try:
    from sentinel_evaluators import EvalInput, aggregate_score, run_suite

    _EVALS_AVAILABLE = True
except Exception:  # pragma: no cover
    _EVALS_AVAILABLE = False
    logger.warning("sentinel_evaluators not installed; trust scoring disabled")


def _flatten_text(value) -> str:
    """Coerce an arbitrary input/output payload into plain text for evaluation."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("content", "text", "output", "message"):
            if key in value:
                return _flatten_text(value[key])
        return " ".join(_flatten_text(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten_text(v) for v in value)
    return str(value)


async def ingest_trace(session: AsyncSession, payload: TraceIngest) -> IngestResponse:
    touched: set[str] = set()
    for span_in in payload.spans:
        await _upsert_span(session, span_in)
        touched.add(span_in.trace_id)
        metrics.record_span(span_in)

    await session.flush()

    alerts_created = 0
    for trace_id in touched:
        alerts_created += await _process_trace(session, trace_id, payload)

    await session.commit()
    return IngestResponse(
        accepted=len(payload.spans),
        traces_touched=len(touched),
        alerts_created=alerts_created,
    )


async def _upsert_span(session: AsyncSession, span_in: SpanIn) -> Span:
    existing = await session.get(Span, span_in.span_id)
    usage = span_in.usage
    fields = dict(
        trace_id=span_in.trace_id,
        parent_span_id=span_in.parent_span_id,
        name=span_in.name,
        kind=span_in.kind,
        status=span_in.status,
        status_message=span_in.status_message,
        start_time_ns=span_in.start_time_ns,
        end_time_ns=span_in.end_time_ns,
        duration_ms=span_in.duration_ms,
        model=span_in.model,
        provider=span_in.provider,
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
        total_tokens=usage.total_tokens if usage else 0,
        cost_usd=span_in.cost_usd,
        input=span_in.input,
        output=span_in.output,
        attributes=span_in.attributes,
        events=[e.model_dump() for e in span_in.events],
    )
    if existing is None:
        span = Span(span_id=span_in.span_id, **fields)
        session.add(span)
        return span
    for key, value in fields.items():
        setattr(existing, key, value)
    return existing


async def _process_trace(
    session: AsyncSession, trace_id: str, payload: TraceIngest
) -> int:
    rows = (
        (await session.execute(select(Span).where(Span.trace_id == trace_id)))
        .scalars()
        .all()
    )
    if not rows:
        return 0

    settings = get_settings()
    # Context for groundedness: text from retrieval/tool spans in this trace.
    context = [
        _flatten_text(s.output)
        for s in rows
        if s.kind in {"retrieval", "tool"} and s.output
    ]

    alerts_created = 0
    llm_spans = [s for s in rows if s.kind == "llm"]

    for span in rows:
        # Evaluate LLM spans exactly once (trust_score stays None until scored).
        if (
            _EVALS_AVAILABLE
            and settings.enable_evaluators
            and span.kind == "llm"
            and span.trust_score is None
            and span.output is not None
        ):
            output_text = _flatten_text(span.output)
            if output_text:
                results = run_suite(
                    EvalInput(
                        output=output_text,
                        prompt=_flatten_text(span.input),
                        context=context or None,
                    )
                )
                span.eval_results = [r.to_dict() for r in results]
                span.trust_score = aggregate_score(results)
                metrics.record_trust(span.trust_score)

        eval_dicts = span.eval_results or []
        for spec in run_guardrails(_span_to_dict(span), eval_dicts, span.trust_score):
            if await _alert_exists(session, trace_id, spec.rule, spec.span_id):
                continue
            session.add(
                Alert(
                    trace_id=trace_id,
                    span_id=spec.span_id,
                    rule=spec.rule,
                    severity=spec.severity,
                    message=spec.message,
                    details=spec.details,
                )
            )
            alerts_created += 1
            metrics.record_alert(spec.severity)

    # Runaway-loop detection at the trace level.
    if len(llm_spans) > settings.runaway_span_threshold and not await _alert_exists(
        session, trace_id, "runaway_loop", None
    ):
        session.add(
            Alert(
                trace_id=trace_id,
                rule="runaway_loop",
                severity="critical",
                message=f"Trace made {len(llm_spans)} LLM calls "
                f"(> {settings.runaway_span_threshold}); possible runaway loop.",
                details={"llm_call_count": len(llm_spans)},
            )
        )
        alerts_created += 1
        metrics.record_alert("critical")

    await session.flush()
    await _recompute_trace(session, trace_id, rows, payload)
    return alerts_created


def _span_to_dict(span: Span) -> dict:
    return {
        "span_id": span.span_id,
        "kind": span.kind,
        "status": span.status,
        "status_message": span.status_message,
        "input": span.input,
        "output": span.output,
    }


async def _alert_exists(
    session: AsyncSession, trace_id: str, rule: str, span_id: Optional[str]
) -> bool:
    stmt = select(Alert.id).where(Alert.trace_id == trace_id, Alert.rule == rule)
    if span_id is not None:
        stmt = stmt.where(Alert.span_id == span_id)
    return (await session.execute(stmt.limit(1))).first() is not None


async def _recompute_trace(
    session: AsyncSession, trace_id: str, spans: list[Span], payload: TraceIngest
) -> None:
    starts = [s.start_time_ns for s in spans if s.start_time_ns is not None]
    ends = [s.end_time_ns for s in spans if s.end_time_ns is not None]
    root = min(spans, key=lambda s: s.start_time_ns, default=None)
    trust_scores = [s.trust_score for s in spans if s.trust_score is not None]

    # Query open alerts *before* touching the Trace row, so autoflush never
    # tries to persist a half-populated trace.
    open_alerts = (
        await session.execute(
            select(Alert.id).where(Alert.trace_id == trace_id, Alert.resolved.is_(False))
        )
    ).first()

    trace = await session.get(Trace, trace_id)
    if trace is None:
        trace = Trace(trace_id=trace_id)
        session.add(trace)

    trace.service_name = payload.service_name
    trace.environment = payload.environment
    trace.root_name = root.name if root else None
    trace.status = "error" if any(s.status == "error" for s in spans) else "ok"
    trace.start_time_ns = min(starts) if starts else 0
    trace.end_time_ns = max(ends) if ends else None
    trace.duration_ms = (
        (max(ends) - min(starts)) / 1_000_000 if starts and ends else None
    )
    trace.span_count = len(spans)
    trace.llm_call_count = sum(1 for s in spans if s.kind == "llm")
    trace.total_tokens = sum(s.total_tokens or 0 for s in spans)
    trace.total_cost_usd = round(sum(s.cost_usd or 0.0 for s in spans), 8)
    trace.min_trust_score = min(trust_scores) if trust_scores else 1.0
    trace.has_alert = open_alerts is not None
