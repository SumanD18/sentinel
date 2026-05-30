"""Server test fixtures: an isolated in-memory DB and an async test client."""

from __future__ import annotations

import os

# Force an in-memory SQLite DB before anything imports the app/config.
os.environ.setdefault("SENTINEL_DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402


@pytest_asyncio.fixture
async def client():
    # Import lazily so the env var above is in effect.
    from sentinel_server.db import init_db
    from sentinel_server.main import app

    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def make_trace(trace_id: str = "t1", output: str = "Paris is the capital of France."):
    """Build a minimal ingestion payload with one LLM span."""
    return {
        "service_name": "test-svc",
        "environment": "test",
        "spans": [
            {
                "name": "openai.chat.completions",
                "kind": "llm",
                "trace_id": trace_id,
                "span_id": f"{trace_id}-s1",
                "parent_span_id": None,
                "start_time_ns": 1_000,
                "end_time_ns": 2_000_000,
                "duration_ms": 1.999,
                "status": "ok",
                "model": "gpt-4o",
                "provider": "openai",
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
                "cost_usd": 0.0001,
                "input": [{"role": "user", "content": "What is the capital of France?"}],
                "output": {"role": "assistant", "content": output},
                "attributes": {},
                "events": [],
            }
        ],
    }
