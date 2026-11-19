"""Job consumer on the Redis `saq:jobs` stream (ADR-013).

Each worker type has its own consumer group, so every type sees every job and acks the topics
it does not handle. A handled job is acked only after it succeeds; a failure stays pending and
is re-claimed after `reclaim_idle_ms` by any consumer of the group. `job_key` makes redelivery
safe: a key already marked done is acked without running again.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from apps.orchestrator.relay import JOBS_STREAM

log = logging.getLogger(__name__)
Handler = Callable[[dict[str, Any]], None]
DONE_TTL_S = 7 * 24 * 3600


class JobConsumer:
    def __init__(
        self,
        client: Any,
        group: str,
        consumer: str,
        handlers: dict[str, Handler],
        *,
        stream: str = JOBS_STREAM,
        reclaim_idle_ms: int = 5 * 60 * 1000,
    ) -> None:
        self._redis = client
        self.group, self.consumer, self.stream = group, consumer, stream
        self.handlers = handlers
        self.reclaim_idle_ms = reclaim_idle_ms

    def ensure_group(self) -> None:
        try:
            self._redis.xgroup_create(self.stream, self.group, id="0", mkstream=True)
        except Exception as exc:  # BUSYGROUP: already exists
            if "BUSYGROUP" not in str(exc):
                raise

    def _done_key(self, job_key: str) -> str:
        return f"saq:done:{self.group}:{job_key}"

    def _handle(self, msg_id: Any, fields: dict[bytes, bytes]) -> bool:
        topic = fields[b"topic"].decode()
        handler = self.handlers.get(topic)
        if handler is None:
            self._redis.xack(self.stream, self.group, msg_id)
            return False
        message = json.loads(fields[b"message"])
        payload: dict[str, Any] = {**message["payload"], "event_id": message["event_id"]}
        key = payload.get("job_key") or message["event_id"]
        if self._redis.exists(self._done_key(key)):
            self._redis.xack(self.stream, self.group, msg_id)
            return False
        try:
            handler(payload)
        except Exception:
            log.exception("job %s failed; left pending for retry", topic)
            return False
        self._redis.set(self._done_key(key), "1", ex=DONE_TTL_S)
        self._redis.xack(self.stream, self.group, msg_id)
        return True

    def poll_once(self, block_ms: int = 1000, count: int = 10) -> int:
        """Handle reclaimed stale jobs, then new ones. Returns how many jobs ran successfully."""
        _, claimed, _ = self._redis.xautoclaim(
            self.stream, self.group, self.consumer, self.reclaim_idle_ms, "0-0", count=count
        )
        batch = list(claimed)
        if not batch:
            for _, entries in (
                self._redis.xreadgroup(
                    self.group, self.consumer, {self.stream: ">"}, count=count, block=block_ms
                )
                or []
            ):
                batch.extend(entries)
        return sum(self._handle(msg_id, fields) for msg_id, fields in batch)
