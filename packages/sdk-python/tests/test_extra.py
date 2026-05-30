"""Decorator options and HTTP exporter retry/queue behavior."""

from __future__ import annotations

import urllib.error

import pytest

from sentinel.config import SentinelConfig
from sentinel.exporter import HTTPExporter
from sentinel.types import Span, SpanStatus


def test_decorator_capture_args_false(tracer, exporter, monkeypatch):
    import sentinel

    monkeypatch.setattr(sentinel, "_default_tracer", tracer)

    @sentinel.trace(name="masked", capture_args=False)
    def masked(x, y):
        return x + y

    assert masked(10, 20) == 30
    span = exporter.by_name("masked")[0]
    assert span.input is None
    assert span.output == 30


@pytest.mark.asyncio
async def test_async_decorator_records_exception(tracer, exporter, monkeypatch):
    import sentinel

    monkeypatch.setattr(sentinel, "_default_tracer", tracer)

    @sentinel.trace(name="afail")
    async def afail():
        raise ValueError("nope")

    with pytest.raises(ValueError):
        await afail()
    span = exporter.by_name("afail")[0]
    assert span.status is SpanStatus.ERROR
    assert "ValueError" in span.status_message


class _Resp:
    def __init__(self, status: int):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _make_exporter() -> HTTPExporter:
    # Tiny backoff path is exercised via the worker; we call _send directly.
    return HTTPExporter(SentinelConfig(endpoint="http://localhost:9", export_timeout_seconds=0.1))


def test_http_exporter_send_success(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append(1)
        return _Resp(200)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    exp = _make_exporter()
    try:
        exp._send([Span(name="x")])
        assert len(calls) == 1  # success on first try, no retries
    finally:
        exp.shutdown()


def test_http_exporter_retries_then_drops(monkeypatch):
    # Build the exporter (starts its worker thread) BEFORE patching Event.wait,
    # so the thread-start handshake isn't affected; the patch only skips the
    # retry backoff sleeps inside _send.
    exp = _make_exporter()
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append(1)
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("threading.Event.wait", lambda self, timeout=None: True)
    try:
        exp._send([Span(name="x")])  # must not raise; drops after 3 attempts
        assert len(calls) == 3
    finally:
        exp.shutdown()


def test_http_exporter_queue_full_increments_dropped(monkeypatch):
    cfg = SentinelConfig(
        endpoint="http://localhost:9", max_queue_size=1, export_timeout_seconds=0.2
    )
    exp = HTTPExporter(cfg)
    try:
        # Stop the worker from draining so the queue stays full.
        monkeypatch.setattr(exp._queue, "put_nowait", _raise_full)
        exp.export(Span(name="a"))
        assert exp._dropped >= 1
    finally:
        exp.shutdown()


def _raise_full(*_a, **_k):
    import queue

    raise queue.Full
