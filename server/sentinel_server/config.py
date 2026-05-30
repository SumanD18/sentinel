"""Server configuration, loaded from environment variables.

Defaults target a zero-config local run against SQLite. Set ``DATABASE_URL`` to
a Postgres DSN for production.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SENTINEL_", env_file=".env", extra="ignore")

    # SQLite by default; e.g. postgresql+asyncpg://user:pass@host/db for Postgres.
    database_url: str = "sqlite+aiosqlite:///./sentinel.db"

    # Comma-separated API keys. Empty => auth disabled (local dev default).
    api_keys: str = ""

    # CORS origins for the dashboard.
    cors_origins: str = "*"

    # Run the inline evaluator suite during ingestion.
    enable_evaluators: bool = True

    # Trust score at/below which an alert is raised.
    alert_trust_threshold: float = 0.5

    # Max LLM calls in a single trace before a runaway-loop alert fires.
    runaway_span_threshold: int = 50

    # Retention: delete traces older than this many days (0 = keep forever).
    retention_days: int = 0

    log_level: str = "INFO"

    @property
    def api_key_set(self) -> set[str]:
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}

    @property
    def auth_enabled(self) -> bool:
        return bool(self.api_key_set)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()] or ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
