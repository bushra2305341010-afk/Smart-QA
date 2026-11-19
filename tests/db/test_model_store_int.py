"""T-603: the model gateway on Postgres (replay cache, model_call recorder, budget) + cost API."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.model_store import PostgresRecorder, PostgresReplayCache, project_budget
from apps.api.db.models import ModelCall, Project
from apps.api.db.session import project_session
from packages.model_gateway.gateway import ModelGateway
from tests.model_gateway.fakes import FakeProvider, ok
from tests.model_gateway.test_gateway import PRICES, TASK, Case, _req

pytestmark = pytest.mark.integration


def _gateway(app, pid, provider, cache=None, cap=10.0):  # type: ignore[no-untyped-def]
    return ModelGateway(
        provider=provider,
        prices=PRICES,
        cache=cache or PostgresReplayCache(app, pid),
        budget=project_budget(app, pid, cap),
        recorder=PostgresRecorder(app, pid),
    )


def test_replay_cache_survives_processes_and_records_calls(
    app: sessionmaker[Session], make_tenant
) -> None:
    pid = make_tenant().project_id
    first = FakeProvider([ok('{"title": "Login", "steps": ["open"]}')])
    res = _gateway(app, pid, first).generate(TASK, _req(), Case)
    assert res.status == "ok" and not res.from_cache
    second = FakeProvider([])  # a new process: nothing scripted, so any call would fail
    again = _gateway(app, pid, second).generate(TASK, _req(), Case)
    assert again.from_cache and again.output == res.output and second.calls == []
    with project_session(app, pid) as s:
        rows = s.scalars(select(ModelCall).order_by(ModelCall.created_at)).all()
    assert [(r.from_cache, r.status, r.stage) for r in rows] == [
        (False, "ok", "designer"),
        (True, "ok", "designer"),
    ]
    assert rows[0].input_tokens == 100 and rows[0].cost_usd > 0 and rows[1].cost_usd == 0


def test_cache_is_per_project(app: sessionmaker[Session], make_tenant) -> None:
    a, b = make_tenant().project_id, make_tenant().project_id
    PostgresReplayCache(app, a).put("k", {"v": 1})
    assert PostgresReplayCache(app, b).get("k") is None
    PostgresReplayCache(app, a).put("k", {"v": 2})  # first write wins
    assert PostgresReplayCache(app, a).get("k") == {"v": 1}


def test_approved_only_mode(app: sessionmaker[Session], make_tenant) -> None:
    pid = make_tenant().project_id
    cache = PostgresReplayCache(app, pid)
    cache.put("k1", {"v": 1})
    strict = PostgresReplayCache(app, pid, approved_only=True)
    assert strict.get("k1") is None
    assert cache.approve(["k1", "missing"]) == 1
    assert cache.approve([]) == 0
    assert strict.get("k1") == {"v": 1}


def test_budget_includes_spend_from_earlier_calls(app: sessionmaker[Session], make_tenant) -> None:
    pid = make_tenant().project_id
    _gateway(app, pid, FakeProvider([ok('{"title": "A", "steps": []}')])).generate(
        TASK, _req("one"), Case
    )
    budget = project_budget(app, pid, 10.0)
    assert budget.spent_usd > 0 and budget.cap_usd == 10.0
    with project_session(app, pid) as s:
        s.get_one(Project, pid).settings = {"budget_monthly_usd": 0}
    blocked = _gateway(app, pid, FakeProvider([])).generate(TASK, _req("two"), Case)
    assert blocked.status == "budget_exceeded"
    with project_session(app, pid) as s:
        statuses = s.scalars(select(ModelCall.status).order_by(ModelCall.created_at)).all()
    assert statuses == ["ok", "budget_exceeded"]
