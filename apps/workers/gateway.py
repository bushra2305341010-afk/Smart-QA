"""Build a project's ModelGateway from settings: provider by model policy, Postgres cache,
recorder and budget (T-603). Prices come from settings and must be set for an external model
(check the provider's current price page; they are never hard-coded)."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.model_store import PostgresRecorder, PostgresReplayCache, project_budget
from apps.api.pricing import prices_for
from apps.api.settings import Settings
from packages.model_gateway.factory import build_provider
from packages.model_gateway.gateway import ModelGateway
from packages.model_gateway.types import ModelProvider

GatewayFactory = Callable[[uuid.UUID], ModelGateway]


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
