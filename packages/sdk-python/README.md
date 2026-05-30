# sentinel-llm

Drop-in observability and trust layer for AI pipelines and agents. Part of
[Sentinel](https://github.com/SumanD18/sentinel). Installs as `sentinel-llm`,
imports as `sentinel`.

The SDK has **zero runtime dependencies** (standard library only) so it's safe to
import into any process. It intercepts LLM calls, tool calls, and retrieval steps
and ships them - batched, PII-redacted, on a background thread - to a Sentinel
collector.

## Install

```bash
pip install sentinel-llm
# optional provider extras
pip install "sentinel-llm[openai]"      # or [anthropic], [otel]
```

## Use

```python
import sentinel
from openai import OpenAI

sentinel.init(service_name="my-agent")     # defaults to http://localhost:8000
client = sentinel.wrap(OpenAI())           # the only change to your code

client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}],
)
```

Instrument your own code:

```python
@sentinel.trace(kind="tool")
def search(query: str) -> list[str]:
    ...

with sentinel.span("agent-run", kind="agent"):
    search("vector databases")             # nested under the agent span
```

Works with sync and async clients, streaming responses, and Anthropic
(`sentinel.wrap(Anthropic())`). For other frameworks, use `@sentinel.trace` /
`sentinel.span()` directly.

## Configuration

All settings have env-var equivalents (`SENTINEL_*`); see the
[configuration guide](https://github.com/SumanD18/sentinel/blob/main/docs/configuration.md).

| Option | Default | Purpose |
| --- | --- | --- |
| `endpoint` | `http://localhost:8000` | collector URL |
| `service_name` | `default` | logical service name |
| `capture_content` | `true` | record prompt/response payloads |
| `redact_pii` | `true` | redact PII before export |
| `sample_rate` | `1.0` | head-based sampling |
| `enabled` | `true` | set false to make the SDK a no-op |

## License

Apache 2.0.
