// OpenAI client instrumentation (non-streaming + streaming).
// Patches `chat.completions.create` on the given client instance.

import type { Tracer } from "../tracer.js";
import type { Span, TokenUsage } from "../types.js";

/* eslint-disable @typescript-eslint/no-explicit-any */
type AnyObj = Record<string, any>;

function extractUsage(resp: AnyObj | undefined): TokenUsage | null {
  const u = resp?.usage;
  if (!u) return null;
  return {
    prompt_tokens: u.prompt_tokens ?? 0,
    completion_tokens: u.completion_tokens ?? 0,
    total_tokens: u.total_tokens ?? (u.prompt_tokens ?? 0) + (u.completion_tokens ?? 0),
  };
}

function stampRequest(span: Span, args: AnyObj): void {
  span.model = args?.model ?? null;
  span.provider = "openai";
  span.setAttribute("stream", Boolean(args?.stream));
  span.input = args?.messages ?? null;
}

function isAsyncIterable(x: unknown): x is AsyncIterable<AnyObj> {
  return (
    x != null &&
    typeof (x as { [Symbol.asyncIterator]?: unknown })[Symbol.asyncIterator] === "function"
  );
}

/** Instrument an OpenAI client (the official `openai` npm package) in place. */
export function instrumentOpenAI<T extends AnyObj>(client: T, tracer: Tracer): T {
  const completions = client?.chat?.completions;
  const original = completions?.create;
  if (typeof original !== "function" || (original as AnyObj).__sentinelWrapped) {
    return client;
  }

  const wrapped = async function (this: unknown, args: AnyObj, ...rest: unknown[]) {
    const span = tracer.startSpan("openai.chat.completions", "llm");
    stampRequest(span, args);

    let result: unknown;
    try {
      result = await original.call(completions, args, ...rest);
    } catch (err) {
      span.recordException(err);
      tracer.endSpan(span);
      throw err;
    }

    if (args?.stream && isAsyncIterable(result)) {
      return wrapStream(result, span, tracer);
    }

    const resp = result as AnyObj;
    span.usage = extractUsage(resp);
    const choice = resp?.choices?.[0];
    if (choice) {
      span.setAttribute("finish_reason", choice.finish_reason ?? null);
      tracer.setOutput(span, choice.message ?? null);
    }
    tracer.endSpan(span);
    return result;
  };

  (wrapped as AnyObj).__sentinelWrapped = true;
  completions.create = wrapped;
  return client;
}

async function* wrapStream(
  stream: AsyncIterable<AnyObj>,
  span: Span,
  tracer: Tracer,
): AsyncGenerator<AnyObj> {
  const parts: string[] = [];
  let usage: TokenUsage | null = null;
  let finish: string | null = null;
  let count = 0;
  try {
    for await (const chunk of stream) {
      count++;
      const choice = chunk?.choices?.[0];
      const piece = choice?.delta?.content;
      if (piece) parts.push(piece);
      if (choice?.finish_reason) finish = choice.finish_reason;
      const u = extractUsage(chunk);
      if (u) usage = u;
      yield chunk;
    }
  } catch (err) {
    span.recordException(err);
    throw err;
  } finally {
    span.setAttribute("stream_chunks", count);
    if (finish) span.setAttribute("finish_reason", finish);
    if (usage) span.usage = usage;
    tracer.setOutput(span, parts.join(""));
    tracer.endSpan(span);
  }
}
