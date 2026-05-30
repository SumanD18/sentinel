// Tracer + context propagation via AsyncLocalStorage, so nested spans link up
// correctly across async/await without threading a context object everywhere.

import { AsyncLocalStorage } from "node:async_hooks";
import { estimateCost } from "./cost.js";
import {
  configFromEnv,
  HttpExporter,
  NoopExporter,
  type Exporter,
  type SentinelConfig,
} from "./exporter.js";
import { Span, type SpanKind } from "./types.js";

const storage = new AsyncLocalStorage<Span>();

export class Tracer {
  readonly config: SentinelConfig;
  private readonly exporter: Exporter;

  constructor(config?: Partial<SentinelConfig>, exporter?: Exporter) {
    this.config = configFromEnv(config);
    this.exporter =
      exporter ?? (this.config.enabled ? new HttpExporter(this.config) : new NoopExporter());
  }

  currentSpan(): Span | undefined {
    return storage.getStore();
  }

  startSpan(name: string, kind: SpanKind = "unknown"): Span {
    return new Span(name, kind, this.currentSpan() ?? null);
  }

  endSpan(span: Span): void {
    if (span.kind === "llm" && span.cost_usd === null) {
      span.cost_usd = estimateCost(span.model, span.usage);
    }
    span.end();
    if (this.config.enabled) this.exporter.export(span);
  }

  /** Run `fn` inside a span that becomes the active parent for nested spans. */
  async withSpan<T>(
    name: string,
    kind: SpanKind,
    fn: (span: Span) => Promise<T> | T,
  ): Promise<T> {
    const span = this.startSpan(name, kind);
    // Sampled out: still establish context (correct parent + trace id) so nested
    // spans link up, but never export this span.
    if (this.config.sampleRate < 1 && Math.random() >= this.config.sampleRate) {
      return storage.run(span, () => fn(span));
    }
    return storage.run(span, async () => {
      try {
        return await fn(span);
      } catch (err) {
        span.recordException(err);
        throw err;
      } finally {
        this.endSpan(span);
      }
    });
  }

  setOutput(span: Span, output: unknown): void {
    if (this.config.captureContent) span.output = output;
  }

  flush(): Promise<void> {
    return this.exporter.flush();
  }

  shutdown(): Promise<void> {
    return this.exporter.shutdown();
  }
}
