"""OpenTelemetry exporter.

Maps finished Sentinel spans onto OpenTelemetry spans and ships them through any
OTLP-compatible backend (Grafana Tempo, Datadog, Honeycomb, an OTel Collector,
etc.). LLM spans are annotated with the OpenTelemetry GenAI semantic conventions
(``gen_ai.*``) so they render correctly in OTel-aware tooling.

Requires the optional dependency group::

    pip install "sentinel-llm[otel]"

Usage::

    import sentinel
    from sentinel.exporters import OTelExporter

    sentinel.init(exporter=OTelExporter())            # OTel only
    # or send to both the Sentinel collector and OTel:
    from sentinel.exporter import HTTPExporter, MultiExporter
    cfg = sentinel.SentinelConfig.from_env()
    sentinel.init(cfg, exporter=MultiExporter(HTTPExporter(cfg), OTelExporter()))
"""

from __future__ import annotations

import logging
import os
from typing import Any

from ..exporter import Exporter
from ..types import Span, SpanKind, SpanStatus

logger = logging.getLogger("sentinel")

_IMPORT_HINT = (
    "OTelExporter requires OpenTelemetry. Install it with: "
    'pip install "sentinel-llm[otel]"'
)


def _to_trace_id(hex_id: str) -> int:
    # Sentinel trace ids are 32-hex-char uuid4s == 128 bits, exactly an OTel trace id.
    try:
        value = int(hex_id[:32], 16)
    except (ValueError, TypeError):
        value = 0
    return value or 1


def _to_span_id(hex_id: str) -> int:
    # OTel span ids are 64-bit; take the high 16 hex chars of our id.
    try:
        value = int(hex_id[:16], 16)
    except (ValueError, TypeError):
        value = 0
    return value or 1


class OTelExporter(Exporter):
    """Exports Sentinel spans to OpenTelemetry.

    Pass a custom OTel ``SpanExporter`` (e.g. ``ConsoleSpanExporter`` or an
    in-memory exporter for tests); otherwise an OTLP/HTTP exporter is created
    from the standard ``OTEL_EXPORTER_OTLP_*`` environment variables.
    """

    def __init__(
        self,
        otel_exporter: Any = None,
        *,
        service_name: str | None = None,
        resource_attributes: dict | None = None,
    ) -> None:
        try:
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.util.instrumentation import InstrumentationScope
        except ImportError as exc:  # pragma: no cover - exercised only without otel
            raise ImportError(_IMPORT_HINT) from exc

        from .. import __version__

        if otel_exporter is None:
            otel_exporter = self._default_exporter()
        self._exporter = otel_exporter

        service = service_name or os.getenv("SENTINEL_SERVICE_NAME") or "sentinel"
        attrs: dict[str, Any] = {"service.name": service}
        if resource_attributes:
            attrs.update(resource_attributes)
        self._resource = Resource.create(attrs)
        self._scope = InstrumentationScope("sentinel", __version__)

    @staticmethod
    def _default_exporter() -> Any:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )
        except ImportError as exc:  # pragma: no cover
            raise ImportError(_IMPORT_HINT) from exc
        return OTLPSpanExporter()

    def _otel_kind(self, kind: SpanKind) -> Any:
        from opentelemetry.trace import SpanKind as OTelSpanKind

        if kind in (SpanKind.LLM, SpanKind.EMBEDDING, SpanKind.RETRIEVAL):
            return OTelSpanKind.CLIENT
        return OTelSpanKind.INTERNAL

    def _attributes(self, span: Span) -> dict:
        attrs: dict[str, Any] = {"sentinel.kind": span.kind.value}
        if span.provider:
            attrs["gen_ai.system"] = span.provider
        if span.model:
            attrs["gen_ai.request.model"] = span.model
        if span.usage:
            attrs["gen_ai.usage.input_tokens"] = span.usage.prompt_tokens
            attrs["gen_ai.usage.output_tokens"] = span.usage.completion_tokens
            attrs["gen_ai.usage.total_tokens"] = span.usage.total_tokens
        if span.cost_usd is not None:
            attrs["sentinel.cost_usd"] = span.cost_usd
        # trust_score is set server-side; include it only if present on the span.
        trust_score = getattr(span, "trust_score", None)
        if trust_score is not None:
            attrs["sentinel.trust_score"] = trust_score
        # Flatten primitive attributes; OTel attribute values must be scalars
        # or homogeneous scalar sequences.
        for key, value in (span.attributes or {}).items():
            if isinstance(value, (str, bool, int, float)):
                attrs[f"sentinel.{key}"] = value
        return attrs

    def _build(self, span: Span) -> Any:
        from opentelemetry.sdk.trace import ReadableSpan
        from opentelemetry.trace import SpanContext, TraceFlags
        from opentelemetry.trace.status import Status, StatusCode

        trace_id = _to_trace_id(span.trace_id)
        context = SpanContext(
            trace_id=trace_id,
            span_id=_to_span_id(span.span_id),
            is_remote=False,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )
        parent = None
        if span.parent_span_id:
            parent = SpanContext(
                trace_id=trace_id,
                span_id=_to_span_id(span.parent_span_id),
                is_remote=True,
                trace_flags=TraceFlags(TraceFlags.SAMPLED),
            )

        if span.status is SpanStatus.ERROR:
            status = Status(StatusCode.ERROR, span.status_message or "error")
        elif span.status is SpanStatus.OK:
            status = Status(StatusCode.OK)
        else:
            status = Status(StatusCode.UNSET)

        return ReadableSpan(
            name=span.name,
            context=context,
            parent=parent,
            resource=self._resource,
            attributes=self._attributes(span),
            kind=self._otel_kind(span.kind),
            status=status,
            start_time=span.start_time_ns,
            end_time=span.end_time_ns or span.start_time_ns,
            instrumentation_scope=self._scope,
        )

    # -- Exporter API -------------------------------------------------------

    def export(self, span: Span) -> None:
        try:
            self._exporter.export([self._build(span)])
        except Exception:  # pragma: no cover - never break the host app
            logger.exception("sentinel: OTel export failed")

    def flush(self, timeout: float | None = None) -> bool:
        force_flush = getattr(self._exporter, "force_flush", None)
        if callable(force_flush):
            try:
                if timeout is not None:
                    return bool(force_flush(timeout_millis=int(timeout * 1000)))
                return bool(force_flush())
            except Exception:  # pragma: no cover
                return False
        return True

    def shutdown(self) -> None:
        shutdown = getattr(self._exporter, "shutdown", None)
        if callable(shutdown):
            try:
                shutdown()
            except Exception:  # pragma: no cover
                logger.exception("sentinel: OTel exporter shutdown failed")
