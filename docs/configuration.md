# Configuration

Everything resolves in this order: **explicit argument → environment variable →
built-in default.** Local development needs no configuration at all.

## SDK (the app that sends traces)

`sentinel.init(...)` accepts these as keyword args, or set the env vars.

| Argument | Env var | Default | Purpose |
| --- | --- | --- | --- |
| `endpoint` | `SENTINEL_ENDPOINT` | `http://localhost:8000` | collector base URL |
| `api_key` | `SENTINEL_API_KEY` | - | bearer token if the server has auth on |
| `service_name` | `SENTINEL_SERVICE_NAME` | `default` | logical service name |
| `environment` | `SENTINEL_ENVIRONMENT` | `development` | e.g. production/staging |
| `enabled` | `SENTINEL_ENABLED` | `true` | `false` makes the SDK a no-op |
| `capture_content` | `SENTINEL_CAPTURE_CONTENT` | `true` | store prompt/response bodies |
| `redact_pii` | `SENTINEL_REDACT_PII` | `true` | scrub PII before export |
| `sample_rate` | `SENTINEL_SAMPLE_RATE` | `1.0` | head-based sampling (0..1) |
| `flush_interval_seconds` | `SENTINEL_FLUSH_INTERVAL` | `2.0` | export batch interval |
| `max_queue_size` | `SENTINEL_MAX_QUEUE_SIZE` | `10000` | backpressure cap |
| `max_batch_size` | `SENTINEL_MAX_BATCH_SIZE` | `256` | spans per POST |

```python
import sentinel
sentinel.init(
    service_name="checkout-agent",
    environment="production",
    endpoint="http://collector.internal:8000",
    sample_rate=0.25,
)
```

### Custom redaction

```python
from sentinel import SentinelConfig

def my_redactor(text: str) -> str:
    return text.replace(secret, "[REDACTED]")

sentinel.init(SentinelConfig(redactor=my_redactor))
```

### Custom pricing

```python
from sentinel.cost import register_pricing
register_pricing("my-self-hosted-llm", prompt_per_1k=0.0, completion_per_1k=0.0)
```

## Server (the collector)

Env-driven, prefix `SENTINEL_`.

| Env var | Default | Purpose |
| --- | --- | --- |
| `SENTINEL_DATABASE_URL` | `sqlite+aiosqlite:///./sentinel.db` | DB DSN |
| `SENTINEL_API_KEYS` | - (auth off) | comma-separated valid keys |
| `SENTINEL_CORS_ORIGINS` | `*` | dashboard origins |
| `SENTINEL_ENABLE_EVALUATORS` | `true` | inline trust scoring |
| `SENTINEL_ALERT_TRUST_THRESHOLD` | `0.5` | alert when trust ≤ this |
| `SENTINEL_RUNAWAY_SPAN_THRESHOLD` | `50` | runaway-loop alert at N LLM calls |
| `SENTINEL_RETENTION_DAYS` | `0` (keep) | prune traces older than N days |
| `SENTINEL_LOG_LEVEL` | `INFO` | log level |

### Enabling auth

```bash
export SENTINEL_API_KEYS="prod-key-1,prod-key-2"
# then in the app:
sentinel.init(api_key="prod-key-1")
```

With no keys set, auth is disabled: the right default for local dev.

### Postgres

```bash
pip install "sentinel-server[postgres]"
export SENTINEL_DATABASE_URL="postgresql+asyncpg://sentinel:sentinel@db:5432/sentinel"
```

Or `docker compose --profile postgres up --build`.

## Dashboard

| Env var | Purpose |
| --- | --- |
| `VITE_API_BASE` | API origin (empty = same origin / dev proxy) |
| `VITE_API_KEY` | bearer token when auth is enabled |
