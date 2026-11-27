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
    saq_encryption_key: SecretStr | None = None  # base64 32 bytes; AES-256-GCM for secrets at rest
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
    embedding_url: str | None = None  # internal OpenAI-compatible server (T-204)
    embedding_model: str = "bge-m3"
    # USD per million tokens for SAQ_DEFAULT_MODEL; verify on the provider's price page.
    model_price_input_per_mtok: float | None = None
    model_price_output_per_mtok: float | None = None
    model_price_cache_read_per_mtok: float | None = None
    git_read_token: SecretStr | None = None  # read-only token for private repo import (T-202)
    github_token: SecretStr | None = None  # tracker filing (N21); never stored in the DB
    breach_check_mode: Literal["off", "online", "offline"] = "off"
    breach_hash_file: str | None = None  # offline mode: SHA-1 per line
    rate_limit_backend: Literal["memory", "redis"] = "memory"
    rate_login_per_ip_per_min: int = Field(default=20, ge=1)
    rate_requests_per_user_per_min: int = Field(default=600, ge=1)
    rate_job_starts_per_project_per_min: int = Field(default=30, ge=1)
    saq_telemetry: Literal["off", "on"] = "off"
    saq_budget_monthly_usd: float = Field(default=20.0, ge=0)
    log_level: str = "info"
    public_url: str | None = None  # https://qa.example.com (used in links and CORS checks)

    def production_problems(self) -> list[str]:
        """Settings that are unsafe or missing for SAQ_ENV=prod (empty list = OK).

        Every process calls `check_production` at start so a bad deployment fails fast
        instead of running with an ephemeral signing key, in-memory rate limits or no storage.
        """
        if self.saq_env != "prod":
            return []
        problems = []
        required = {
            "DATABASE_URL": self.database_url,
            "REDIS_URL": self.redis_url,
            "JWT_PRIVATE_KEY": self.jwt_private_key,
            "S3_ENDPOINT": self.s3_endpoint,
            "S3_ACCESS_KEY": self.s3_access_key,
            "S3_SECRET_KEY": self.s3_secret_key,
            "PUBLIC_URL": self.public_url,
        }
        problems += [f"{name} is required" for name, value in required.items() if not value]
        if self.rate_limit_backend != "redis":
            problems.append("RATE_LIMIT_BACKEND must be redis (limits must hold across replicas)")
        if self.public_url and not self.public_url.startswith("https://"):
            problems.append("PUBLIC_URL must be https:// (cookies are Secure in prod)")
        for name, url in (
            ("DATABASE_URL", self.database_url),
            ("WORKER_DATABASE_URL", self.worker_database_url),
        ):
            if url and "saq_dev_password" in url:
                problems.append(f"{name} uses the development password")
        if self.database_url and "saq_migrator" in self.database_url:
            problems.append("DATABASE_URL must use the runtime role saq_app, not saq_migrator")
        if self.saq_model_policy == "local-only" and not self.local_model_url:
            problems.append("LOCAL_MODEL_URL is required for SAQ_MODEL_POLICY=local-only")
        elif not (self.anthropic_api_key or self.local_model_url):
            problems.append("Set ANTHROPIC_API_KEY or LOCAL_MODEL_URL for the model policy")
        return problems


def check_production(settings: Settings) -> None:
    problems = settings.production_problems()
    if problems:
        raise SystemExit("Refusing to start (SAQ_ENV=prod):\n- " + "\n- ".join(problems))


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance."""
    return Settings()
