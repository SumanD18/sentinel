"""Cost estimation and PII redaction tests."""

from __future__ import annotations

from sentinel.cost import estimate_cost, register_pricing
from sentinel.redact import redact_text, redact_value
from sentinel.types import TokenUsage


def test_cost_known_model():
    usage = TokenUsage(prompt_tokens=1000, completion_tokens=1000)
    cost = estimate_cost("gpt-4o", usage)
    assert cost == round(0.0025 + 0.01, 8)


def test_cost_prefix_match_for_dated_model():
    usage = TokenUsage(prompt_tokens=1000, completion_tokens=0)
    assert estimate_cost("gpt-4o-2024-08-06", usage) == 0.0025


def test_cost_unknown_model_returns_none():
    assert estimate_cost("totally-made-up-model", TokenUsage(100, 100)) is None


def test_register_custom_pricing():
    register_pricing("my-local-llm", 0.0, 0.0)
    assert estimate_cost("my-local-llm", TokenUsage(1000, 1000)) == 0.0


def test_redact_email_and_key():
    text = "contact me at jane.doe@example.com using sk-abcdef0123456789ABCDEF"
    out = redact_text(text)
    assert "jane.doe@example.com" not in out
    assert "[REDACTED:EMAIL]" in out
    assert "[REDACTED:API_KEY]" in out


def test_redact_nested_structure():
    payload = {"messages": [{"role": "user", "content": "ssn 123-45-6789"}]}
    out = redact_value(payload)
    assert "[REDACTED:SSN]" in out["messages"][0]["content"]
    # Structure preserved, original untouched.
    assert payload["messages"][0]["content"] == "ssn 123-45-6789"
