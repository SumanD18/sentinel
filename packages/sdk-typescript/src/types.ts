// Core data structures, mirroring the Python SDK and the collector's wire format.

import { randomUUID } from "node:crypto";

export type SpanKind =
  | "llm"
  | "tool"
  | "retrieval"
  | "agent"
  | "chain"
  | "embedding"
  | "guardrail"
  | "function"
  | "unknown";

export type SpanStatus = "unset" | "ok" | "error";

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface SpanEvent {
  name: string;
  timestamp_ns: number;
  attributes: Record<string, unknown>;
}

function newId(): string {
  return randomUUID().replace(/-/g, "");
}

function nowNs(): number {
  // Wall-clock epoch nanoseconds (ms precision is fine for display).
  return Date.now() * 1_000_000;
}

/** A single unit of work within a trace. */
export class Span {
  name: string;
  kind: SpanKind;
  trace_id: string;
  span_id: string;
  parent_span_id: string | null;
  start_time_ns: number;
  end_time_ns: number | null = null;
  status: SpanStatus = "unset";
  status_message: string | null = null;
  attributes: Record<string, unknown> = {};
  events: SpanEvent[] = [];
  model: string | null = null;
  provider: string | null = null;
  usage: TokenUsage | null = null;
  cost_usd: number | null = null;
  input: unknown = null;
  output: unknown = null;

  constructor(name: string, kind: SpanKind = "unknown", parent?: Span | null) {
    this.name = name;
    this.kind = kind;
    this.trace_id = parent ? parent.trace_id : newId();
    this.span_id = newId();
    this.parent_span_id = parent ? parent.span_id : null;
    this.start_time_ns = nowNs();
  }

  setAttribute(key: string, value: unknown): void {
    this.attributes[key] = value;
  }

  addEvent(name: string, attributes: Record<string, unknown> = {}): void {
    this.events.push({ name, timestamp_ns: nowNs(), attributes });
  }

  recordException(err: unknown): void {
    const e = err as Error;
    this.status = "error";
    this.status_message = `${e?.name ?? "Error"}: ${e?.message ?? String(err)}`;
    this.addEvent("exception", {
      exception_type: e?.name ?? "Error",
      exception_message: e?.message ?? String(err),
    });
  }

  end(): void {
    if (this.end_time_ns === null) this.end_time_ns = nowNs();
    if (this.status === "unset") this.status = "ok";
  }

  get durationMs(): number | null {
    if (this.end_time_ns === null) return null;
    return (this.end_time_ns - this.start_time_ns) / 1_000_000;
  }

  toJSON(): Record<string, unknown> {
    return {
      name: this.name,
      kind: this.kind,
      trace_id: this.trace_id,
      span_id: this.span_id,
      parent_span_id: this.parent_span_id,
      start_time_ns: this.start_time_ns,
      end_time_ns: this.end_time_ns,
      duration_ms: this.durationMs,
      status: this.status,
      status_message: this.status_message,
      attributes: this.attributes,
      events: this.events,
      model: this.model,
      provider: this.provider,
      usage: this.usage,
      cost_usd: this.cost_usd,
      input: this.input,
      output: this.output,
    };
  }
}
