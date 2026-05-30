"""Data retention: prune traces (and their cascaded spans/alerts) older than the
configured number of days.

Deletion goes through the ORM so the ``delete-orphan`` cascade on the Trace
relationships removes spans and alerts regardless of whether the database
enforces foreign keys (SQLite does not, by default). Work is chunked so a large
backlog never opens one giant transaction.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging

from sqlalchemy import select

from .db import SessionLocal
from .models import Trace

logger = logging.getLogger("sentinel.server")


async def prune_old_traces(retention_days: int, batch: int = 1000) -> int:
    """Delete traces created more than ``retention_days`` ago. Returns the count
    deleted. A non-positive ``retention_days`` is a no-op (keep forever)."""
    if retention_days <= 0:
        return 0
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=retention_days)
    deleted = 0
    async with SessionLocal() as session:
        while True:
            rows = (
                (
                    await session.execute(
                        select(Trace).where(Trace.created_at < cutoff).limit(batch)
                    )
                )
                .scalars()
                .all()
            )
            if not rows:
                break
            for trace in rows:
                await session.delete(trace)
            await session.commit()
            deleted += len(rows)
            if len(rows) < batch:
                break
    return deleted


async def retention_loop(
    stop: asyncio.Event, retention_days: int, interval_seconds: float = 3600.0
) -> None:
    """Run :func:`prune_old_traces` on an interval until ``stop`` is set."""
    while not stop.is_set():
        try:
            n = await prune_old_traces(retention_days)
            if n:
                logger.info(
                    "retention: pruned %d trace(s) older than %d day(s)",
                    n,
                    retention_days,
                )
        except Exception:  # pragma: no cover - never let the sweep crash the app
            logger.exception("retention sweep failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            pass
