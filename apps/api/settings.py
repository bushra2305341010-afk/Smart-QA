"""Typed application settings.

Precedence (see docs/04-design.md §7): defaults in code → environment variables / `.env`.
Per-project settings live in the database and are layered on top later.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide configuration loaded from env vars (prefix-free, see .env.example)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    saq_env: Literal["dev", "test", "prod"] = "dev"
    database_url: str | None = None
    migration_database_url: str | None = None
    worker_database_url: str | None = None  # saq_worker login (system role, ADR-012)
    jwt_private_key: SecretStr | None = None  # Ed25519 PEM; required when SAQ_ENV=prod
    redis_url: str | None = None
    s3_endpoint: str | None = None
    s3_bucket: str = "evidence"
    s3_access_key: str | None = None
    s3_secret_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    saq_default_model: str = "claude-opus-5-5"
    saq_model_policy: Literal["local-only", "external-redacted", "external-code"] = (
        "external-redacted"
    )
    local_model_url: str | None = None
    local_model_name: str = "qwen3:8b"
    # USD per million tokens for SAQ_DEFAULT_MODEL; verify on the provider's price page.
    model_price_input_per_mtok: float | None = None
    model_price_output_per_mtok: float | None = None
    model_price_cache_read_per_mtok: float | None = None
    github_token: SecretStr | None = None  # tracker filing (N21); never stored in the DB
    rate_limit_backend: Literal["memory", "redis"] = "memory"
    rate_login_per_ip_per_min: int = Field(default=20, ge=1)
    rate_requests_per_user_per_min: int = Field(default=600, ge=1)
    rate_job_starts_per_project_per_min: int = Field(default=30, ge=1)
    saq_telemetry: Literal["off", "on"] = "off"
    saq_budget_monthly_usd: float = Field(default=20.0, ge=0)
    log_level: str = "info"


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance."""
    return Settings()
