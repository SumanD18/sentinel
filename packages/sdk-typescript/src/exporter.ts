// Batching HTTP exporter. Spans are queued and flushed on a timer (and on
// process exit), so the host's hot path never blocks on the network.

import type { Span } from "./types.js";

export interface SentinelConfig {
  endpoint: string;
  apiKey?: string;
  serviceName: string;
  environment: string;
  enabled: boolean;
  captureContent: boolean;
  flushIntervalMs: number;
  maxBatchSize: number;
  sampleRate: number;
}

export function configFromEnv(overrides: Partial<SentinelConfig> = {}): SentinelConfig {
  const env = process.env;
  return {
    endpoint: env.SENTINEL_ENDPOINT ?? "http://localhost:8000",
    apiKey: env.SENTINEL_API_KEY,
    serviceName: env.SENTINEL_SERVICE_NAME ?? "default",
    environment: env.SENTINEL_ENVIRONMENT ?? "development",
    enabled: (env.SENTINEL_ENABLED ?? "true") !== "false",
    captureContent: (env.SENTINEL_CAPTURE_CONTENT ?? "true") !== "false",
    flushIntervalMs: Number(env.SENTINEL_FLUSH_INTERVAL_MS ?? 2000),
    maxBatchSize: Number(env.SENTINEL_MAX_BATCH_SIZE ?? 256),
    sampleRate: Number(env.SENTINEL_SAMPLE_RATE ?? 1.0),
    ...overrides,
  };
}

export interface Exporter {
  export(span: Span): void;
  flush(): Promise<void>;
  shutdown(): Promise<void>;
}

export class HttpExporter implements Exporter {
  private queue: Span[] = [];
  private timer: ReturnType<typeof setInterval> | null = null;
  private readonly url: string;
  private shuttingDown = false;

  constructor(private readonly config: SentinelConfig) {
    this.url = config.endpoint.replace(/\/+$/, "") + "/v1/traces";
    this.timer = setInterval(() => void this.flush(), config.flushIntervalMs);
    // Don't keep the event loop alive just for the flush timer.
    if (this.timer.unref) this.timer.unref();
    process.once("beforeExit", () => void this.shutdown());
  }

  export(span: Span): void {
    if (this.shuttingDown) return;
    this.queue.push(span);
    if (this.queue.length >= this.config.maxBatchSize) void this.flush();
  }

  async flush(): Promise<void> {
    if (this.queue.length === 0) return;
    const batch = this.queue.splice(0, this.queue.length);
    const payload = {
      service_name: this.config.serviceName,
      environment: this.config.environment,
      resource_attributes: {},
      spans: batch.map((s) => s.toJSON()),
    };
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (this.config.apiKey) headers["Authorization"] = `Bearer ${this.config.apiKey}`;

    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const res = await fetch(this.url, {
          method: "POST",
          headers,
          body: JSON.stringify(payload),
        });
        if (res.ok) return;
        if (res.status >= 400 && res.status < 500) return; // don't retry client errors
      } catch {
        // network error - retry with a short backoff
      }
      await new Promise((r) => setTimeout(r, 250 * (attempt + 1)));
    }
    // Give up silently; observability must never crash the app.
  }

  async shutdown(): Promise<void> {
    if (this.shuttingDown) return;
    this.shuttingDown = true;
    if (this.timer) clearInterval(this.timer);
    await this.flush();
  }
}

export class NoopExporter implements Exporter {
  export(): void {}
  async flush(): Promise<void> {}
  async shutdown(): Promise<void> {}
}
