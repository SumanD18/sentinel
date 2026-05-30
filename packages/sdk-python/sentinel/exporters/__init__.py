"""Optional, dependency-heavy exporters (kept out of the core import path).

The OpenTelemetry exporter lives here so the core SDK stays dependency-free; it
is imported lazily and only requires ``opentelemetry-sdk`` when actually used.
"""

from __future__ import annotations

__all__ = ["OTelExporter"]


def __getattr__(name: str):  # PEP 562 lazy attribute access
    if name == "OTelExporter":
        from .otel import OTelExporter

        return OTelExporter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
