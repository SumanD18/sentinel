"""End-to-end API tests: ingestion, evaluation, alerts, prompts, stats."""

from __future__ import annotations

import pytest

from conftest import make_trace


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_ingest_and_retrieve_trace(client):
    r = await client.post("/v1/traces", json=make_trace("good"))
    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] == 1
    assert body["traces_touched"] == 1

    r = await client.get("/api/traces/good")
    assert r.status_code == 200
    trace = r.json()
    assert trace["llm_call_count"] == 1
    assert trace["total_tokens"] == 15
    assert len(trace["spans"]) == 1
    span = trace["spans"][0]
    # A clean factual answer should score well and carry eval results.
    assert span["trust_score"] is not None
    assert span["trust_score"] > 0.7
    assert span["eval_results"]


@pytest.mark.asyncio
async def test_low_trust_output_raises_alert(client):
    # A hedging refusal: drives the weakest dimension to zero, which pulls the
    # blended trust score below the alert threshold.
    payload = make_trace(
        "bad",
        output="I am unable to answer this, and as an AI I cannot verify any of it.",
    )
    r = await client.post("/v1/traces", json=payload)
    assert r.json()["alerts_created"] >= 1

    r = await client.get("/api/alerts", params={"resolved": False})
    alerts = r.json()
    assert any(a["rule"] == "low_trust_score" for a in alerts)

    # The trace should be flagged.
    trace = (await client.get("/api/traces/bad")).json()
    assert trace["has_alert"] is True


@pytest.mark.asyncio
async def test_resolve_alert_clears_trace_flag(client):
    await client.post(
        "/v1/traces",
        json=make_trace("res", output="I cannot help with that request."),
    )
    alerts = (await client.get("/api/alerts", params={"resolved": False})).json()
    target = next(a for a in alerts if a["trace_id"] == "res")
    r = await client.post(f"/api/alerts/{target['id']}/resolve")
    assert r.status_code == 200
    assert r.json()["resolved"] is True


@pytest.mark.asyncio
async def test_streaming_multi_batch_ingestion_is_idempotent(client):
    # Same span sent twice (as a streaming exporter might) must not double-count.
    await client.post("/v1/traces", json=make_trace("dup"))
    await client.post("/v1/traces", json=make_trace("dup"))
    trace = (await client.get("/api/traces/dup")).json()
    assert trace["span_count"] == 1


@pytest.mark.asyncio
async def test_prompt_registry_versioning_and_rollback(client):
    r = await client.post(
        "/api/prompts",
        json={"name": "greeting", "template": "Hello {name}", "variables": ["name"]},
    )
    assert r.status_code == 201
    assert r.json()["version"] == 1
    assert r.json()["is_active"] is True

    r = await client.post(
        "/api/prompts",
        json={"name": "greeting", "template": "Hi there {name}!", "variables": ["name"]},
    )
    assert r.json()["version"] == 2

    active = (await client.get("/api/prompts/greeting/active")).json()
    assert active["version"] == 2

    r = await client.post("/api/prompts/greeting/rollback/1")
    assert r.status_code == 200
    active = (await client.get("/api/prompts/greeting/active")).json()
    assert active["version"] == 1


@pytest.mark.asyncio
async def test_stats_overview(client):
    await client.post("/v1/traces", json=make_trace("s1"))
    r = await client.get("/api/stats/overview")
    assert r.status_code == 200
    stats = r.json()
    assert stats["total_traces"] >= 1
    assert stats["total_llm_calls"] >= 1
    assert "gpt-4o" in stats["cost_by_model"]
    assert stats["calls_by_provider"].get("openai", 0) >= 1


@pytest.mark.asyncio
async def test_metrics_endpoint(client):
    await client.post("/v1/traces", json=make_trace("m1"))
    r = await client.get("/metrics")
    assert r.status_code == 200
    assert b"sentinel_spans_ingested_total" in r.content
