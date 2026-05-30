# @sentinel/sdk

TypeScript/Node SDK for [Sentinel](https://github.com/SumanD18/sentinel):
drop-in observability and trust layer for AI pipelines and agents.

Zero non-dev dependencies; uses `fetch` and `AsyncLocalStorage` from the Node
runtime (Node ≥ 18).

## Install

```bash
npm install @sentinel/sdk
```

## Use

```ts
import * as sentinel from "@sentinel/sdk";
import OpenAI from "openai";

sentinel.init({ serviceName: "my-agent" });   // defaults to http://localhost:8000
const client = sentinel.wrap(new OpenAI());    // the only change to your code

await client.chat.completions.create({
  model: "gpt-4o",
  messages: [{ role: "user", content: "Hello!" }],
});
```

Streaming is handled automatically - the span closes when the stream is fully
consumed, accumulating the final text and token usage.

Instrument your own code:

```ts
const searchDocs = sentinel.traced("search_docs", "tool", async (q: string) => {
  return await vectorStore.query(q);
});

await sentinel.span("agent-run", "agent", async () => {
  await searchDocs("vector databases");        // nested under the agent span
});
```

Nesting works across `async/await` via `AsyncLocalStorage`, so child spans link
to their parent without you passing any context around.

## Configuration

Set via `init({...})` or `SENTINEL_*` env vars: `endpoint`, `apiKey`,
`serviceName`, `environment`, `enabled`, `captureContent`, `sampleRate`. See the
[configuration guide](https://github.com/SumanD18/sentinel/blob/main/docs/configuration.md).

Call `await sentinel.flush()` before a short-lived process exits to send the last
batch.

## Status

Tracing core, batching exporter, and the OpenAI wrapper are shipped and tested.
Anthropic/Gemini wrappers are on the [roadmap](https://github.com/SumanD18/sentinel#roadmap);
until then, use `sentinel.span()` / `sentinel.traced()` for any client.

## License

Apache 2.0.
