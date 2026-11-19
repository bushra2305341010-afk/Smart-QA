"""Approved graph → planner inputs (US-04: 2 roles + 1 length limit → 2 happy + 2 boundary)."""

import pytest

from packages.planning.counts import suggest_segment
from packages.planning.from_graph import EdgeView, NodeView, journeys_from_graph, limit_from_rule


def N(id_, type_, label, **attrs) -> NodeView:  # type: ignore[no-untyped-def]
    return NodeView(id_, type_, label, attrs)


def test_us04_two_roles_one_limit() -> None:
    nodes = [
        N("j", "Journey", "Sign up", criticality="5", change_frequency="9"),
        N("r1", "Role", "Customer"), N("r2", "Role", "Admin"), N("x", "Screen", "not a role"),
        N("s1", "Step", "Fill form"), N("sc", "Screen", "Sign-up page"),
        N("f", "Field", "Password", classes="letters, digits"), N("fx", "Step", "not a field"),
        N("rule", "Rule", "Password length", subject="password length", value="8 to 64"),
        N("cap", "Rule", "Coupon cap", subject="maximum coupons per order", value="3",
          forbidden_roles="Guest, Banned", transition="draft->submitted"),
        N("doc", "Rule", "No number rule", value="always"),
        N("other", "Journey", "Browse"),
    ]  # fmt: skip
    edges = [
        EdgeView("r1", "j", "performs"), EdgeView("r2", "j", "performs"),
        EdgeView("x", "j", "performs"),
        EdgeView("j", "s1", "has_step"), EdgeView("s1", "sc", "on_screen"),
        EdgeView("sc", "f", "has_field"), EdgeView("sc", "fx", "has_field"),
        EdgeView("rule", "f", "governs"), EdgeView("cap", "j", "governs"),
        EdgeView("doc", "s1", "governs"),
        EdgeView("ghost", "j", "performs"),
    ]  # fmt: skip
    [(browse, browse_risk), (signup, risk)] = journeys_from_graph(nodes, edges)
    assert browse.name == "Browse" and browse.roles == [] and browse_risk.business_criticality == 3
    assert signup.roles == ["Admin", "Customer"] and signup.screens == 1
    password = next(i for i in signup.inputs if i.name == "Password")
    assert password.classes == ["letters", "digits"]
    assert (password.limits[0].min, password.limits[0].max) == (8, 64)
    coupons = next(i for i in signup.inputs if i.name == "maximum coupons per order")
    assert (coupons.limits[0].min, coupons.limits[0].max) == (None, 3)
    assert signup.forbidden == ["Banned", "Guest"] and signup.transitions == ["draft->submitted"]
    assert (risk.business_criticality, risk.change_frequency, risk.rule_count) == (5, 5, 3)
    rows = {r.technique: r.count for r in suggest_segment(signup, risk).rows}
    assert rows["happy_path"] == 2 and rows["boundary_value"] == 4


@pytest.mark.parametrize(
    ("attrs", "expected"),
    [
        ({"min": "2", "max": "5"}, (2, 5)),
        ({"max": "10"}, (None, 10)),
        ({"subject": "minimum age", "value": "18"}, (18, None)),
        ({"subject": "at most items", "value": "5 items"}, (None, 5)),
        ({"subject": "age", "value": "18"}, None),
        ({"subject": "age", "value": "64-8"}, (8, 64)),
        ({"subject": "length", "value": "8-64"}, (8, 64)),
        ({"subject": "temperature", "value": "-5 to 40"}, (-5, 40)),
        ({"value": "none"}, None),
    ],
)
def test_limit_from_rule(attrs, expected) -> None:  # type: ignore[no-untyped-def]
    limit = limit_from_rule(N("r", "Rule", "Label", **attrs))
    assert (None if limit is None else (limit.min, limit.max)) == expected
