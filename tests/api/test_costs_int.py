"""Cost meter and budget endpoints."""

from decimal import Decimal

import pytest

from apps.api import ids
from apps.api.db.models import ModelCall
from apps.api.db.session import project_session
from tests.orchestrator.seed import seed

pytestmark = pytest.mark.integration
V1 = "/api/v1"


def test_costs_and_budget(project, make_user, app) -> None:  # type: ignore[no-untyped-def]
    owner, pid = project
    puid = ids.decode("prj", pid)
    empty = owner.client.get(f"{V1}/projects/{pid}/costs").json()
    assert empty["by_stage"] == [] and Decimal(empty["month"]["spent_usd"]) == 0
    with project_session(app, puid) as s:
        run_id = seed(s, puid).run.id
        s.add_all([
            ModelCall(project_id=puid, stage="design", model="m", prompt_version="v",
                      cost_usd=Decimal("1.5"), run_id=run_id),
            ModelCall(project_id=puid, stage="design", model="m", prompt_version="v",
                      cost_usd=Decimal("0"), from_cache=True),
            ModelCall(project_id=puid, stage="plan", model="m", prompt_version="v",
                      cost_usd=Decimal("0.25")),
        ])  # fmt: skip
    costs = owner.client.get(f"{V1}/projects/{pid}/costs").json()
    assert [(x["stage"], x["calls"], x["cache_hits"]) for x in costs["by_stage"]] == [
        ("design", 2, 1),
        ("plan", 1, 0),
    ]
    assert costs["by_run"] == [{"run_id": ids.encode("run", run_id), "cost_usd": "1.500000"}]
    assert Decimal(costs["month"]["spent_usd"]) == Decimal("1.75")
    assert len(costs["by_month"]) == 1

    lead = make_user()
    owner.post(f"{V1}/projects/{pid}/members", json={"email": lead.email, "role": "qa_lead"})
    put = lead.client.put(f"{V1}/projects/{pid}/budget", json={"monthly_usd": 5},
                          headers={"X-CSRF-Token": lead.csrf})  # fmt: skip
    assert put.status_code == 403
    ok = owner.client.put(f"{V1}/projects/{pid}/budget", json={"monthly_usd": 5},
                          headers={"X-CSRF-Token": owner.csrf})  # fmt: skip
    assert ok.status_code == 200 and Decimal(ok.json()["remaining_usd"]) == Decimal("3.25")
    month = owner.client.get(f"{V1}/projects/{pid}/costs").json()["month"]
    assert Decimal(month["cap_usd"]) == 5
    actions = [e["action"] for e in owner.client.get(f"{V1}/projects/{pid}/audit").json()["items"]]
    assert actions[-1] == "budget.changed"


def test_budget_is_read_from_the_right_project(project) -> None:  # type: ignore[no-untyped-def]
    """A user in two projects must never see the other project's settings (RLS lets a user see
    all their projects' rows in `project`, so every lookup filters by id)."""
    owner, first = project
    second = owner.post(f"{V1}/projects", json={"name": "Second"}).json()["id"]
    owner.client.put(
        f"{V1}/projects/{second}/budget",
        json={"monthly_usd": 1},
        headers={"X-CSRF-Token": owner.csrf},
    )
    caps = {
        pid: Decimal(owner.client.get(f"{V1}/projects/{pid}/costs").json()["month"]["cap_usd"])
        for pid in (first, second)
    }
    assert caps[second] == 1 and caps[first] != 1
