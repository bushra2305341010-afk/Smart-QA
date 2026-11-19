"""Pipeline endpoints: state, human events, server-side gate and permission errors."""

import pytest

pytestmark = pytest.mark.integration
V1 = "/api/v1"


def test_pipeline_flow_over_http(project, make_user) -> None:  # type: ignore[no-untyped-def]
    owner, pid = project
    url = f"{V1}/projects/{pid}/pipeline"
    assert owner.client.get(url).json() == {"current": None, "history": []}

    viewer = make_user()
    owner.post(f"{V1}/projects/{pid}/members", json={"email": viewer.email, "role": "viewer"})
    denied = viewer.post(f"{url}/events", json={"event": "start"})
    assert denied.status_code == 403 and denied.json()["error"]["details"] == {
        "permission": "pipeline.manage"
    }

    started = owner.post(f"{url}/events", json={"event": "start"})
    assert started.status_code == 200 and started.json()["stage"] == "ingest"
    conflict = owner.post(f"{url}/events", json={"event": "graph_approved"})
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "STATE_CONFLICT"
    assert conflict.json()["error"]["details"]["stage"] == "ingest"

    system_only = owner.post(f"{url}/events", json={"event": "sources_parsed"})
    assert (
        system_only.status_code == 400
        and "start" in system_only.json()["error"]["details"]["allowed"]
    )

    assert owner.post(f"{url}/events", json={"event": "cancel"}).json()["status"] == "cancelled"
    state = viewer.client.get(url).json()
    assert state["current"]["status"] == "cancelled" and len(state["history"]) == 2


def test_gate_error_over_http(project, app) -> None:  # type: ignore[no-untyped-def]
    from datetime import UTC, datetime

    from apps.api import ids
    from apps.api.db.models import PipelineState
    from apps.api.db.session import project_session

    owner, pid = project
    puid = ids.decode("prj", pid)
    with project_session(app, puid) as s:
        s.add(PipelineState(project_id=puid, stage="graph_review", status="awaiting_approval",
                            entered_at=datetime.now(UTC)))  # fmt: skip
    res = owner.post(f"{V1}/projects/{pid}/pipeline/events", json={"event": "graph_approved"})
    assert res.status_code == 409
    assert res.json()["error"] == {
        **res.json()["error"],
        "code": "GATE_NOT_APPROVED",
        "details": {"gate": 1},
    }
