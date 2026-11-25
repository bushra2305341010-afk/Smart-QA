"""`uv run python -m apps.workers`: run the job consumers for every worker stage."""

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
from apps.api.trackers import tracker_factory
from apps.workers.analyst import handle_understand_job
from apps.workers.compiler import handle_compile_job
from apps.workers.consumer import Handler, JobConsumer
from apps.workers.designer import handle_design_job
from apps.workers.gateway import gateway_factory
from apps.workers.ingest import GitOptions, handle_ingest_job
from apps.workers.planner import handle_plan_job
from apps.workers.reporter import handle_report_job
from packages.citations.embed import LocalEmbedder


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
    client = redis.Redis.from_url(settings.redis_url)
    token = settings.git_read_token.get_secret_value() if settings.git_read_token else None
    git = GitOptions(token=token)
    embedder = (
        LocalEmbedder(settings.embedding_url, settings.embedding_model)
        if settings.embedding_url
        else None
    )
    make_gateway = gateway_factory(factory, settings)
    handlers: dict[str, dict[str, Handler]] = {
        "ingest": {"job.ingest": lambda m: handle_ingest_job(factory, store, m, git, embedder)},
        "understand": {
            "job.understand": functools.partial(handle_understand_job, factory, store, make_gateway)
        },
        "plan": {"job.plan": functools.partial(handle_plan_job, factory, settings)},
        "design": {
            "job.design": functools.partial(handle_design_job, factory, store, make_gateway)
        },
        "compile": {
            "job.compile": functools.partial(handle_compile_job, factory, store, make_gateway)
        },
        "report": {
            "job.report": functools.partial(
                handle_report_job, factory, store, tracker_factory(settings)
            )
        },
    }
    consumers = [
        JobConsumer(client, group=group, consumer=socket.gethostname(), handlers=h)
        for group, h in handlers.items()
    ]
    for consumer in consumers:
        consumer.ensure_group()
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    while not stop.is_set():
        for consumer in consumers:
            consumer.poll_once(block_ms=200)


if __name__ == "__main__":  # pragma: no cover
    main()
