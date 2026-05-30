# Python SDK reference

```python
import sentinel
```

## `sentinel.init(config=None, **overrides) -> Tracer`

Initialise the process-global tracer. Pass a `SentinelConfig` or keyword
overrides (`endpoint`, `service_name`, `api_key`, …). Safe to call more than
once; the previous tracer is shut down cleanly. If you never call `init`, the SDK
lazily creates a default tracer from the environment on first use.

## `sentinel.wrap(client, **kwargs) -> client`

Instrument a supported LLM client **in place** and return it. The provider is
detected from the client's type, so you don't import provider-specific helpers.

- Supported: `OpenAI`, `AsyncOpenAI`, `Anthropic`, `AsyncAnthropic`.
- Sync, async, and streaming are all handled; streaming spans close when the
  stream is fully consumed, accumulating the final text and usage.
- Unsupported clients raise `TypeError`; use `@trace` / `span()` for those.

```python
client = sentinel.wrap(OpenAI())
async_client = sentinel.wrap(AsyncOpenAI())
```

## `@sentinel.trace(name=None, kind="function", capture_args=True)`

Wrap a sync or async function in a span. Arguments and the return value are
captured as the span input/output unless `capture_args=False`.

```python
@sentinel.trace(kind="tool", name="search_web")
def search_web(query: str) -> list[str]:
    ...

@sentinel.trace                       # bare form; name defaults to qualname
async def fetch(url: str) -> str:
    ...
```

`kind` accepts a `SpanKind` or a string: `"llm"`, `"tool"`, `"retrieval"`,
`"agent"`, `"chain"`, `"embedding"`, `"guardrail"`, `"function"`.

## `sentinel.span(name, kind="unknown", *, attributes=None, input=None)`

Context manager that opens a span, makes it the current parent for nested spans,
records exceptions, and closes/exports on exit.

```python
with sentinel.span("rag-pipeline", kind="chain", input=question) as span:
    docs = retrieve(question)         # nested spans link automatically
    span.set_attribute("k", len(docs))
```

Inside the block you can set `span.model`, `span.usage`, `span.output`,
`span.set_attribute(...)`, and `span.add_event(...)`.

## `sentinel.flush(timeout=None) -> bool`

Block until queued spans are exported (or the timeout elapses). Call before a
short-lived script exits so the last batch is sent.

## `sentinel.shutdown()`

Flush and tear down the global tracer. Registered with `atexit`, so you rarely
call it directly.

## Disabling in tests / CI

```python
sentinel.init(enabled=False)          # all spans become no-ops
# or
export SENTINEL_ENABLED=false
```

## Types

`Span`, `SpanKind`, `SpanStatus`, `TokenUsage`, and `Event` are exported from the
top-level package for type annotations and manual span construction.
