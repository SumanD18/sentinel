"""Anthropic tool-use, instrumented by Sentinel.

`sentinel.wrap` detects the Anthropic client automatically and traces every
`messages.create` call (streaming or not) with token usage and cost.

Run:
    pip install -e ../../packages/sdk-python "anthropic>=0.25"
    export ANTHROPIC_API_KEY=sk-ant-...
    export SENTINEL_ENDPOINT=http://localhost:8000
    python tools.py
"""

from __future__ import annotations

import os

import sentinel

try:
    from anthropic import Anthropic
except ImportError:  # pragma: no cover
    raise SystemExit("Install the Anthropic SDK: pip install 'anthropic>=0.25'")

sentinel.init(service_name="anthropic-tools", environment="demo")
client = sentinel.wrap(Anthropic())

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")

TOOLS = [
    {
        "name": "calculator",
        "description": "Evaluate a basic arithmetic expression.",
        "input_schema": {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
    }
]


@sentinel.trace(kind="tool", name="calculator")
def calculator(expression: str) -> str:
    # Tiny safe arithmetic evaluator (no builtins).
    allowed = set("0123456789+-*/(). ")
    if not set(expression) <= allowed:
        return "error: unsupported characters"
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))  # noqa: S307
    except Exception as exc:  # pragma: no cover
        return f"error: {exc}"


def run(question: str) -> str:
    with sentinel.span("math-agent", kind="agent", input=question):
        messages = [{"role": "user", "content": question}]
        for _ in range(5):
            resp = client.messages.create(
                model=MODEL, max_tokens=1024, tools=TOOLS, messages=messages
            )
            messages.append({"role": "assistant", "content": resp.content})

            tool_uses = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
            if not tool_uses:
                texts = [getattr(b, "text", "") for b in resp.content]
                return "".join(texts)

            results = []
            for tu in tool_uses:
                out = calculator(**tu.input)
                results.append(
                    {"type": "tool_result", "tool_use_id": tu.id, "content": out}
                )
            messages.append({"role": "user", "content": results})
        return "Gave up after too many tool calls."


if __name__ == "__main__":
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("Set ANTHROPIC_API_KEY to run this example.")
    print("\nClaude:", run("What is (1234 * 17) + 9? Use the calculator."))
    sentinel.flush(timeout=10)
    print("\nTrace sent. Open the dashboard to inspect it.")
