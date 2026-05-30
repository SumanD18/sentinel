"""Alert feed and resolution endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_api_key
from ..db import get_session
from ..models import Alert, Trace
from ..schemas import AlertOut

router = APIRouter(tags=["alerts"], dependencies=[Depends(require_api_key)])


@router.get("/api/alerts", response_model=list[AlertOut])
async def list_alerts(
    session: AsyncSession = Depends(get_session),
    severity: Optional[str] = None,
    rule: Optional[str] = None,
    resolved: Optional[bool] = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
) -> list[Alert]:
    stmt = select(Alert).order_by(Alert.created_at.desc())
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    if rule:
        stmt = stmt.where(Alert.rule == rule)
    if resolved is not None:
        stmt = stmt.where(Alert.resolved.is_(resolved))
    stmt = stmt.limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars().all())


@router.post("/api/alerts/{alert_id}/resolve", response_model=AlertOut)
async def resolve_alert(
    alert_id: int, session: AsyncSession = Depends(get_session)
) -> Alert:
    alert = await session.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.resolved = True

    # If no open alerts remain for the trace, clear its flag.
    remaining = (
        await session.execute(
            select(Alert.id).where(
                Alert.trace_id == alert.trace_id,
                Alert.resolved.is_(False),
                Alert.id != alert_id,
            )
        )
    ).first()
    trace = await session.get(Trace, alert.trace_id)
    if trace is not None:
        trace.has_alert = remaining is not None
    await session.commit()
    await session.refresh(alert)
    return alert
