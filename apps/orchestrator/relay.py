"""Outbox relay: publish committed outbox rows to Redis, then mark them (docs/12 §3).

At-least-once: a crash between publish and mark re-publishes, so consumers dedupe by
`event_id` (jobs also carry `job_key`). Runs as `saq_system` (ADR-012) to see every project.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Protocol

from sqlalchemy.orm import Session, sessionmaker

from apps.api.db import outbox

log = logging.getLogger(__name__)

JOBS_STREAM = "saq:jobs"
EVENTS_STREAM = "saq:events"
STREAM_MAXLEN = 100_000


class Publisher(Protocol):
    def publish(self, topic: str, message: dict[str, Any]) -> None: ...


class RedisPublisher:
    """`job.*` topics go to the jobs stream (consumer groups), the rest to the events stream."""

    def __init__(self, client: Any) -> None:
        self._redis = client

    @staticmethod
    def stream_for(topic: str) -> str:
        return JOBS_STREAM if topic.startswith("job.") else EVENTS_STREAM

    def publish(self, topic: str, message: dict[str, Any]) -> None:
        fields = {"topic": topic, "message": json.dumps(message, sort_keys=True)}
        self._redis.xadd(self.stream_for(topic), fields, maxlen=STREAM_MAXLEN, approximate=True)


def relay_once(factory: sessionmaker[Session], publisher: Publisher, limit: int = 100) -> int:
    """Publish up to `limit` events in order. Stops at the first failure (kept for next round)."""
    published = []
    with factory.begin() as s:
        for event in outbox.claim_unpublished(s, limit):
            message = {
                "event_id": str(event.id),
                "project_id": str(event.project_id),
                "payload": event.payload,
            }
            try:
                publisher.publish(event.topic, message)
            except Exception:
                log.exception(
                    "outbox publish failed; will retry", extra={"event_id": str(event.id)}
                )
                break
            published.append(event.id)
        outbox.mark_published(s, published)
    return len(published)


def serve(
    factory: sessionmaker[Session],
    publisher: Publisher,
    stop: threading.Event,
    interval_s: float = 0.5,
) -> None:
    """Relay until `stop` is set; poll faster while there is a backlog."""
    while not stop.is_set():
        if relay_once(factory, publisher) == 0:
            stop.wait(interval_s)
