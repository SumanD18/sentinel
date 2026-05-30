"""Sentinel collector & API server.

Single FastAPI app exposing:
  * ``POST /v1/traces``      span ingestion (the SDK target)
  * ``GET  /api/...``        retrieval, stats, prompts, alerts (the dashboard)
  * ``GET  /metrics``        Prometheus metrics
  * ``GET  /health``         liveness/readiness
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from . import metrics
from .config import get_settings
from .db import init_db
from .routes import alerts, prompts, stats, traces

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("sentinel.server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info(
        "Sentinel server ready (db=%s, auth=%s, evaluators=%s)",
        settings.database_url.split("://")[0],
        settings.auth_enabled,
        settings.enable_evaluators,
    )
    yield


app = FastAPI(
    title="Sentinel",
    description="Open-source observability & trust layer for AI agents.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(traces.router)
app.include_router(alerts.router)
app.include_router(prompts.router)
app.include_router(stats.router)


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok", "version": app.version}


@app.get("/metrics", tags=["system"], include_in_schema=False)
async def prometheus_metrics() -> Response:
    body, content_type = metrics.render()
    return Response(content=body, media_type=content_type)
