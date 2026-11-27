"""Fail-fast production configuration (docs/23)."""

from typing import Any

import pytest

from apps.api.main import create_app
from apps.api.settings import Settings, check_production, get_settings

GOOD: dict[str, Any] = {
    "saq_env": "prod",
    "database_url": "postgresql+psycopg://saq_app:Strong-pass-1@db:5432/saq",
    "worker_database_url": "postgresql+psycopg://saq_worker:Strong-pass-2@db:5432/saq",
    "redis_url": "redis://redis:6379/0",
    "jwt_private_key": "pem",
    "s3_endpoint": "https://s3.example.com",
    "s3_access_key": "ak",
    "s3_secret_key": "sk",
    "public_url": "https://qa.example.com",
    "rate_limit_backend": "redis",
    "anthropic_api_key": "key",
}


def make(**kw: Any) -> Settings:
    return Settings(_env_file=None, **{**GOOD, **kw})  # type: ignore[call-arg]


def test_good_prod_and_dev_have_no_problems() -> None:
    assert make().production_problems() == []
    assert Settings(_env_file=None).production_problems() == []  # type: ignore[call-arg]
    check_production(make())


@pytest.mark.parametrize(
    ("override", "problem"),
    [
        ({"database_url": None}, "DATABASE_URL is required"),
        ({"jwt_private_key": None}, "JWT_PRIVATE_KEY is required"),
        ({"s3_secret_key": None}, "S3_SECRET_KEY is required"),
        ({"rate_limit_backend": "memory"}, "RATE_LIMIT_BACKEND must be redis"),
        ({"public_url": "http://qa.example.com"}, "PUBLIC_URL must be https://"),
        ({"database_url": "postgresql+psycopg://saq_app:saq_dev_password@db/saq"},
         "DATABASE_URL uses the development password"),
        ({"worker_database_url": "postgresql+psycopg://saq_worker:saq_dev_password@db/saq"},
         "WORKER_DATABASE_URL uses the development password"),
        ({"database_url": "postgresql+psycopg://saq_migrator:x@db/saq"}, "runtime role saq_app"),
        ({"anthropic_api_key": None}, "Set ANTHROPIC_API_KEY or LOCAL_MODEL_URL"),
        ({"saq_model_policy": "local-only"}, "LOCAL_MODEL_URL is required"),
    ],
)  # fmt: skip
def test_each_problem(override: dict[str, Any], problem: str) -> None:
    problems = make(**override).production_problems()
    assert any(problem in p for p in problems), problems
    with pytest.raises(SystemExit, match="Refusing to start"):
        check_production(make(**override))


def test_app_refuses_to_start_misconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAQ_ENV", "prod")
    monkeypatch.delenv("JWT_PRIVATE_KEY", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(SystemExit, match="JWT_PRIVATE_KEY is required"):
            create_app()
    finally:
        get_settings.cache_clear()


def test_signer_accepts_escaped_one_line_pem() -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from apps.api.auth.tokens import JwtSigner

    pem = (
        Ed25519PrivateKey.generate()
        .private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        .decode()
    )
    one_line = pem.strip().replace("\n", "\\n")
    assert JwtSigner.from_pem(one_line) is not None
    assert JwtSigner.from_pem(pem) is not None


def test_empty_env_values_mean_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_PRICE_INPUT_PER_MTOK", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.model_price_input_per_mtok is None and s.anthropic_api_key is None
