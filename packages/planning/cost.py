"""Cost and time estimate before generating cases (N13, NFR-6).

The stable context (system prompt + approved graph) is sent once per design run;
`cached_fraction` of it is billed at the cache-read price. Per-case tokens are billed normally.
"""

from __future__ import annotations

from packages.contracts.plan import CostAssumptions, CostEstimate, PriceTable

_MTOK = 1_000_000


def estimate_design_cost(
    case_count: int, prices: PriceTable, assumptions: CostAssumptions | None = None
) -> CostEstimate:
    """Estimate tokens, USD and minutes for designing `case_count` cases."""
    if case_count < 0:
        raise ValueError("case_count must be >= 0")
    a = assumptions or CostAssumptions()

    cached_ctx = a.fixed_context_tokens * a.cached_fraction
    uncached_ctx = a.fixed_context_tokens - cached_ctx
    per_case_in = case_count * a.input_tokens_per_case
    output = case_count * a.output_tokens_per_case

    usd = (
        (uncached_ctx + per_case_in) / _MTOK * prices.input_per_mtok_usd
        + cached_ctx / _MTOK * prices.cache_read_per_mtok_usd
        + output / _MTOK * prices.output_per_mtok_usd
    )
    return CostEstimate(
        model=prices.model,
        input_tokens=a.fixed_context_tokens + per_case_in,
        output_tokens=output,
        usd=round(usd, 4),
        minutes=round(case_count * a.seconds_per_case / 60, 2),
    )
