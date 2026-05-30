// Public API for the Sentinel TypeScript SDK.
//
//   import * as sentinel from "@sentinel/sdk";
//   sentinel.init({ serviceName: "my-agent" });
//   const client = sentinel.wrap(new OpenAI());
//
//   await sentinel.span("agent-run", "agent", async () => { ... });

import type { SentinelConfig } from "./exporter.js";
import { Tracer } from "./tracer.js";
import type { SpanKind, Span } from "./types.js";
import { instrumentOpenAI } from "./wrappers/openai.js";

export { Tracer } from "./tracer.js";
export { Span } from "./types.js";
export type { SpanKind, SpanStatus, TokenUsage } from "./types.js";
export type { SentinelConfig } from "./exporter.js";
export { registerPricing } from "./cost.js";

let defaultTracer: Tracer | null = null;

export function init(config?: Partial<SentinelConfig>): Tracer {
  defaultTracer = new Tracer(config);
  return defaultTracer;
}

export function getTracer(): Tracer {
  if (!defaultTracer) defaultTracer = new Tracer();
  return defaultTracer;
}

/* eslint-disable @typescript-eslint/no-explicit-any */
type AnyObj = Record<string, any>;

/** Detect the provider from the client and instrument it in place. */
export function wrap<T extends AnyObj>(client: T): T {
  const ctor = client?.constructor?.name;
  if (ctor === "OpenAI" || ctor === "AzureOpenAI" || client?.chat?.completions?.create) {
    return instrumentOpenAI(client, getTracer());
  }
  throw new TypeError(
    `sentinel.wrap does not support ${ctor ?? typeof client}. ` +
      "Use sentinel.span() to instrument unsupported clients.",
  );
}

/** Run a function inside a span on the global tracer. */
export function span<T>(
  name: string,
  kind: SpanKind,
  fn: (span: Span) => Promise<T> | T,
): Promise<T> {
  return getTracer().withSpan(name, kind, fn);
}

/** Wrap a function so each call is traced. */
export function traced<A extends unknown[], R>(
  name: string,
  kind: SpanKind,
  fn: (...args: A) => Promise<R> | R,
): (...args: A) => Promise<R> {
  return (...args: A) =>
    getTracer().withSpan(name, kind, async (s) => {
      s.input = args;
      const result = await fn(...args);
      getTracer().setOutput(s, result);
      return result;
    });
}

export function flush(): Promise<void> {
  return getTracer().flush();
}

export function shutdown(): Promise<void> {
  return getTracer().shutdown();
}
