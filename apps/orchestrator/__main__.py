"""`uv run python -m apps.orchestrator`: recover stalled jobs, then relay the outbox forever."""

from __future__ import annotations

import logging
import signal
import threading

import redis

from apps.api.db.session import make_engine, make_session_factory
from apps.api.settings import check_production, get_settings
from apps.orchestrator.recover import recover
from apps.orchestrator.relay import RedisPublisher, serve


def main() -> None:  # pragma: no cover - process wiring; parts are tested separately
    logging.basicConfig(level=get_settings().log_level.upper())
    settings = get_settings()
    check_production(settings)
    if not settings.worker_database_url or not settings.redis_url:
        raise SystemExit("Set WORKER_DATABASE_URL and REDIS_URL")
    factory = make_session_factory(make_engine(settings.worker_database_url))
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    logging.getLogger(__name__).info("recovered %d stalled job(s)", recover(factory))
    serve(factory, RedisPublisher(redis.Redis.from_url(settings.redis_url)), stop)


if __name__ == "__main__":  # pragma: no cover
    main()
