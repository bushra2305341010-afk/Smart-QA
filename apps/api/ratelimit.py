"""Fixed-window rate limits (docs/06-api.md §1, docs/10 §3): login per IP, requests per user,
job starts per project. Over the limit → 429 RATE_LIMITED with Retry-After.

`MemoryRateLimiter` is per process (laptop mode); `RedisRateLimiter` is shared by all API
replicas (team mode, `RATE_LIMIT_BACKEND=redis`).
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from apps.api.errors import ApiError


@dataclass(frozen=True)
class Decision:
    allowed: bool
    retry_after_s: int


class RateLimiter(Protocol):
    def hit(self, key: str, limit: int, window_s: int) -> Decision: ...


class MemoryRateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._windows: dict[str, tuple[float, int]] = {}

    def hit(self, key: str, limit: int, window_s: int) -> Decision:
        now = self._clock()
        start, count = self._windows.get(key, (now, 0))
        if now - start >= window_s:
            start, count = now, 0
        count += 1
        self._windows[key] = (start, count)
        if count > limit:
            return Decision(False, max(1, math.ceil(start + window_s - now)))
        return Decision(True, 0)


class RedisRateLimiter:
    def __init__(self, client: Any, prefix: str = "saq:rl:") -> None:
        self._redis = client
        self._prefix = prefix

    def hit(self, key: str, limit: int, window_s: int) -> Decision:
        name = self._prefix + key
        pipe = self._redis.pipeline()
        pipe.incr(name)
        pipe.expire(name, window_s, nx=True)
        pipe.ttl(name)
        count, _, ttl = pipe.execute()
        if int(count) > limit:
            return Decision(False, max(1, int(ttl)))
        return Decision(True, 0)


def enforce(limiter: RateLimiter, key: str, limit: int, window_s: int = 60) -> None:
    decision = limiter.hit(key, limit, window_s)
    if not decision.allowed:
        raise ApiError(
            429,
            "RATE_LIMITED",
            "Too many requests; slow down",
            {"retry_after_s": decision.retry_after_s},
            {"Retry-After": str(decision.retry_after_s)},
        )
