"""The tracer: creates spans, wires up parent/child context, and hands finished
spans to the exporter.

A :class:`Tracer` is cheap; it holds a config and an exporter. Most users never
touch it directly - they call the module-level helpers in ``sentinel`` which
delegate to a process-global default tracer.
"""

from __future__ import annotations

import logging
import random
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from . import context as ctx
from .config import SentinelConfig
from .cost import estimate_cost
from .exporter import Exporter, HTTPExporter, NoopExporter
from .redact import redact_value
from .types import Span, SpanKind, TokenUsage

logger = logging.getLogger("sentinel")


class Tracer:
    """Creates and exports spans according to a :class:`SentinelConfig`."""

    def __init__(
        self, config: SentinelConfig | None = None, exporter: Exporter | None = None
    ) -> None:
        self.config = config or SentinelConfig.from_env()
        if exporter is not None:
            self._exporter: Exporter = exporter
        elif self.config.enabled:
            self._exporter = HTTPExporter(self.config)
        else:
            self._exporter = NoopExporter()

    # -- sampling -----------------------------------------------------------

    def _should_sample(self) -> bool:
        rate = self.config.sample_rate
        if rate >= 1.0:
            return True
        if rate <= 0.0:
            return False
        return random.random() < rate

    # -- span lifecycle -----------------------------------------------------

    def start_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.UNKNOWN,
        *,
        attributes: dict[str, Any] | None = None,
        input: Any = None,
    ) -> Span:
        """Create a span as a child of the current context span.

        The returned span is *not* yet in scope; use :meth:`span` for the common
        context-managed case, or call :meth:`end_span` manually.
        """
        parent = ctx.get_current_span()
        trace_id = parent.trace_id if parent else None
        span = Span(name=name, kind=kind)
        if trace_id:
            span.trace_id = trace_id
        span.parent_span_id = parent.span_id if parent else None

        if attributes:
            span.attributes.update(attributes)
        if self.config.resource_attributes:
            span.attributes.setdefault("resource", {}).update(
                self.config.resource_attributes
            )
        if input is not None and self.config.capture_content:
            span.input = self._prepare(input)
        return span

    def end_span(self, span: Span) -> None:
        """Finalize a span: compute cost, end it, and export it."""
        try:
            if span.kind is SpanKind.LLM and span.cost_usd is None:
                span.cost_usd = estimate_cost(span.model, span.usage)
            span.end()
            if not self.config.enabled:
                return
            self._exporter.export(span)
        except Exception:  # pragma: no cover - defensive
            if not self.config.fail_silently:
                raise
            logger.exception("sentinel: failed to end span %s", span.name)

    @contextmanager
    def span(
        self,
        name: str,
        kind: SpanKind = SpanKind.UNKNOWN,
        *,
        attributes: dict[str, Any] | None = None,
        input: Any = None,
    ) -> Iterator[Span]:
        """Context manager that opens a span, makes it current, and closes it.

        Exceptions are recorded on the span and re-raised so application
        behaviour is unchanged.
        """
        if not self._should_sample():
            # Still yield a span so calling code works, but never export it.
            yield Span(name=name, kind=kind)
            return

        span = self.start_span(name, kind, attributes=attributes, input=input)
        token = ctx.set_current_span(span)
        try:
            yield span
        except BaseException as exc:
            span.record_exception(exc)
            raise
        finally:
            ctx.reset_current_span(token)
            self.end_span(span)

    # -- helpers ------------------------------------------------------------

    def set_output(self, span: Span, output: Any) -> None:
        if self.config.capture_content:
            span.output = self._prepare(output)

    def set_usage(
        self,
        span: Span,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
    ) -> None:
        span.usage = TokenUsage(prompt_tokens, completion_tokens, total_tokens)

    def _prepare(self, value: Any) -> Any:
        """Apply PII redaction (if enabled) before a payload is stored."""
        if self.config.redact_pii:
            try:
                return redact_value(value, self.config.redactor)
            except Exception:  # pragma: no cover - never break on redaction
                logger.debug("sentinel: redaction failed; storing raw value")
        return value

    def flush(self, timeout: float | None = None) -> bool:
        return self._exporter.flush(timeout)

    def shutdown(self) -> None:
        self._exporter.shutdown()
