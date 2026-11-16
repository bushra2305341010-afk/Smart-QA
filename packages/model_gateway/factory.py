"""Choose the model provider from the project's model policy (docs/21 section B3).

`local-only` is enforced here, in code: it never builds the Claude provider, and it refuses a
local model URL that is not on an internal host, so no request can leave the company network.
"""

from __future__ import annotations

import ipaddress
from typing import Literal
from urllib.parse import urlparse

from packages.contracts.plan import PriceTable
from packages.model_gateway.anthropic_adapter import DEFAULT_MODEL, AnthropicProvider
from packages.model_gateway.local_adapter import LocalProvider
from packages.model_gateway.types import ModelProvider

ModelPolicy = Literal["local-only", "external-redacted", "external-code"]

LOCAL_PRICES = PriceTable(
    model="local", input_per_mtok_usd=0, output_per_mtok_usd=0, cache_read_per_mtok_usd=0
)

_INTERNAL_NAMES = {"localhost", "host.docker.internal"}
_INTERNAL_SUFFIXES = (".local", ".internal", ".lan", ".home.arpa")


class PolicyViolationError(Exception):
    """The configuration would break the project's model privacy policy."""


def is_internal_url(url: str) -> bool:
    """True if `url` points at loopback, a private IP, or an internal host name.

    Internal names: localhost, host.docker.internal, single-label names (Docker Compose
    service names such as `ollama`), and names ending in .local/.internal/.lan/.home.arpa.
    No DNS lookup is made.
    """
    host = urlparse(url).hostname
    if not host:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        name = host.lower()
        return name in _INTERNAL_NAMES or "." not in name or name.endswith(_INTERNAL_SUFFIXES)
    return ip.is_private or ip.is_loopback


def build_provider(
    policy: ModelPolicy,
    *,
    local_url: str | None,
    local_model: str,
    claude_model: str = DEFAULT_MODEL,
) -> ModelProvider:
    """Return the provider allowed by `policy`."""
    if policy == "local-only":
        if not local_url:
            raise PolicyViolationError("local-only policy requires LOCAL_MODEL_URL")
        if not is_internal_url(local_url):
            raise PolicyViolationError(
                f"local-only policy: {local_url} is not an internal host; refusing to send data"
            )
        return LocalProvider(base_url=local_url, model=local_model)
    return AnthropicProvider(model=claude_model)
