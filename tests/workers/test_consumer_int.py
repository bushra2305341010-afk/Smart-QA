"""Redis-stream job consumer: ack on success, dedupe by job_key, retry by reclaim (ADR-013)."""

import json
import os
import uuid

import pytest

from apps.workers.consumer import JobConsumer

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.environ.get("REDIS_URL"), reason="REDIS_URL not set"),
]


@pytest.fixture
def redis_client():  # type: ignore[no-untyped-def]
    import redis

    client = redis.Redis.from_url(os.environ["REDIS_URL"])
    stream = f"test:jobs:{uuid.uuid4().hex}"
    yield client, stream
    client.delete(stream)
    for key in client.scan_iter("saq:done:g-*"):
        client.delete(key)


def _add(client, stream, topic, job_key=None):  # type: ignore[no-untyped-def]
    payload = {"project_id": "p"} | ({"job_key": job_key} if job_key else {})
    message = {"event_id": uuid.uuid4().hex, "project_id": "p", "payload": payload}
    client.xadd(stream, {"topic": topic, "message": json.dumps(message)})


def test_handles_acks_and_dedupes(redis_client) -> None:  # type: ignore[no-untyped-def]
    client, stream = redis_client
    seen: list[dict] = []
    group = f"g-{uuid.uuid4().hex}"
    c = JobConsumer(client, group, "c1", {"job.ingest": seen.append}, stream=stream)
    c.ensure_group()
    c.ensure_group()  # idempotent
    _add(client, stream, "job.ingest", "k1")
    _add(client, stream, "job.ingest", "k1")  # duplicate dispatch (recovery)
    _add(client, stream, "job.plan")  # another worker type's job
    _add(client, stream, "job.ingest")  # no job_key → event_id is the key
    assert c.poll_once(block_ms=10) == 2
    assert [m.get("job_key") for m in seen] == ["k1", None]
    assert client.xpending(stream, group)["pending"] == 0
    assert c.poll_once(block_ms=10) == 0


def test_failed_job_is_reclaimed_and_retried(redis_client) -> None:  # type: ignore[no-untyped-def]
    client, stream = redis_client
    attempts: list[int] = []

    def flaky(_msg: dict) -> None:
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("worker crashed")

    group = f"g-{uuid.uuid4().hex}"
    c = JobConsumer(client, group, "c1", {"job.ingest": flaky}, stream=stream, reclaim_idle_ms=0)
    c.ensure_group()
    _add(client, stream, "job.ingest", "k2")
    assert c.poll_once(block_ms=10) == 0
    assert client.xpending(stream, group)["pending"] == 1
    assert c.poll_once(block_ms=10) == 1  # reclaimed
    assert len(attempts) == 2 and client.xpending(stream, group)["pending"] == 0


def test_ensure_group_reraises_other_errors() -> None:
    class Broken:
        def xgroup_create(self, *a, **k):  # type: ignore[no-untyped-def]
            raise ConnectionError("down")

    with pytest.raises(ConnectionError):
        JobConsumer(Broken(), "g", "c", {}).ensure_group()
