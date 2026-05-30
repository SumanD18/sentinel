# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-05-31

### Added

- **OpenTelemetry exporter** (`sentinel.exporters.OTelExporter`): ships spans to
  any OTLP backend using the GenAI semantic conventions (`gen_ai.*`), preserving
  Sentinel trace/span ids. `sentinel.init(exporter=...)` and a new
  `MultiExporter` let you send to the collector and OTel at once.
- **Retention pruning**: a background sweep deletes traces older than
  `SENTINEL_RETENTION_DAYS` (0 = keep forever).
- Greatly expanded test coverage (Anthropic wrapper, async + streaming paths,
  OTel mapping, secret-leak and prompt-injection guardrails, trace deletion,
  retention, redaction patterns, factuality/repetition evaluators, exporter
  retry/backpressure).

### Fixed

- Collector: bounded the stats endpoint's percentile scan and aggregate trust in
  SQL (no longer loads every row into memory); made prompt activation a single
  atomic statement; hardened root-span selection against missing timestamps.
- SDK: made exporter shutdown/enqueue race-safe, guarded the dropped-span
  counter, and ensured streaming spans still close if finalization raises.
- TypeScript SDK: clamped `sampleRate`/`maxBatchSize`/`flushIntervalMs` against
  NaN/zero/negative values, serialized concurrent flushes, and kept parent
  context for sampled-out spans.

### Changed

- Reconciled the README with the implementation: the OpenTelemetry claim is now
  backed by a real exporter, and the guardrail wording accurately describes
  detection/alerting plus SDK-side PII redaction.

## [0.1.0] - 2026-05-31

First public release.

### Added

- **Python SDK (`sentinel-llm`, imports as `sentinel`)**: one-line instrumentation
  via `sentinel.wrap()` for OpenAI and Anthropic (sync, async, and streaming),
  plus `@sentinel.trace` and `sentinel.span()` for any framework. Background,
  batched, non-blocking span export with PII redaction before egress.
- **TypeScript SDK (`@sentinel/sdk`)**: tracing core, batching exporter, and an
  OpenAI wrapper with `AsyncLocalStorage` context propagation.
- **Evaluators (`sentinel-evaluators`)**: local-first, model-free trust scoring
  (confidence, groundedness, repetition, refusal, factuality) with an optional
  embeddings backend for semantic similarity and self-consistency.
- **Collector (FastAPI)**: idempotent span ingestion, inline evaluation, a
  pluggable guardrail engine (PII, prompt-injection, secret-leak, runaway-loop),
  an alert feed, a git-like prompt registry with rollback, and a Prometheus
  `/metrics` endpoint. SQLite by default, Postgres supported.
- **Dashboard (React + TypeScript)**: trace waterfall, cost/latency overview,
  alert feed, and prompt versioning.
- **Tooling**: one-command Docker Compose stack, runnable examples (OpenAI,
  Anthropic, LangChain, offline demo seeder), a CI-gated evals framework, and
  GitHub Actions for lint, type-check, tests, Docker build, evals, and PyPI
  publishing via Trusted Publishing.

[Unreleased]: https://github.com/SumanD18/sentinel/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/SumanD18/sentinel/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/SumanD18/sentinel/releases/tag/v0.1.0
