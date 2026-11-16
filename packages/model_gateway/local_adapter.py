"""Local-model adapter (pillar P4: local-first, bring your own model).

Talks to any server exposing the OpenAI-compatible `/chat/completions` endpoint (Ollama,
llama.cpp server, vLLM, LM Studio) with plain HTTP. Used for air-gapped or privacy-strict
projects, where nothing may leave the company network.

Notes:
- Structured output uses `response_format: json_schema`. Support varies by server and model;
  the gateway validates every reply anyway and retries with the validation error.
- `effort` has no equivalent and is ignored; temperature is 0 for repeatable output.
- There is no standard token-count endpoint, so `count_tokens` returns a conservative
  estimate (about 3 characters per token). Local calls are priced at $0 (see factory).
"""

from __future__ import annotations

from typing import Any

import httpx

from packages.model_gateway.types import ProviderCall, ProviderResponse, Usage

_FINISH_TO_STOP = {
    "stop": "end_turn",
    "length": "max_tokens",
    "content_filter": "refusal",
}
_CHARS_PER_TOKEN = 3


class LocalModelError(Exception):
    """The local model server failed, was unreachable or returned an unexpected body."""


class LocalProvider:
    """`ModelProvider` backed by a self-hosted model server."""

    def __init__(
        self,
        base_url: str,
        model: str,
        client: httpx.Client | None = None,
        timeout_s: float = 120.0,
    ) -> None:
        self.model = model
        self.client = client or httpx.Client(base_url=base_url.rstrip("/") + "/", timeout=timeout_s)

    @staticmethod
    def _messages(call: ProviderCall) -> list[dict[str, str]]:
        system = (
            call.system if not call.cached_context else f"{call.system}\n\n{call.cached_context}"
        )
        user = call.user if not call.retry_feedback else f"{call.user}\n\n{call.retry_feedback}"
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    def complete(self, call: ProviderCall) -> ProviderResponse:
        """Send one chat-completion request and map it to the provider-neutral shape."""
        body: dict[str, Any] = {
            "model": self.model,
            "messages": self._messages(call),
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "output", "schema": call.json_schema, "strict": True},
            },
            "max_tokens": call.max_tokens,
            "temperature": 0,
        }
        try:
            resp = self.client.post("chat/completions", json=body)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LocalModelError(
                f"local model server returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise LocalModelError(f"local model server unreachable: {exc}") from exc

        try:
            data = resp.json()
            choice = data["choices"][0]
            text = choice["message"].get("content") or ""
            finish = str(choice.get("finish_reason") or "stop")
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LocalModelError("unexpected response from local model server") from exc

        usage = data.get("usage") or {}
        return ProviderResponse(
            text=text,
            stop_reason=_FINISH_TO_STOP.get(finish, finish),
            model=str(data.get("model") or self.model),
            usage=Usage(
                input_tokens=int(usage.get("prompt_tokens") or 0),
                output_tokens=int(usage.get("completion_tokens") or 0),
            ),
        )

    def count_tokens(self, call: ProviderCall) -> int:
        """Conservative estimate (no standard endpoint exists)."""
        chars = len(call.system) + len(call.cached_context or "") + len(call.user)
        return chars // _CHARS_PER_TOKEN + 1
