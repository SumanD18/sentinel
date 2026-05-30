import assert from "node:assert/strict";
import { test } from "node:test";
import { Tracer } from "../src/tracer.js";
import type { Exporter } from "../src/exporter.js";
import { Span } from "../src/types.js";
import { instrumentOpenAI } from "../src/wrappers/openai.js";

class MemoryExporter implements Exporter {
  spans: Span[] = [];
  export(span: Span): void {
    this.spans.push(span);
  }
  async flush(): Promise<void> {}
  async shutdown(): Promise<void> {}
  byName(name: string): Span[] {
    return this.spans.filter((s) => s.name === name);
  }
}

function tracerWith(exp: MemoryExporter): Tracer {
  return new Tracer({ enabled: true, captureContent: true }, exp);
}

test("nested spans share trace id and link parent", async () => {
  const exp = new MemoryExporter();
  const tracer = tracerWith(exp);
  await tracer.withSpan("parent", "agent", async () => {
    await tracer.withSpan("child", "tool", async (child) => {
      assert.equal(child.parent_span_id !== null, true);
    });
  });
  const [child] = exp.byName("child");
  const [parent] = exp.byName("parent");
  assert.equal(child.trace_id, parent.trace_id);
  assert.equal(child.parent_span_id, parent.span_id);
  assert.equal(child.status, "ok");
});

test("exception is recorded and rethrown", async () => {
  const exp = new MemoryExporter();
  const tracer = tracerWith(exp);
  await assert.rejects(
    tracer.withSpan("boom", "function", async () => {
      throw new Error("nope");
    }),
  );
  const [span] = exp.byName("boom");
  assert.equal(span.status, "error");
  assert.match(span.status_message ?? "", /nope/);
});

test("instrumentOpenAI captures usage and cost", async () => {
  const exp = new MemoryExporter();
  const tracer = tracerWith(exp);
  const fakeClient = {
    chat: {
      completions: {
        create: async () => ({
          choices: [{ index: 0, finish_reason: "stop", message: { content: "hi" } }],
          usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 },
        }),
      },
    },
  };
  const client = instrumentOpenAI(fakeClient, tracer);
  await client.chat.completions.create({
    model: "gpt-4o",
    messages: [{ role: "user", content: "hi" }],
  });
  const [span] = exp.byName("openai.chat.completions");
  assert.equal(span.model, "gpt-4o");
  assert.equal(span.usage?.total_tokens, 15);
  assert.equal(typeof span.cost_usd, "number");
  assert.ok((span.cost_usd ?? 0) > 0);
});

test("instrumentOpenAI accumulates streamed chunks", async () => {
  const exp = new MemoryExporter();
  const tracer = tracerWith(exp);
  async function* stream() {
    for (const c of ["h", "i"]) {
      yield { choices: [{ delta: { content: c }, finish_reason: null }] };
    }
    yield {
      choices: [{ delta: {}, finish_reason: "stop" }],
      usage: { prompt_tokens: 10, completion_tokens: 2, total_tokens: 12 },
    };
  }
  const fakeClient = {
    chat: { completions: { create: async () => stream() } },
  };
  const client = instrumentOpenAI(fakeClient, tracer);
  const result = await client.chat.completions.create({ model: "gpt-4o", stream: true });
  const chunks = [];
  for await (const ch of result as AsyncIterable<unknown>) chunks.push(ch);
  const [span] = exp.byName("openai.chat.completions");
  assert.equal(span.output, "hi");
  assert.equal(span.usage?.completion_tokens, 2);
  assert.equal(span.attributes.finish_reason, "stop");
});
