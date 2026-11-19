"""Rate limits (T-105c): unit tests for both backends + the three API limits."""

import os
import uuid

import pytest

from apps.api import main
from apps.api.errors import ApiError
from apps.api.ratelimit import MemoryRateLimiter, RedisRateLimiter, enforce
from apps.api.settings import Settings, get_settings
from tests.api.conftest import PASSWORD

V1 = "/api/v1"


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_memory_window() -> None:
    clock = Clock()
    rl = MemoryRateLimiter(clock)
    assert [rl.hit("k", 2, 60).allowed for _ in range(3)] == [True, True, False]
    clock.now += 59.2
    assert rl.hit("k", 2, 60).retry_after_s == 1
    clock.now += 1
    assert rl.hit("k", 2, 60).allowed  # new window
    assert rl.hit("other", 1, 60).allowed


def test_enforce_raises_429_with_retry_after() -> None:
    rl = MemoryRateLimiter(Clock())
    enforce(rl, "k", 1)
    with pytest.raises(ApiError) as exc:
        enforce(rl, "k", 1, window_s=30)
    assert exc.value.status == 429 and exc.value.headers == {"Retry-After": "30"}


def test_backend_choice() -> None:
    assert isinstance(main._limiter(Settings()), MemoryRateLimiter)
    redis_conf = Settings(rate_limit_backend="redis", redis_url="redis://localhost:1/0")
    assert isinstance(main._limiter(redis_conf), RedisRateLimiter)
    assert isinstance(
        main._limiter(Settings(rate_limit_backend="redis", redis_url=None)), MemoryRateLimiter
    )


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("REDIS_URL"), reason="REDIS_URL not set")
def test_redis_backend_shared_counter() -> None:
    import redis

    client = redis.Redis.from_url(os.environ["REDIS_URL"])
    prefix = f"test:rl:{uuid.uuid4().hex}:"
    a, b = RedisRateLimiter(client, prefix), RedisRateLimiter(client, prefix)  # two API replicas
    assert a.hit("k", 2, 60).allowed and b.hit("k", 2, 60).allowed
    denied = a.hit("k", 2, 60)
    assert not denied.allowed and 1 <= denied.retry_after_s <= 60
    client.delete(prefix + "k")


@pytest.mark.integration
def test_login_user_and_job_limits(make_client, make_user, project, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_login_per_ip_per_min", 2)
    c = make_client()
    body = {"email": "nobody@example.com", "password": PASSWORD}
    assert [c.post(f"{V1}/auth/login", json=body).status_code for _ in range(3)] == [401, 401, 429]
    limited = c.post(f"{V1}/auth/login", json=body)
    assert (
        limited.json()["error"]["code"] == "RATE_LIMITED"
        and int(limited.headers["Retry-After"]) > 0
    )

    monkeypatch.setattr(settings, "rate_login_per_ip_per_min", 100)
    monkeypatch.setattr(settings, "rate_requests_per_user_per_min", 3)
    u = make_user()
    assert [u.client.get(f"{V1}/me").status_code for _ in range(4)] == [200, 200, 200, 429]

    monkeypatch.setattr(settings, "rate_requests_per_user_per_min", 600)
    monkeypatch.setattr(settings, "rate_job_starts_per_project_per_min", 1)
    owner, pid = project
    url = f"{V1}/projects/{pid}/pipeline/events"
    assert owner.post(url, json={"event": "start"}).status_code == 200
    assert owner.post(url, json={"event": "cancel"}).status_code == 200  # not a job start
    again = owner.post(url, json={"event": "start"})
    assert again.status_code == 429 and again.json()["error"]["code"] == "RATE_LIMITED"
