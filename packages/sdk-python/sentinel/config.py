"""Runtime configuration for the Sentinel SDK.

Values resolve in this order: explicit argument > environment variable >
built-in default. This keeps local development zero-config while allowing CI and
production to override everything through the environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .redact import Redactor, redact_text


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass
class SentinelConfig:
    """All knobs for the SDK. Construct directly or via :func:`from_env`."""

    # Where to ship traces. The collector exposes POST /v1/traces.
    endpoint: str = "http://localhost:8000"
    api_key: str | None = None

    # Logical service name shown in the dashboard.
    service_name: str = "default"
    environment: str = "development"

    # When False, the SDK becomes a no-op: no spans are created or exported.
    enabled: bool = True

    # Capture full prompt/response payloads. Disable to record only metadata.
    capture_content: bool = True

    # Redact PII from payloads before they leave the process.
    redact_pii: bool = True
    redactor: Redactor = redact_text

    # Export tuning.
    flush_interval_seconds: float = 2.0
    max_queue_size: int = 10_000
    max_batch_size: int = 256
    export_timeout_seconds: float = 10.0

    # Sampling: 1.0 = keep everything, 0.0 = drop everything.
    sample_rate: float = 1.0

    # If True, errors inside the SDK never propagate to the host application.
    fail_silently: bool = True

    # Extra static attributes attached to every span (e.g. region, version).
    resource_attributes: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls, **overrides) -> SentinelConfig:
        cfg = cls(
            endpoint=os.getenv("SENTINEL_ENDPOINT", cls.endpoint),
            api_key=os.getenv("SENTINEL_API_KEY"),
            service_name=os.getenv("SENTINEL_SERVICE_NAME", cls.service_name),
            environment=os.getenv("SENTINEL_ENVIRONMENT", cls.environment),
            enabled=_env_bool("SENTINEL_ENABLED", cls.enabled),
            capture_content=_env_bool("SENTINEL_CAPTURE_CONTENT", cls.capture_content),
            redact_pii=_env_bool("SENTINEL_REDACT_PII", cls.redact_pii),
            flush_interval_seconds=_env_float(
                "SENTINEL_FLUSH_INTERVAL", cls.flush_interval_seconds
            ),
            max_queue_size=_env_int("SENTINEL_MAX_QUEUE_SIZE", cls.max_queue_size),
            max_batch_size=_env_int("SENTINEL_MAX_BATCH_SIZE", cls.max_batch_size),
            sample_rate=_env_float("SENTINEL_SAMPLE_RATE", cls.sample_rate),
        )
        for key, value in overrides.items():
            if not hasattr(cfg, key):
                raise TypeError(f"Unknown SentinelConfig field: {key!r}")
            setattr(cfg, key, value)
        return cfg
