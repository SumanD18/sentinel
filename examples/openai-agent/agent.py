"""A minimal tool-using OpenAI agent, fully instrumented by Sentinel.

What to notice:
  * `sentinel.wrap(client)` - every chat completion becomes an LLM span with
    tokens, cost, and a trust score, with zero changes to how you call OpenAI.
  * `@sentinel.trace(kind="tool")` - your own tools show up as nested spans.
  * The whole multi-step run is a single trace you can replay in the dashboard.

Run:
    pip install -e ../../packages/sdk-python "openai>=1.0"
    export OPENAI_API_KEY=sk-...
    export SENTINEL_ENDPOINT=http://localhost:8000
    python agent.py
"""

from __future__ import annotations

import json
import os

import sentinel

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    raise SystemExit("Install the OpenAI SDK: pip install 'openai>=1.0'")

sentinel.init(service_name="openai-agent", environment="demo")
client = sentinel.wrap(OpenAI())

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


@sentinel.trace(kind="tool", name="get_weather")
def get_weather(city: str) -> dict:
    """Pretend weather tool. In real life this hits an API."""
    fake = {"San Francisco": 17, "Tokyo": 22, "Berlin": 12}
    return {"city": city, "temp_c": fake.get(city, 20), "conditions": "clear"}


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    }
]


def run(question: str) -> str:
    with sentinel.span("weather-agent", kind="agent", input=question):
        messages = [{"role": "user", "content": question}]
        for _ in range(5):  # cap the agent loop
            resp = client.chat.completions.create(
                model=MODEL, messages=messages, tools=TOOLS
            )
            msg = resp.choices[0].message
            messages.append(msg.model_dump())

            if not msg.tool_calls:
                return msg.content or ""

            for call in msg.tool_calls:
                args = json.loads(call.function.arguments)
                result = get_weather(**args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result),
                    }
                )
        return "Gave up after too many tool calls."


if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY to run this example.")
    answer = run("What's the weather in Tokyo and should I bring a jacket?")
    print("\nAgent:", answer)
    sentinel.flush(timeout=10)
    print("\nTrace sent. Open the dashboard to inspect it.")
