"""A tiny RAG pipeline with LangChain, instrumented by Sentinel.

LangChain wraps the OpenAI client internally, so the cleanest integration is:
  1. `sentinel.wrap` the underlying OpenAI client that ChatOpenAI uses, and
  2. use `sentinel.span(kind="retrieval")` around your retriever so the dashboard
     can compute groundedness (answer-vs-context overlap) and flag hallucinations.

Run:
    pip install -e ../../packages/sdk-python langchain-openai langchain-core "openai>=1.0"
    export OPENAI_API_KEY=sk-...
    export SENTINEL_ENDPOINT=http://localhost:8000
    python rag.py
"""

from __future__ import annotations

import os

import sentinel

try:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover
    raise SystemExit(
        "Install LangChain: pip install langchain-openai langchain-core 'openai>=1.0'"
    )

sentinel.init(service_name="langchain-rag", environment="demo")

# A toy in-memory "vector store".
DOCS = [
    "Sentinel is an open-source observability and trust layer for AI agents.",
    "Sentinel computes a trust score for every LLM output using local evaluators.",
    "Sentinel exports OpenTelemetry-compatible traces and Prometheus metrics.",
]


@sentinel.trace(kind="retrieval", name="retrieve")
def retrieve(query: str, k: int = 2) -> list[str]:
    """Naive keyword retriever (stand-in for a real vector search)."""
    q = set(query.lower().split())
    scored = sorted(DOCS, key=lambda d: len(q & set(d.lower().split())), reverse=True)
    return scored[:k]


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY to run this example.")

    llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0)
    # Instrument the OpenAI client LangChain uses under the hood.
    if getattr(llm, "root_client", None) is not None:
        sentinel.wrap(llm.root_client)

    question = "What does Sentinel export for monitoring?"
    with sentinel.span("rag-pipeline", kind="chain", input=question):
        context = retrieve(question)
        prompt = [
            SystemMessage(
                content="Answer using ONLY the context. If unsure, say so.\n\n"
                + "\n".join(f"- {c}" for c in context)
            ),
            HumanMessage(content=question),
        ]
        answer = llm.invoke(prompt)
        print("\nAnswer:", answer.content)

    sentinel.flush(timeout=10)
    print("\nTrace sent. Open the dashboard to inspect groundedness.")


if __name__ == "__main__":
    main()
