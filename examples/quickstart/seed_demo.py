"""Populate a running Sentinel server with realistic demo traces.

No API keys, no provider SDKs - this uses Sentinel's manual span API to fabricate
a handful of agent runs (a healthy one, a RAG run, an error, a hallucination, and
a runaway loop) so you can see the dashboard light up immediately:

    # terminal 1
    docker compose up --build
    # terminal 2
    pip install -e packages/sdk-python
    python examples/quickstart/seed_demo.py

Then open http://localhost:3000.
"""

from __future__ import annotations

import os
import time

import sentinel
from sentinel import SpanKind
from sentinel.types import TokenUsage

ENDPOINT = os.getenv("SENTINEL_ENDPOINT", "http://localhost:8000")


def llm_span(name: str, model: str, prompt: str, completion: str, p_tok: int, c_tok: int):
    """Open an LLM span and stamp it like a real provider wrapper would."""
    tracer = sentinel.get_tracer()
    cm = sentinel.span(name, SpanKind.LLM, input=prompt)
    span = cm.__enter__()
    span.model = model
    span.provider = "openai" if model.startswith(("gpt", "o1")) else "anthropic"
    span.usage = TokenUsage(prompt_tokens=p_tok, completion_tokens=c_tok)
    tracer.set_output(span, completion)
    time.sleep(0.02)
    cm.__exit__(None, None, None)


def healthy_run() -> None:
    with sentinel.span("support-agent", SpanKind.AGENT, input="How do I reset my password?"):
        with sentinel.span("classify-intent", SpanKind.CHAIN):
            llm_span(
                "openai.chat.completions",
                "gpt-4o-mini",
                "Classify: How do I reset my password?",
                "intent: account_recovery",
                64,
                12,
            )
        llm_span(
            "openai.chat.completions",
            "gpt-4o",
            "Answer the password reset question.",
            "Go to Settings → Security → Reset password and follow the email link.",
            520,
            48,
        )


def rag_run() -> None:
    with sentinel.span("docs-rag", SpanKind.AGENT, input="What is our refund policy?"):
        with sentinel.span("retrieve", SpanKind.RETRIEVAL) as r:
            r.output = [
                "Refunds are available within 30 days of purchase.",
                "Digital goods are non-refundable once downloaded.",
            ]
        llm_span(
            "openai.chat.completions",
            "gpt-4o",
            "Using the context, answer the refund question.",
            "You can request a refund within 30 days of purchase, except for "
            "downloaded digital goods.",
            780,
            36,
        )


def hallucination_run() -> None:
    """An answer that ignores its context - should get a low trust score."""
    with sentinel.span("flaky-rag", SpanKind.AGENT, input="When was the company founded?"):
        with sentinel.span("retrieve", SpanKind.RETRIEVAL) as r:
            r.output = ["The company was founded in 2019 in Berlin."]
        llm_span(
            "openai.chat.completions",
            "gpt-4o",
            "Answer using the provided context only.",
            "I'm not sure, but as an AI I cannot verify this. It may have been 1847.",
            300,
            40,
        )


def error_run() -> None:
    try:
        with sentinel.span("payment-agent", SpanKind.AGENT):
            with sentinel.span("charge-card", SpanKind.TOOL):
                raise RuntimeError("payment gateway timeout after 30s")
    except RuntimeError:
        pass


def runaway_run() -> None:
    with sentinel.span("looping-agent", SpanKind.AGENT, input="Plan a trip"):
        for i in range(55):  # exceeds the runaway threshold (default 50)
            llm_span(
                "openai.chat.completions",
                "gpt-4o-mini",
                f"step {i}: think",
                f"thinking about step {i}...",
                40,
                20,
            )


def main() -> None:
    sentinel.init(endpoint=ENDPOINT, service_name="demo", environment="production")
    print(f"Seeding demo traces to {ENDPOINT} ...")
    healthy_run()
    rag_run()
    hallucination_run()
    error_run()
    runaway_run()
    sentinel.flush(timeout=10)
    print("Done. Open http://localhost:3000 to explore the traces and alerts.")


if __name__ == "__main__":
    main()
