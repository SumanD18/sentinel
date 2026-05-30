# sentinel-server

The Sentinel collector and API server. Part of
[Sentinel](https://github.com/SumanD18/sentinel).

Ingests spans from the SDK, runs trust evaluation and guardrails, stores traces
(SQLite or Postgres), and serves the dashboard API plus a Prometheus
`/metrics` endpoint.

## Run

```bash
pip install sentinel-evaluators        # required dependency (local checkout: ../packages/evaluators)
pip install sentinel-server
sentinel-server --host 0.0.0.0 --port 8000
# dev: sentinel-server --reload
```

Or via Docker from the repo root: `docker compose up --build`.

## Endpoints

| Method & path | Purpose |
| --- | --- |
| `POST /v1/traces` | span ingestion (SDK target) |
| `GET /api/traces` | list traces (filters: service, status, has_alert, min_trust) |
| `GET /api/traces/{id}` | one trace with its full span tree |
| `GET /api/spans/{id}` | a single span |
| `GET /api/alerts` | alert feed |
| `POST /api/alerts/{id}/resolve` | resolve an alert |
| `GET /api/prompts` · `/api/prompts/{name}/versions` | prompt registry |
| `POST /api/prompts/{name}/rollback/{v}` | roll back to a prompt version |
| `GET /api/stats/overview` | dashboard aggregates |
| `GET /metrics` | Prometheus metrics |
| `GET /health` · `/docs` | liveness · OpenAPI |

## Configuration

Env-driven (prefix `SENTINEL_`). Highlights:

| Var | Default | Purpose |
| --- | --- | --- |
| `SENTINEL_DATABASE_URL` | `sqlite+aiosqlite:///./sentinel.db` | DB DSN |
| `SENTINEL_API_KEYS` | _(empty → auth off)_ | comma-separated keys |
| `SENTINEL_ENABLE_EVALUATORS` | `true` | inline trust scoring |
| `SENTINEL_ALERT_TRUST_THRESHOLD` | `0.5` | alert below this score |
| `SENTINEL_RUNAWAY_SPAN_THRESHOLD` | `50` | runaway-loop alert at N LLM calls |

For Postgres: `pip install "sentinel-server[postgres]"` and set
`SENTINEL_DATABASE_URL=postgresql+asyncpg://user:pass@host/db`.

## License

Apache 2.0.
