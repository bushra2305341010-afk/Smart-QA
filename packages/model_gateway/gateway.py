"""The single entry point for every model call (ADR-003, docs/08-agent.md section 2).

Order of operations for `generate`:
1. Redact personal data and secrets; wrap untrusted text.
2. Return a validated output from the replay cache if the same request was answered before.
3. Estimate cost and check the budget BEFORE calling the provider.
4. Call the provider; handle refusal and truncation; validate JSON against the stage schema,
   retrying with the validation error (at most `max_attempts` calls).
5. Record the call (tokens, cost, latency, cache hit) and charge the budget.
An invalid, refused or truncated result never carries an output, so it can never become a Pass.
"""

from __future__ import annotations

import time
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from packages.contracts.plan import PriceTable
from packages.model_gateway.cache import ReplayCache, cache_key
from packages.model_gateway.cost import Budget, BudgetExceededError, usage_cost
from packages.model_gateway.redact import redact
from packages.model_gateway.schema import strict_json_schema
from packages.model_gateway.types import (
    GatewayResult,
    GatewayStatus,
    ModelCallRecord,
    ModelProvider,
    ModelRequest,
    ProviderCall,
    Recorder,
    TaskSpec,
    Usage,
)
from packages.model_gateway.untrusted import wrap_untrusted

T = TypeVar("T", bound=BaseModel)
_MTOK = 1_000_000
_MAX_ERROR_CHARS = 1_500


class ModelGateway:
    """Provider-neutral, budget-aware, cached, validated model calls."""

    def __init__(
        self,
        provider: ModelProvider,
        prices: PriceTable,
        cache: ReplayCache,
        budget: Budget,
        recorder: Recorder,
        max_attempts: int = 3,
    ) -> None:
        if not 1 <= max_attempts <= 3:
            raise ValueError("max_attempts must be between 1 and 3 (1 call + up to 2 retries)")
        self.provider = provider
        self.prices = prices
        self.cache = cache
        self.budget = budget
        self.recorder = recorder
        self.max_attempts = max_attempts

    def _prepare(self, request: ModelRequest) -> tuple[ModelRequest, int]:
        user = redact(request.user)
        parts = [user.text]
        redactions = user.total
        for source in sorted(request.untrusted):
            clean = redact(request.untrusted[source])
            redactions += clean.total
            parts.append(wrap_untrusted(source, clean.text))
        cached = None
        if request.cached_context is not None:
            ctx = redact(request.cached_context)
            redactions += ctx.total
            cached = ctx.text
        prepared = ModelRequest(
            system=request.system, user="\n\n".join(parts), cached_context=cached
        )
        return prepared, redactions

    def generate(self, task: TaskSpec, request: ModelRequest, schema: type[T]) -> GatewayResult[T]:
        """Run one stage call and return a validated output or an honest failure status."""
        started = time.perf_counter()
        prepared, redactions = self._prepare(request)
        key = cache_key(self.provider.model, task, prepared, schema.__name__)

        def finish(
            status: GatewayStatus,
            output: T | None,
            attempts: int,
            usage: Usage,
            cost: float,
            from_cache: bool,
            model: str,
            detail: str = "",
        ) -> GatewayResult[T]:
            self.recorder(
                ModelCallRecord(
                    stage=task.stage,
                    prompt_version=task.prompt_version,
                    model=model,
                    status=status,
                    attempts=attempts,
                    usage=usage,
                    cost_usd=cost,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    from_cache=from_cache,
                    redactions=redactions,
                )
            )
            return GatewayResult(status, output, attempts, usage, cost, from_cache, model, detail)

        hit = self.cache.get(key)
        if hit is not None:
            return finish(
                "ok", schema.model_validate(hit), 0, Usage(), 0.0, True, self.provider.model
            )

        call = ProviderCall(
            system=prepared.system,
            user=prepared.user,
            cached_context=prepared.cached_context,
            effort=task.effort,
            max_tokens=task.max_tokens,
            json_schema=strict_json_schema(schema),
        )
        estimate = (
            self.provider.count_tokens(call) / _MTOK * self.prices.input_per_mtok_usd
            + task.expected_output_tokens / _MTOK * self.prices.output_per_mtok_usd
        )
        try:
            self.budget.check(estimate)
        except BudgetExceededError as exc:
            return finish(
                "budget_exceeded", None, 0, Usage(), 0.0, False, self.provider.model, str(exc)
            )

        usage = Usage()
        model = self.provider.model
        status: GatewayStatus = "invalid"
        output: T | None = None
        detail = ""
        attempts = 0
        while attempts < self.max_attempts:
            attempts += 1
            resp = self.provider.complete(call)
            usage = usage + resp.usage
            model = resp.model
            if resp.stop_reason == "refusal":
                status, detail = "refused", resp.refusal_category or ""
                break
            if resp.stop_reason == "max_tokens":
                status, detail = "truncated", "output hit max_tokens"
                break
            try:
                output = schema.model_validate_json(resp.text)
            except ValidationError as exc:
                detail = str(exc)[:_MAX_ERROR_CHARS]
                call = call.model_copy(
                    update={
                        "retry_feedback": "Your previous output failed validation:\n"
                        f"{detail}\nReturn only JSON that matches the schema."
                    }
                )
                continue
            status, detail = "ok", ""
            self.cache.put(key, output.model_dump(mode="json"))
            break

        cost = usage_cost(usage, self.prices)
        self.budget.add(cost)
        return finish(status, output, attempts, usage, cost, False, model, detail)
