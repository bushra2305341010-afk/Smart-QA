from packages.graph.scope import journey_scope
from packages.planning.from_graph import EdgeView, NodeView

NODES = [NodeView(i, t, i) for i, t in [
    ("checkout", "Journey"), ("signup", "Journey"), ("buyer", "Role"), ("admin", "Role"),
    ("pay", "Step"), ("form", "Screen"), ("card", "Field"), ("api", "Endpoint"),
    ("card_rule", "Rule"), ("pw_rule", "Rule"), ("orphan_rule", "Rule"), ("req", "Requirement"),
    ("pw", "Field"), ("signup_step", "Step"),
]]  # fmt: skip
EDGES = [
    EdgeView("buyer", "checkout", "performs"), EdgeView("admin", "signup", "performs"),
    EdgeView("checkout", "pay", "has_step"), EdgeView("pay", "form", "on_screen"),
    EdgeView("form", "card", "has_field"), EdgeView("pay", "api", "calls"),
    EdgeView("card_rule", "card", "governs"), EdgeView("checkout", "req", "satisfies"),
    EdgeView("signup", "signup_step", "has_step"), EdgeView("pw_rule", "pw", "governs"),
    EdgeView("signup_step", "ghost", "has_step"),
]  # fmt: skip


def test_checkout_scope() -> None:
    assert journey_scope(NODES, EDGES, "checkout") == {
        "checkout", "buyer", "pay", "form", "card", "api", "card_rule", "req", "orphan_rule",
    }  # fmt: skip


def test_unknown_journey_gets_everything() -> None:
    assert journey_scope(NODES, EDGES, "nope") == {n.id for n in NODES}
