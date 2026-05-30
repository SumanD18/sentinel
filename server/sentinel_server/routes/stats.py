"""Aggregate statistics for the dashboard overview."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_api_key
from ..db import get_session
from ..models import Alert, Span, Trace
from ..schemas import StatsOverview

router = APIRouter(tags=["stats"], dependencies=[Depends(require_api_key)])


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    if lo == hi:
        return round(ordered[lo], 3)
    frac = k - lo
    return round(ordered[lo] * (1 - frac) + ordered[hi] * frac, 3)


@router.get("/api/stats/overview", response_model=StatsOverview)
async def overview(session: AsyncSession = Depends(get_session)) -> StatsOverview:
    total_traces = (await session.execute(select(func.count(Trace.trace_id)))).scalar() or 0
    total_spans = (await session.execute(select(func.count(Span.span_id)))).scalar() or 0
    total_llm = (
        await session.execute(select(func.count(Span.span_id)).where(Span.kind == "llm"))
    ).scalar() or 0
    total_tokens = (await session.execute(select(func.sum(Span.total_tokens)))).scalar() or 0
    total_cost = (await session.execute(select(func.sum(Span.cost_usd)))).scalar() or 0.0
    open_alerts = (
        await session.execute(
            select(func.count(Alert.id)).where(Alert.resolved.is_(False))
        )
    ).scalar() or 0

    # Mean trust is aggregated in the database so we never pull every span row.
    mean_trust_raw = (
        await session.execute(
            select(func.avg(Span.trust_score)).where(Span.trust_score.is_not(None))
        )
    ).scalar()
    mean_trust = round(float(mean_trust_raw), 4) if mean_trust_raw is not None else 1.0

    # Percentiles need the raw values, so bound the scan to the most recent
    # traces rather than loading the entire table into memory.
    _DURATION_SAMPLE = 20_000
    durations = [
        d
        for (d,) in (
            await session.execute(
                select(Trace.duration_ms)
                .where(Trace.duration_ms.is_not(None))
                .order_by(Trace.created_at.desc())
                .limit(_DURATION_SAMPLE)
            )
        ).all()
    ]

    cost_rows = (
        await session.execute(
            select(Span.model, func.sum(Span.cost_usd))
            .where(Span.model.is_not(None))
            .group_by(Span.model)
        )
    ).all()
    cost_by_model = {m: round(c or 0.0, 6) for m, c in cost_rows}

    provider_rows = (
        await session.execute(
            select(Span.provider, func.count(Span.span_id))
            .where(Span.provider.is_not(None))
            .group_by(Span.provider)
        )
    ).all()
    calls_by_provider = {p: int(c) for p, c in provider_rows}

    return StatsOverview(
        total_traces=int(total_traces),
        total_spans=int(total_spans),
        total_llm_calls=int(total_llm),
        total_tokens=int(total_tokens),
        total_cost_usd=round(float(total_cost), 6),
        open_alerts=int(open_alerts),
        mean_trust_score=mean_trust,
        p50_latency_ms=_percentile(durations, 0.5),
        p95_latency_ms=_percentile(durations, 0.95),
        cost_by_model=cost_by_model,
        calls_by_provider=calls_by_provider,
    )
