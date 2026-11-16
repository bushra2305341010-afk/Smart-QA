"""Liveness and readiness checks (docs/11-load-balancing.md §2, docs/12-reliability.md)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urlparse

Check = Callable[[], Awaitable[bool]]


@dataclass(frozen=True)
class DependencyStatus:
    """Result of checking one dependency."""

    name: str
    ok: bool
    detail: str = ""


async def tcp_reachable(url: str, timeout: float = 1.5) -> bool:
    """Return True if a TCP connection to the URL's host:port succeeds within `timeout`."""
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port
    if host is None or port is None:
        return False
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
    except (OSError, TimeoutError):
        return False
    writer.close()
    await writer.wait_closed()
    return True


async def check_dependencies(targets: dict[str, str | None]) -> list[DependencyStatus]:
    """Check every configured dependency. Unconfigured ones are reported, not failed."""
    results: list[DependencyStatus] = []
    for name, url in targets.items():
        if not url:
            results.append(DependencyStatus(name=name, ok=True, detail="not configured"))
            continue
        ok = await tcp_reachable(url)
        results.append(DependencyStatus(name=name, ok=ok, detail="reachable" if ok else "down"))
    return results
