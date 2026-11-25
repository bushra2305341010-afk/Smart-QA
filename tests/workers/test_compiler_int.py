"""Compiler worker: approved cases → plan-locked actions, Playwright file, run row (F20)."""

from __future__ import annotations

import ast
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.models import (
    Environment,
    GraphVersion,
    Node,
    PipelineState,
    Plan,
    Project,
    Run,
    Segment,
    Step,
    TestCase,
)
from apps.api.db.session import project_session
from apps.api.storage import MemoryObjectStore
from apps.workers.compiler import (
    CompilerError,
    code_key,
    compile_all,
    handle_compile_job,
    json_key,
    pick_environment,
)
from apps.workers.gateway import gateway_factory
from packages.contracts.run import CompiledCase
from tests.model_gateway.fakes import FakeProvider, ok
from tests.workers.test_analyst_int import SETTINGS

pytestmark = pytest.mark.integration
QUOTE = "The cart shows 'Total: 10.00'."


def _seed(s: Session, pid: uuid.UUID, *, envs: list[tuple[str, str]] | None = None) -> Plan:
    gv = GraphVersion(project_id=pid, number=1, status="approved")
    s.add(gv)
    s.flush()
    journey = Node(project_id=pid, graph_version_id=gv.id, type="Journey", label="Cart")
    screen = Node(project_id=pid, graph_version_id=gv.id, type="Screen", label="Cart",
                  attrs={"route": "/cart"}, review_status="approved")  # fmt: skip
    noroute = Node(project_id=pid, graph_version_id=gv.id, type="Screen", label="Home",
                   attrs={"route": "home"}, review_status="approved")  # fmt: skip
    field = Node(project_id=pid, graph_version_id=gv.id, type="Field", label="Quantity",
                 review_status="edited")  # fmt: skip
    plan = Plan(project_id=pid, graph_version_id=gv.id, status="approved")
    s.add_all([journey, screen, noroute, field, plan])
    s.flush()
    seg = Segment(project_id=pid, plan_id=plan.id, journey_node_id=journey.id,
                  suggested_count=3, risk_score=1.0, priority="Must")  # fmt: skip
    s.add(seg)
    for name, kind in envs if envs is not None else [("prod", "production"), ("dev", "local")]:
        s.add(Environment(project_id=pid, name=name, kind=kind, base_url="http://127.0.0.1:8765"))
    s.flush()

    def case(code: str, steps: list[str], expected: str, status: str = "approved",
             cited: bool = True) -> None:  # fmt: skip
        citation = (
            {"status": "verified", "quote": QUOTE} if cited else {"status": "unable_to_verify"}
        )
        tc = TestCase(project_id=pid, segment_id=seg.id, code=code, role="buyer",
                      technique="happy_path", priority="Must", expected_text=expected,
                      citation=citation, review_status=status)  # fmt: skip
        s.add(tc)
        s.flush()
        s.add_all(Step(project_id=pid, test_case_id=tc.id, n=i, action=a)
                  for i, a in enumerate(steps, 1))  # fmt: skip

    case("TC-CAR-001", ["Visit the cart page", "Fill 'Quantity' with '2'", "Click 'Update'"],
         "The cart shows 'Total: 10.00'")  # fmt: skip
    case("TC-CAR-002", ["Go to /cart", "Shake the phone"], "The total is updated", "edited")
    case("TC-CAR-003", ["Dance"], "Nothing literal", cited=False)
    case("TC-CAR-004", ["Go to /cart"], "'X'", status="rejected")
    case("TC-CAR-005", ["Go to /cart", "Wiggle"], "'Saved'")
    return plan


def _pipeline(s: Session, pid: uuid.UUID) -> None:
    s.add(PipelineState(project_id=pid, stage="compile", status="queued",
                        entered_at=datetime.now(UTC)))  # fmt: skip


def _actions(store: MemoryObjectStore, s: Session, code: str) -> CompiledCase:
    case_id = s.scalars(select(TestCase.id).where(TestCase.code == code)).one()
    return CompiledCase.model_validate_json(store.get(json_key(case_id)))


def test_compile_grammar_only(app: sessionmaker[Session], make_tenant: Any) -> None:
    pid = make_tenant().project_id
    with project_session(app, pid) as s:
        _seed(s, pid)
        _pipeline(s, pid)
    store = MemoryObjectStore()
    handle_compile_job(app, store, None, {"project_id": str(pid)})
    with project_session(app, pid) as s:
        state = s.scalars(select(PipelineState).order_by(PipelineState.entered_at.desc())).first()
        assert state is not None
        assert (state.stage, state.status) == ("execute", "queued")
        run = s.scalars(select(Run)).one()
        assert run.totals == {"cases": 4, "compiled": 1, "partial": 2, "not_compiled": 1}
        env = s.get_one(Environment, run.env_id)
        assert env.kind == "local"  # production skipped
        first = _actions(store, s, "TC-CAR-001")
        assert [a.kind for a in first.actions] == ["goto", "fill", "click", "expect_text"]
        assert first.actions[0].value == "/cart" and first.actions[-1].expected
        second = _actions(store, s, "TC-CAR-002")
        assert second.unparsed_steps == [2, 3]
        paths = dict(s.execute(select(TestCase.code, TestCase.compiled_path)).all())
        assert paths["TC-CAR-003"] is None and paths["TC-CAR-004"] is None
        source = store.get(code_key(first.case_id)).decode()
        ast.parse(source)
        assert "Total: 10.00" in source and "127.0.0.1:8765" in source


def test_model_fills_only_unparsed_steps(app: sessionmaker[Session], make_tenant: Any) -> None:
    pid = make_tenant().project_id
    with project_session(app, pid) as s:
        _seed(s, pid)
        s.get_one(Project, pid).settings = {"budget_monthly_usd": 100}
    car2 = {"actions": [
        {"kind": "press", "step_n": 2, "value": "Tab"},
        {"kind": "expect_text", "step_n": 3, "locator": {"by": "text", "value": "Updated"},
         "expected": True},
        {"kind": "click", "step_n": 1, "locator": {"by": "css", "value": "#evil"}},
    ]}  # fmt: skip
    car3 = {"actions": [{"kind": "goto", "step_n": 1, "value": "/dance"},
                        {"kind": "goto", "step_n": 9, "value": "/nope"}]}  # fmt: skip
    fake = FakeProvider([ok(json.dumps(car2)), ok(json.dumps(car3)), ok(json.dumps(car3))])
    store = MemoryObjectStore()
    _, totals = compile_all(app, store, gateway_factory(app, SETTINGS, provider=fake), pid)
    assert totals == {"cases": 4, "compiled": 2, "partial": 2, "not_compiled": 0}
    assert "(expected result)" not in fake.calls[2].user
    assert "<untrusted_data" in fake.calls[0].user and "Quantity" in fake.calls[0].user
    with project_session(app, pid) as s:
        second = _actions(store, s, "TC-CAR-002")
        assert [(a.kind, a.step_n) for a in second.actions] == [
            ("goto", 1), ("press", 2), ("expect_text", 3)
        ]  # fmt: skip
        assert second.unparsed_steps == [] and second.actions[-1].expected
        third = _actions(store, s, "TC-CAR-003")
        assert [a.value for a in third.actions] == ["/dance"] and third.unparsed_steps == [2]


def test_model_failure_and_empty_answer(app: sessionmaker[Session], make_tenant: Any) -> None:
    pid = make_tenant().project_id
    with project_session(app, pid) as s:
        _seed(s, pid)
        s.get_one(Project, pid).settings = {"budget_monthly_usd": 100}
    fake = FakeProvider([ok("not json")] * 3 + [ok(json.dumps({"actions": []}))] * 4)
    _, totals = compile_all(app, MemoryObjectStore(), gateway_factory(app, SETTINGS, provider=fake),
                            pid)  # fmt: skip
    assert totals["not_compiled"] == 1


@pytest.mark.parametrize(
    ("envs", "default", "expected"),
    [([("p", "production")], None, "p"), ([("a", "local"), ("b", "staging")], "b", "b"),
     ([("a", "local")], "missing", "a")],
)  # fmt: skip
def test_pick_environment(
    app: sessionmaker[Session], make_tenant: Any, envs: list[tuple[str, str]],
    default: str | None, expected: str,
) -> None:  # fmt: skip
    pid = make_tenant().project_id
    with project_session(app, pid) as s:
        for name, kind in envs:
            s.add(Environment(project_id=pid, name=name, kind=kind, base_url="http://x"))
        s.flush()
        if default:
            env_id = s.scalar(select(Environment.id).where(Environment.name == default))
            s.get_one(Project, pid).settings = {"default_env_id": str(env_id or "missing")}
        assert pick_environment(s, pid).name == expected


def test_failures(app: sessionmaker[Session], make_tenant: Any) -> None:
    pid = make_tenant().project_id
    with project_session(app, pid) as s, pytest.raises(CompilerError, match="environment"):
        pick_environment(s, pid)
    with pytest.raises(CompilerError, match="approved plan"):
        compile_all(app, MemoryObjectStore(), None, pid)
    with project_session(app, pid) as s:
        plan = _seed(s, pid)
        s.execute(update(TestCase).values(review_status="pending"))
        _pipeline(s, pid)
        assert plan.id
    handle_compile_job(app, MemoryObjectStore(), None, {"project_id": str(pid)})
    with project_session(app, pid) as s:
        state = s.scalars(select(PipelineState).order_by(PipelineState.entered_at.desc())).first()
        assert state is not None and state.status == "failed"
    # pipeline moved on: a stale job must not crash
    handle_compile_job(app, MemoryObjectStore(), None, {"project_id": str(pid)})
