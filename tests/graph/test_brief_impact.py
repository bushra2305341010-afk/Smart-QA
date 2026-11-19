from packages.graph.brief import build_brief
from packages.graph.impact import affected_journeys, changed_lines
from packages.planning.from_graph import EdgeView, NodeView

NODES = [
    NodeView("j", "Journey", "Checkout"), NodeView("j2", "Journey", "Sign up"),
    NodeView("s", "Step", "Pay"), NodeView("sc", "Screen", "Payment page"),
    NodeView("f", "Field", "Coupon code"), NodeView("ep", "Endpoint", "POST /orders"),
    NodeView("r", "Rule", "Coupon expiry", {"subject": "coupon expires"}),
    NodeView("role", "Role", "Customer"), NodeView("q", "Question", "What is fast?"),
    NodeView("c", "Conflict", "Sources disagree"), NodeView("lone", "Endpoint", "GET /health"),
]  # fmt: skip
EDGES = [
    EdgeView("j", "s", "has_step"), EdgeView("s", "sc", "on_screen"),
    EdgeView("sc", "f", "has_field"), EdgeView("s", "ep", "calls"),
    EdgeView("r", "f", "governs"), EdgeView("role", "j", "performs"),
    EdgeView("j2", "ghost", "has_step"),
]  # fmt: skip


def test_brief() -> None:
    md = build_brief("Shop", NODES, EDGES, {"r": ["Coupons expire after 30 days."]})
    assert md.startswith("# Shop: product brief")
    assert "- **Checkout**: Pay" in md and "- **Sign up**\n" in md
    assert '> "Coupons expire after 30 days."' in md and "`POST /orders`" in md
    assert "## Open questions\n- What is fast?" in md and "## Spec conflicts" in md
    assert build_brief("Empty", [], [], {}) == "# Empty: product brief\n"


def test_impact_from_diff() -> None:
    diff = """--- a/api.py
+++ b/api.py
@@
-@router.post("/orders")
+@router.post("/orders")  # validate coupon expires date
 unchanged line about health
"""
    impacts = affected_journeys(NODES, EDGES, diff)
    assert [i.journey for i in impacts] == ["Checkout"]
    reasons = " | ".join(impacts[0].reasons)
    assert "Endpoint 'POST /orders'" in reasons and "Rule 'Coupon expiry'" in reasons
    assert affected_journeys(NODES, EDGES, "nothing relevant") == []
    assert changed_lines("plain text\n\n") == ["plain text"]
