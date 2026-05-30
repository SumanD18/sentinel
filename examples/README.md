# Examples

Each example sends traces to a running Sentinel collector. Start the stack first:

```bash
docker compose up --build      # from the repo root
# server → http://localhost:8000   dashboard → http://localhost:3000
```

| Example | What it shows | Needs an API key? |
| --- | --- | --- |
| [`quickstart/`](quickstart/) | Seed realistic demo traces (healthy, RAG, error, hallucination, runaway loop) | **No** |
| [`openai-agent/`](openai-agent/) | Tool-using agent with `sentinel.wrap(OpenAI())` | OpenAI |
| [`anthropic-tools/`](anthropic-tools/) | Anthropic tool-use with `sentinel.wrap(Anthropic())` | Anthropic |
| [`langchain-rag/`](langchain-rag/) | RAG pipeline; groundedness/hallucination scoring | OpenAI |

## Fastest path (no keys)

```bash
pip install -e packages/sdk-python
python examples/quickstart/seed_demo.py
```

Open <http://localhost:3000>. You'll see five traces, cost/latency stats, and
alerts for the hallucination, the error, and the runaway loop.

## Other frameworks (CrewAI, AutoGen, LlamaIndex, raw SDKs)

Sentinel is framework-agnostic. There are two integration styles:

1. **Wrap the client** - if the framework exposes the underlying OpenAI/Anthropic
   client, call `sentinel.wrap(client)` once and every model call is traced
   (the [`langchain-rag`](langchain-rag/) example does this via
   `llm.root_client`).
2. **Decorate / span your code** - wrap tools and steps with
   `@sentinel.trace(kind="tool")` or `with sentinel.span("step", kind="agent")`.
   This works for *any* framework, including CrewAI tasks and AutoGen agents.

```python
import sentinel
sentinel.init(service_name="my-crew")

@sentinel.trace(kind="tool")
def search(query: str) -> list[str]:
    ...

with sentinel.span("research-crew", kind="agent"):
    ...  # your CrewAI / AutoGen workflow
```
