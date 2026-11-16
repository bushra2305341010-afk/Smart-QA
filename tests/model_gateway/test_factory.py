import pytest

from packages.model_gateway.anthropic_adapter import AnthropicProvider
from packages.model_gateway.factory import (
    LOCAL_PRICES,
    PolicyViolationError,
    build_provider,
    is_internal_url,
)
from packages.model_gateway.local_adapter import LocalProvider


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:11434/v1",
        "http://127.0.0.1:8080/v1",
        "http://[::1]:8000/v1",
        "http://host.docker.internal:11434/v1",
        "http://ollama:11434/v1",  # single-label Compose service name
        "http://10.0.0.5/v1",
        "http://192.168.1.20:8000/v1",
        "http://gpu-box.lan/v1",
        "http://models.corp.internal/v1",
    ],
)
def test_internal_urls_are_allowed(url: str) -> None:
    assert is_internal_url(url)


@pytest.mark.parametrize(
    "url", ["https://api.example.com/v1", "http://8.8.8.8/v1", "not a url", "http:///v1"]
)
def test_external_urls_are_rejected(url: str) -> None:
    assert not is_internal_url(url)


def test_local_only_builds_local_provider() -> None:
    p = build_provider("local-only", local_url="http://localhost:11434/v1", local_model="qwen3:8b")
    assert isinstance(p, LocalProvider) and p.model == "qwen3:8b"


def test_local_only_without_url_is_a_policy_violation() -> None:
    with pytest.raises(PolicyViolationError, match="LOCAL_MODEL_URL"):
        build_provider("local-only", local_url=None, local_model="m")


def test_local_only_with_external_url_is_a_policy_violation() -> None:
    with pytest.raises(PolicyViolationError, match="not an internal host"):
        build_provider("local-only", local_url="https://api.example.com/v1", local_model="m")


@pytest.mark.parametrize("policy", ["external-redacted", "external-code"])
def test_external_policies_build_claude(policy: str, monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used")
    p = build_provider(policy, local_url=None, local_model="m", claude_model="claude-opus-5-5")
    assert isinstance(p, AnthropicProvider) and p.model == "claude-opus-5-5"


def test_local_prices_are_zero() -> None:
    assert LOCAL_PRICES.input_per_mtok_usd == 0 and LOCAL_PRICES.output_per_mtok_usd == 0
