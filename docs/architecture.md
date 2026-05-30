# Architecture

Sentinel is four cooperating pieces: an **SDK** in your app, a **collector** that
ingests and analyses, a **store**, and a **dashboard**. Everything is
self-hosted; trace data never leaves your network.

## Data flow

1. **Instrument.** `sentinel.wrap(client)` patches the client's bound methods on
   that instance (not globally), so instrumented and uninstrumented clients can
   coexist. `@sentinel.trace` and `sentinel.span()` cover everything else.
2. **Span creation.** Each call opens a `Span` with a `kind` (llm, tool,
   retrieval, agent, …). Parent/child links are resolved through `contextvars`,
   so nesting is correct under threads, asyncio, and concurrent agent steps.
3. **Redaction.** If `redact_pii` is on (default), payloads are scrubbed *in the
   app process* before anything is queued.
4. **Export.** Finished spans go to an in-memory queue drained by a daemon
   thread, which batches and POSTs to `/v1/traces`. The host's hot path never
   blocks on the network; if the collector is unreachable, spans are retried with
   backoff and then dropped (counted, never unbounded).
5. **Ingestion.** The collector upserts spans (idempotent, tolerant of
   out-of-order / multi-batch streaming delivery), runs the inline evaluator
   suite over LLM outputs, applies guardrails, raises alerts, and recomputes
   per-trace aggregates.
6. **Serve.** The dashboard reads the API; Prometheus scrapes `/metrics`; OTel
   exporters can forward to Grafana/Datadog.

```
app --wrap()--> SDK --queue--> background thread --POST /v1/traces--> collector
                                                                        |
                          +---------------------------------------------+
                          v                  v                v          v
                     evaluators        guardrails         storage    metrics
                   (trust scoring)   (alerts/policy)   (SQLite/PG)  (Prometheus)
                          +---------------- dashboard / OTel <----------+
```

## Why patch the instance, not the library

Global monkey-patching of `openai` makes it impossible to run a traced and an
untraced client side by side, and it surprises users. Sentinel patches the
specific client object you hand to `wrap()`, marks the wrapped method with a
sentinel flag to stay idempotent, and degrades gracefully (a warning, not a
crash) if a provider changes its method layout.

## Ingestion is idempotent

The streaming exporter may deliver the same trace across several batches and
out of order. Ingestion therefore **upserts** spans by `span_id` and recomputes
each touched trace's aggregates from the full set of its spans. Re-sending a span
never double-counts. Evaluators run once per span (guarded by `trust_score is
None`) so re-ingestion is cheap.

## Trust scoring

See [`packages/evaluators`](../packages/evaluators/README.md). Scores blend the
weakest dimension with the mean so one hard failure is never averaged away. The
aggregate drives the `low_trust_score` guardrail.

## Storage model

- `traces` - one row per run, with denormalised aggregates (cost, tokens, span
  count, min trust, alert flag) for fast list/overview queries.
- `spans` - the tree; `trace_id` + `parent_span_id` define structure; LLM spans
  carry model/usage/cost and the evaluator output.
- `alerts` - raised by guardrails; de-duplicated per (trace, rule, span).
- `prompt_versions` - git-like prompt registry with a single active version.

SQLite is the zero-config default; set `SENTINEL_DATABASE_URL` to a
`postgresql+asyncpg://…` DSN for production. The ORM (SQLAlchemy 2.0 async) is
identical across both.

## Extensibility

- **Wrappers** - add a provider in `packages/sdk-python/sentinel/wrappers/`.
- **Evaluators** - subclass `Evaluator`, `register()` it.
- **Guardrails** - a function `(span, evals, trust) -> [AlertSpec]`, `register()`ed
  in the server.
- **Exporters** - implement `Exporter` to send spans somewhere other than the
  default collector.
