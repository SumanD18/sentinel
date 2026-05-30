"""Trace ingestion and retrieval endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..auth import require_api_key
from ..db import get_session
from ..ingest import ingest_trace
from ..models import Span, Trace
from ..schemas import (
    IngestResponse,
    SpanOut,
    TraceDetail,
    TraceIngest,
    TraceSummary,
)

router = APIRouter(tags=["traces"])


@router.post(
    "/v1/traces",
    response_model=IngestResponse,
    dependencies=[Depends(require_api_key)],
    summary="Ingest a batch of spans",
)
async def post_traces(
    payload: TraceIngest, session: AsyncSession = Depends(get_session)
) -> IngestResponse:
    if not payload.spans:
        return IngestResponse(accepted=0, traces_touched=0, alerts_created=0)
    return await ingest_trace(session, payload)


@router.get(
    "/api/traces",
    response_model=list[TraceSummary],
    dependencies=[Depends(require_api_key)],
    summary="List traces (newest first) with filters",
)
async def list_traces(
    session: AsyncSession = Depends(get_session),
    service: Optional[str] = None,
    environment: Optional[str] = None,
    status: Optional[str] = None,
    has_alert: Optional[bool] = None,
    min_trust: Optional[float] = None,
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
) -> list[Trace]:
    stmt = select(Trace).order_by(Trace.created_at.desc())
    if service:
        stmt = stmt.where(Trace.service_name == service)
    if environment:
        stmt = stmt.where(Trace.environment == environment)
    if status:
        stmt = stmt.where(Trace.status == status)
    if has_alert is not None:
        stmt = stmt.where(Trace.has_alert.is_(has_alert))
    if min_trust is not None:
        stmt = stmt.where(Trace.min_trust_score >= min_trust)
    stmt = stmt.limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars().all())


@router.get(
    "/api/traces/{trace_id}",
    response_model=TraceDetail,
    dependencies=[Depends(require_api_key)],
    summary="Get one trace with its full span tree",
)
async def get_trace(
    trace_id: str, session: AsyncSession = Depends(get_session)
) -> TraceDetail:
    trace = await session.get(
        Trace, trace_id, options=[selectinload(Trace.spans)]
    )
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    spans = sorted(trace.spans, key=lambda s: s.start_time_ns)
    detail = TraceDetail.model_validate(trace, from_attributes=True)
    detail.spans = [SpanOut.model_validate(s, from_attributes=True) for s in spans]
    return detail


@router.get(
    "/api/spans/{span_id}",
    response_model=SpanOut,
    dependencies=[Depends(require_api_key)],
    summary="Get a single span",
)
async def get_span(
    span_id: str, session: AsyncSession = Depends(get_session)
) -> Span:
    span = await session.get(Span, span_id)
    if span is None:
        raise HTTPException(status_code=404, detail="Span not found")
    return span


@router.delete(
    "/api/traces/{trace_id}",
    dependencies=[Depends(require_api_key)],
    summary="Delete a trace and its spans/alerts",
)
async def delete_trace(
    trace_id: str, session: AsyncSession = Depends(get_session)
) -> dict:
    trace = await session.get(Trace, trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    await session.delete(trace)
    await session.commit()
    return {"deleted": trace_id}
