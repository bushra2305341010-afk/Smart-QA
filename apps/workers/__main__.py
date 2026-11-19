"""`uv run python -m apps.workers`: run the job consumers (ingest for now)."""

from __future__ import annotations

import functools
import logging
import signal
import socket
import threading

import redis

from apps.api.db.session import make_engine, make_session_factory
from apps.api.settings import get_settings
from apps.api.storage import S3ObjectStore
from apps.workers.consumer import JobConsumer
from apps.workers.ingest import handle_ingest_job


def main() -> None:  # pragma: no cover - process wiring; parts are tested separately
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())
    if not (settings.worker_database_url and settings.redis_url and settings.s3_endpoint):
        raise SystemExit("Set WORKER_DATABASE_URL, REDIS_URL and S3_ENDPOINT")
    factory = make_session_factory(make_engine(settings.worker_database_url))
    store = S3ObjectStore.from_settings(
        settings.s3_endpoint,
        settings.s3_bucket,
        settings.s3_access_key or "",
        settings.s3_secret_key.get_secret_value() if settings.s3_secret_key else "",
    )
    consumer = JobConsumer(
        redis.Redis.from_url(settings.redis_url),
        group="ingest",
        consumer=socket.gethostname(),
        handlers={"job.ingest": functools.partial(handle_ingest_job, factory, store)},
    )
    consumer.ensure_group()
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    while not stop.is_set():
        consumer.poll_once()


if __name__ == "__main__":  # pragma: no cover
    main()
