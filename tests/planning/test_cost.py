import pytest
from pydantic import ValidationError

from packages.contracts.plan import CostAssumptions, PriceTable
from packages.planning.cost import estimate_design_cost

PRICES = PriceTable(
    model="test-model",
    input_per_mtok_usd=4.0,
    output_per_mtok_usd=20.0,
    cache_read_per_mtok_usd=0.2,
)


def test_cost_scales_with_case_count() -> None:
    a = estimate_design_cost(10, PRICES)
    b = estimate_design_cost(20, PRICES)
    assert b.input_tokens == 2 * a.input_tokens - CostAssumptions().fixed_context_tokens
    assert b.usd > a.usd


def test_cost_formula_matches_prices() -> None:
    assumptions = CostAssumptions(
        fixed_context_tokens=0,
        input_tokens_per_case=1_000,
        output_tokens_per_case=2_000,
        cached_fraction=0.0,
        seconds_per_case=6,
    )
    est = estimate_design_cost(50, PRICES, assumptions)
    assert est.input_tokens == 50_000
    assert est.output_tokens == 100_000
    assert est.usd == pytest.approx(50_000 / 1e6 * 4 + 100_000 / 1e6 * 20)  # 0.2 + 2.0
    assert est.minutes == pytest.approx(5.0)
    assert est.model == "test-model"


def test_cached_context_is_cheaper() -> None:
    plain = estimate_design_cost(10, PRICES, CostAssumptions(cached_fraction=0.0))
    cached = estimate_design_cost(10, PRICES, CostAssumptions(cached_fraction=0.9))
    assert cached.usd < plain.usd


def test_zero_cases_costs_only_context() -> None:
    est = estimate_design_cost(
        0, PRICES, CostAssumptions(fixed_context_tokens=1000, cached_fraction=0)
    )
    assert est.output_tokens == 0
    assert est.usd == pytest.approx(1000 / 1e6 * 4)


def test_negative_case_count_rejected() -> None:
    with pytest.raises(ValueError, match="case_count"):
        estimate_design_cost(-1, PRICES)


def test_cached_fraction_bounds() -> None:
    with pytest.raises(ValidationError):
        CostAssumptions(cached_fraction=1.5)


def test_estimate_exceeds_budget_flag() -> None:
    est = estimate_design_cost(1000, PRICES)
    assert est.exceeds(0.01) is True
    assert est.exceeds(1e9) is False
