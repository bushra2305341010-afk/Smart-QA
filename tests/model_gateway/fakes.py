"""Test doubles: a scripted provider (no network, no cost)."""

from __future__ import annotations

from dataclasses import dataclass, field

from packages.model_gateway.types import ProviderCall, ProviderResponse, Usage


@dataclass
class FakeProvider:
    responses: list[ProviderResponse]
    model: str = "fake-model"
    token_estimate: int = 1_000
    calls: list[ProviderCall] = field(default_factory=list)

    def complete(self, call: ProviderCall) -> ProviderResponse:
        self.calls.append(call)
        return self.responses.pop(0)

    def count_tokens(self, call: ProviderCall) -> int:
        return self.token_estimate


def ok(text: str, **usage: int) -> ProviderResponse:
    return ProviderResponse(
        text=text,
        stop_reason="end_turn",
        model="fake-model",
        usage=Usage(
            input_tokens=usage.get("input", 100),
            output_tokens=usage.get("output", 50),
            cache_read_input_tokens=usage.get("cache_read", 0),
        ),
    )
