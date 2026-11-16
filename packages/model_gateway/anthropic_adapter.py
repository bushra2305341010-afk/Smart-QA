"""Claude adapter for the Model Gateway, using the official `anthropic` SDK.

Request shape (Messages API, beta endpoint for server-side refusal fallbacks):
- `system`: our stable prompt, then the cacheable context block with `cache_control`.
- `output_config`: explicit `effort` (Claude Opus 5.5 defaults to "medium") and a strict
  JSON-schema `format` so the reply is a single JSON text block.
- `fallbacks="default"` + beta header: a request declined by a safety classifier is re-run
  server-side on the recommended fallback model instead of failing.
Thinking is always on for Claude Opus 5.5, so `thinking` is not sent; thinking blocks in the
response are skipped. Retries for 429 / 5xx / connection errors are done by the SDK.
"""

from __future__ import annotations

from typing import Any

from packages.model_gateway.types import ProviderCall, ProviderResponse, Usage

DEFAULT_MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider:
    """`ModelProvider` backed by Claude."""

    def __init__(
        self, client: Any | None = None, model: str = DEFAULT_MODEL, fallbacks: bool = True
    ) -> None:
        if client is None:
            import anthropic  # imported lazily so tests and local-only mode need no key

            client = anthropic.Anthropic()
        # Any on purpose: the real SDK client or a test double with the same shape.
        self.client: Any = client
        self.model = model
        self.fallbacks = fallbacks

    @staticmethod
    def _system(call: ProviderCall) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = [{"type": "text", "text": call.system}]
        if call.cached_context:
            blocks.append(
                {
                    "type": "text",
                    "text": call.cached_context,
                    "cache_control": {"type": "ephemeral"},
                }
            )
        return blocks

    @staticmethod
    def _messages(call: ProviderCall) -> list[dict[str, Any]]:
        content = call.user if not call.retry_feedback else f"{call.user}\n\n{call.retry_feedback}"
        return [{"role": "user", "content": content}]

    def complete(self, call: ProviderCall) -> ProviderResponse:
        """Send one request and map the response to the provider-neutral shape."""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": call.max_tokens,
            "system": self._system(call),
            "messages": self._messages(call),
            "output_config": {
                "effort": call.effort,
                "format": {"type": "json_schema", "schema": call.json_schema},
            },
        }
        if self.fallbacks:
            kwargs["betas"] = [FALLBACK_BETA]
            kwargs["fallbacks"] = "default"
        resp = self.client.beta.messages.create(**kwargs)

        text = "".join(block.text for block in resp.content if block.type == "text")
        u = resp.usage
        usage = Usage(
            input_tokens=u.input_tokens or 0,
            output_tokens=u.output_tokens or 0,
            cache_read_input_tokens=u.cache_read_input_tokens or 0,
            cache_creation_input_tokens=u.cache_creation_input_tokens or 0,
        )
        category = resp.stop_details.category if resp.stop_details else None
        return ProviderResponse(
            text=text,
            stop_reason=resp.stop_reason,
            model=resp.model,
            usage=usage,
            refusal_category=category,
        )

    def count_tokens(self, call: ProviderCall) -> int:
        """Input-token count for budget checks (uses the token counting endpoint)."""
        resp = self.client.messages.count_tokens(
            model=self.model, system=self._system(call), messages=self._messages(call)
        )
        return int(resp.input_tokens)
