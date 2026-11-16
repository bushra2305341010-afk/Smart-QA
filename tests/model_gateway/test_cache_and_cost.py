import pytest

from packages.contracts.plan import PriceTable
from packages.model_gateway.cache import InMemoryReplayCache, cache_key
from packages.model_gateway.cost import Budget, BudgetExceededError, usage_cost
from packages.model_gateway.types import ModelRequest, TaskSpec, Usage

PRICES = PriceTable(
    model="m", input_per_mtok_usd=4, output_per_mtok_usd=20, cache_read_per_mtok_usd=0.2
)


def _req(user: str = "u") -> ModelRequest:
    return ModelRequest(system="s", cached_context="graph", user=user)


def test_cache_key_changes_with_prompt_version_and_input() -> None:
    t1 = TaskSpec(stage="designer", prompt_version="designer@1.0.0")
    t2 = TaskSpec(stage="designer", prompt_version="designer@1.1.0")
    assert cache_key("m", t1, _req(), "S") == cache_key("m", t1, _req(), "S")
    assert cache_key("m", t1, _req(), "S") != cache_key("m", t2, _req(), "S")
    assert cache_key("m", t1, _req(), "S") != cache_key("m", t1, _req("other"), "S")
    assert cache_key("m", t1, _req(), "S") != cache_key("other-model", t1, _req(), "S")


def test_in_memory_cache_roundtrip() -> None:
    cache = InMemoryReplayCache()
    assert cache.get("k") is None
    cache.put("k", {"a": 1})
    assert cache.get("k") == {"a": 1}


def test_usage_cost_includes_cache_read_and_write() -> None:
    u = Usage(
        input_tokens=1_000_000,
        output_tokens=100_000,
        cache_read_input_tokens=1_000_000,
        cache_creation_input_tokens=1_000_000,
    )
    # input 4 + output 2 + cache read 0.2 + cache write 4 x 1.25 = 11.2
    assert usage_cost(u, PRICES) == pytest.approx(11.2)


def test_budget_blocks_before_overspend() -> None:
    b = Budget(cap_usd=1.0)
    b.check(0.6)
    b.add(0.6)
    with pytest.raises(BudgetExceededError, match="budget"):
        b.check(0.5)
    assert b.remaining == pytest.approx(0.4)


def test_unlimited_budget() -> None:
    b = Budget(cap_usd=None)
    b.check(1e9)
    assert b.remaining is None
