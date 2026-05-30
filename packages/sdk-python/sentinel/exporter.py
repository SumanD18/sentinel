"""Span exporters.

The default :class:`HTTPExporter` batches spans and ships them to the collector
on a background thread so the host application's hot path is never blocked by
network I/O. It uses only the standard library (``urllib``) to avoid pulling a
heavy HTTP dependency into every process that imports the SDK.

Exporters are pluggable: anything implementing :meth:`export` and
:meth:`shutdown` can be passed to the client.
"""

from __future__ import annotations

import abc
import json
import logging
import queue
import threading
import urllib.error
import urllib.request

from .config import SentinelConfig
from .types import Span

logger = logging.getLogger("sentinel")


class Exporter(abc.ABC):
    """Base class for span exporters."""

    @abc.abstractmethod
    def export(self, span: Span) -> None:
        """Enqueue a finished span for export. Must not block."""

    def flush(self, timeout: float | None = None) -> bool:
        """Block until queued spans are sent (or timeout). Returns success."""
        return True

    def shutdown(self) -> None:  # noqa: B027 - optional hook, default no-op
        """Flush and release resources. Idempotent."""


class NoopExporter(Exporter):
    """Drops everything. Used when the SDK is disabled."""

    def export(self, span: Span) -> None:  # noqa: D102
        return None


class ConsoleExporter(Exporter):
    """Pretty-prints spans to stdout. Handy for debugging without a collector."""

    def export(self, span: Span) -> None:  # noqa: D102
        logger.info("span %s", json.dumps(span.to_dict(), indent=2, default=str))


class _Sentinel:
    """Internal queue marker that tells the worker thread to stop."""


_SHUTDOWN = _Sentinel()


class HTTPExporter(Exporter):
    """Batches spans and POSTs them to ``{endpoint}/v1/traces``.

    A single daemon worker thread drains an in-memory queue. If the collector is
    unreachable, spans are retried with capped exponential backoff and then
    dropped (with a warning) rather than growing the queue unbounded.
    """

    def __init__(self, config: SentinelConfig) -> None:
        self._config = config
        self._url = config.endpoint.rstrip("/") + "/v1/traces"
        self._queue: queue.Queue[object] = queue.Queue(maxsize=config.max_queue_size)
        self._lock = threading.Lock()
        self._shutdown = False
        self._dropped = 0
        self._worker = threading.Thread(
            target=self._run, name="sentinel-exporter", daemon=True
        )
        self._worker.start()

    # -- public API ---------------------------------------------------------

    def export(self, span: Span) -> None:
        if self._shutdown:
            return
        try:
            self._queue.put_nowait(span)
        except queue.Full:
            # Never block the caller; account for the loss instead.
            self._dropped += 1
            if self._dropped % 100 == 1:
                logger.warning(
                    "sentinel export queue full; dropped %d spans so far",
                    self._dropped,
                )

    def flush(self, timeout: float | None = None) -> bool:
        deadline_event = threading.Event()

        # Drain by joining the queue with a timeout.
        def _join() -> None:
            self._queue.join()
            deadline_event.set()

        joiner = threading.Thread(target=_join, daemon=True)
        joiner.start()
        wait_for = timeout if timeout is not None else self._config.export_timeout_seconds
        return deadline_event.wait(wait_for)

    def shutdown(self) -> None:
        with self._lock:
            if self._shutdown:
                return
            self._shutdown = True
        try:
            self._queue.put_nowait(_SHUTDOWN)
        except queue.Full:
            pass
        self._worker.join(timeout=self._config.export_timeout_seconds)

    # -- worker -------------------------------------------------------------

    def _run(self) -> None:
        batch: list[Span] = []
        while True:
            try:
                item = self._queue.get(timeout=self._config.flush_interval_seconds)
            except queue.Empty:
                if batch:
                    self._send(batch)
                    batch = []
                continue

            if item is _SHUTDOWN:
                self._queue.task_done()
                break

            assert isinstance(item, Span)
            batch.append(item)
            self._queue.task_done()

            if len(batch) >= self._config.max_batch_size:
                self._send(batch)
                batch = []

        # Final drain on shutdown.
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                break
            if item is _SHUTDOWN:
                self._queue.task_done()
                continue
            assert isinstance(item, Span)
            batch.append(item)
            self._queue.task_done()
        if batch:
            self._send(batch)

    def _send(self, batch: list[Span]) -> None:
        payload = {
            "service_name": self._config.service_name,
            "environment": self._config.environment,
            "resource_attributes": self._config.resource_attributes,
            "spans": [span.to_dict() for span in batch],
        }
        body = json.dumps(payload, default=str).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"

        backoff = 0.5
        for attempt in range(3):
            req = urllib.request.Request(
                self._url, data=body, headers=headers, method="POST"
            )
            try:
                with urllib.request.urlopen(
                    req, timeout=self._config.export_timeout_seconds
                ) as resp:
                    if 200 <= resp.status < 300:
                        return
                    logger.warning(
                        "sentinel collector returned %s for %d spans",
                        resp.status,
                        len(batch),
                    )
                    return
            except urllib.error.URLError as exc:
                if attempt == 2:
                    logger.warning(
                        "sentinel export failed after retries (%s); dropping %d spans",
                        exc,
                        len(batch),
                    )
                    return
                # Crude but effective backoff without importing time.sleep jitter.
                threading.Event().wait(backoff)
                backoff *= 2
