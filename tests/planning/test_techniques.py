from packages.contracts.plan import InputField, JourneySpec, Limit
from packages.planning.techniques import technique_rows


def test_login_example_rows_match_the_design_doc(login: JourneySpec) -> None:
    rows = {r.technique: r for r in technique_rows(login)}
    assert rows["happy_path"].count == 2
    assert rows["equivalence_class"].count == 3
    assert rows["boundary_value"].count == 2
    assert rows["negative_permission"].count == 1
    assert rows["state_transition"].count == 1
    assert rows["accessibility"].count == 1
    assert sum(r.count for r in rows.values()) == 10


def test_every_row_has_a_human_reason(login: JourneySpec) -> None:
    for row in technique_rows(login):
        assert len(row.reason) > 10 and row.reason == row.reason.strip()
    happy = next(r for r in technique_rows(login) if r.technique == "happy_path")
    assert "Customer" in happy.reason and "Admin" in happy.reason


def test_journey_without_roles_still_gets_one_happy_path() -> None:
    j = JourneySpec(journey_id="j", name="Browse", screens=0)
    rows = technique_rows(j)
    assert [(r.technique, r.count) for r in rows] == [("happy_path", 1)]


def test_zero_count_techniques_are_omitted() -> None:
    j = JourneySpec(journey_id="j", name="Search", roles=["Guest"], screens=2)
    assert {r.technique for r in technique_rows(j)} == {"happy_path", "accessibility"}


def test_boundary_two_per_limit_across_inputs() -> None:
    j = JourneySpec(
        journey_id="j",
        name="Profile",
        roles=["User"],
        inputs=[
            InputField(name="age", limits=[Limit(name="value", min=18, max=120)]),
            InputField(
                name="bio",
                limits=[Limit(name="length", min=0, max=500), Limit(name="lines", max=10)],
            ),
        ],
    )
    boundary = next(r for r in technique_rows(j) if r.technique == "boundary_value")
    assert boundary.count == 6


def test_reasons_name_the_inputs(login: JourneySpec) -> None:
    rows = {r.technique: r.reason for r in technique_rows(login)}
    assert "email: valid, invalid format, unregistered" in rows["equivalence_class"]
    assert "password length 8-64" in rows["boundary_value"]


def test_open_ended_and_fractional_limits_are_formatted() -> None:
    j = JourneySpec(
        journey_id="j",
        name="Pay",
        roles=["User"],
        inputs=[InputField(name="amount", limits=[Limit(name="value", min=0.5)])],
    )
    boundary = next(r for r in technique_rows(j) if r.technique == "boundary_value")
    assert "amount value 0.5-?" in boundary.reason
