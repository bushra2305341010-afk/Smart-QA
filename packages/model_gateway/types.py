"""Types for the Model Gateway (docs/08-agent.md section 2, ADR-003)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

Effort = Literal["low", "medium", "high", "xhigh", "max"]
GatewayStatus = Literal["ok", "invalid", "refused", "truncated", "budget_exceeded"]


class TaskSpec(BaseModel):
    """What a stage asks for. `prompt_version` is part of the replay-cache key."""

    model_config = ConfigDict(frozen=True)

    stage: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    effort: Effort = "high"
    max_tokens: int = Field(default=16_000, gt=0)
    expected_output_tokens: int = Field(default=2_000, ge=0)


class ModelRequest(BaseModel):
    """Stage input. `system` is ours (trusted). `cached_context` is stable, cacheable context
    (e.g. the approved graph). `untrusted` maps a source label to text from the app under
    test, documents or logs: it is always wrapped and redacted, never treated as instructions."""

    model_config = ConfigDict(frozen=True)

    system: str
    user: str
    cached_context: str | None = None
    untrusted: dict[str, str] = Field(default_factory=dict)


class Usage(BaseModel):
    """Token usage of one or more calls."""

    model_config = ConfigDict(frozen=True)

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_input_tokens=self.cache_read_input_tokens + other.cache_read_input_tokens,
            cache_creation_input_tokens=self.cache_creation_input_tokens
            + other.cache_creation_input_tokens,
        )


class ProviderCall(BaseModel):
    """Provider-neutral request after redaction and wrapping."""

    model_config = ConfigDict(frozen=True)

    system: str
    user: str
    cached_context: str | None = None
    effort: Effort = "high"
    max_tokens: int = 16_000
    json_schema: dict[str, object]
    retry_feedback: str = ""


class ProviderResponse(BaseModel):
    """Provider-neutral response."""

    model_config = ConfigDict(frozen=True)

    text: str
    stop_reason: str
    model: str
    usage: Usage
    refusal_category: str | None = None


class ModelProvider(Protocol):
    """A model backend: Claude, a local model, or a test double."""

    model: str

    def complete(self, call: ProviderCall) -> ProviderResponse: ...

    def count_tokens(self, call: ProviderCall) -> int: ...


@dataclass(frozen=True)
class GatewayResult[R: BaseModel]:
    """Outcome of `ModelGateway.generate`. `output` is set only when `status == "ok"`."""

    status: GatewayStatus
    output: R | None
    attempts: int
    usage: Usage
    cost_usd: float
    from_cache: bool
    model: str
    detail: str = ""


@dataclass(frozen=True)
class ModelCallRecord:
    """One row for the `model_call` table / tracing (docs/07-database.md)."""

    stage: str
    prompt_version: str
    model: str
    status: GatewayStatus
    attempts: int
    usage: Usage
    cost_usd: float
    latency_ms: int
    from_cache: bool
    redactions: int


Recorder = Callable[[ModelCallRecord], None]
