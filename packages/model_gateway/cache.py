"""Deterministic replay cache (N17): the same model + prompt version + input never pays twice."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol

from packages.model_gateway.types import ModelRequest, TaskSpec


def cache_key(model: str, task: TaskSpec, request: ModelRequest, schema_name: str) -> str:
    """SHA-256 over everything that can change the output."""
    payload = {
        "model": model,
        "stage": task.stage,
        "prompt_version": task.prompt_version,
        "effort": task.effort,
        "schema": schema_name,
        "request": request.model_dump(mode="json"),
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(blob.encode()).hexdigest()


class ReplayCache(Protocol):
    """Storage for validated outputs. The Postgres implementation is `replay_cache` (M08)."""

    def get(self, key: str) -> dict[str, Any] | None: ...

    def put(self, key: str, value: dict[str, Any]) -> None: ...


class InMemoryReplayCache:
    """Process-local cache for tests and the laptop dev loop."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        return self._store.get(key)

    def put(self, key: str, value: dict[str, Any]) -> None:
        self._store[key] = value
