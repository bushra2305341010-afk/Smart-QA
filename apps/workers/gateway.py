"""Build a project's ModelGateway from settings: provider by model policy, Postgres cache,
recorder and budget (T-603). Prices come from settings and must be set for an external model
(check the provider's current price page; they are never hard-coded)."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.model_store import PostgresRecorder, PostgresReplayCache, project_budget
from apps.api.settings import Settings
from packages.contracts.plan import PriceTable
from packages.model_gateway.factory import LOCAL_PRICES, build_provider
from packages.model_gateway.gateway import ModelGateway
from packages.model_gateway.types import ModelProvider

GatewayFactory = Callable[[uuid.UUID], ModelGateway]


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


def gateway_factory(
    factory: sessionmaker[Session],
    settings: Settings,
    provider: ModelProvider | None = None,
) -> GatewayFactory:
    """`provider` is injected in tests; otherwise it follows the model policy (docs/21 B3)."""
    prices = prices_for(settings)
    chosen = provider or build_provider(
        settings.saq_model_policy,
        local_url=settings.local_model_url,
        local_model=settings.local_model_name,
        claude_model=settings.saq_default_model,
    )

    def make(project_id: uuid.UUID) -> ModelGateway:
        return ModelGateway(
            provider=chosen,
            prices=prices,
            cache=PostgresReplayCache(factory, project_id),
            budget=project_budget(factory, project_id, settings.saq_budget_monthly_usd),
            recorder=PostgresRecorder(factory, project_id),
        )

    return make
