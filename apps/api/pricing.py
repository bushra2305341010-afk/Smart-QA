"""Model prices from settings (never hard-coded; check the provider's current price page)."""

from __future__ import annotations

from typing import Any

from apps.api.settings import Settings
from packages.contracts.plan import PriceTable
from packages.model_gateway.factory import LOCAL_PRICES
from packages.planning.cost import estimate_design_cost


def prices_for(settings: Settings) -> PriceTable:
    if settings.saq_model_policy == "local-only":
        return LOCAL_PRICES
    values = (
        settings.model_price_input_per_mtok,
        settings.model_price_output_per_mtok,
        settings.model_price_cache_read_per_mtok,
    )
    if any(v is None for v in values):
        raise ValueError("Set MODEL_PRICE_INPUT/OUTPUT/CACHE_READ_PER_MTOK for the external model")
    i, o, c = values
    return PriceTable(
        model=settings.saq_default_model,
        input_per_mtok_usd=float(i or 0),
        output_per_mtok_usd=float(o or 0),
        cache_read_per_mtok_usd=float(c or 0),
    )


def cost_estimate(settings: Settings, cases: int) -> dict[str, Any]:
    try:
        prices = prices_for(settings)
    except ValueError as exc:
        return {"available": False, "reason": str(exc)}
    return {"available": True, **estimate_design_cost(cases, prices).model_dump()}
