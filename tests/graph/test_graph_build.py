"""Graph merge, quote verification, conflicts and ambiguity (US-02, US-03)."""

from packages.contracts.graph import Attr, ExtractedEdge, ExtractedNode, Extraction
from packages.graph.ambiguity import vague_terms
from packages.graph.build import build_graph
from packages.graph.model import GNode, Graph, norm_label

PRD = "Password must be 8 to 64 characters. Search must be fast. Customers can check out."
CODE = "Validator: password maximum length is 128 characters."


def node(key, type_, label, quote, source="S1", **attrs) -> ExtractedNode:  # type: ignore[no-untyped-def]
    return ExtractedNode(
        key=key, type=type_, label=label, source=source, quote=quote,
        attrs=[Attr(name=k, value=v) for k, v in attrs.items()],
    )  # fmt: skip


def test_build_end_to_end() -> None:
    prd = Extraction(
        nodes=[
            node("r1", "Rule", "Password length 8-64", "Password must be 8 to 64 characters.",
                 subject="password maximum length", value="64"),
            node("q1", "Requirement", "Search is fast", "Search must be fast."),
            node("j1", "Journey", "Checkout", "Customers can check out."),
            node("role", "Role", "Customer", "Customers can check out."),
            node("ghost", "Rule", "Refunds within 3 days", "Refunds are processed in 3 days."),
        ],
        edges=[
            ExtractedEdge(from_key="role", to_key="j1", kind="performs"),
            ExtractedEdge(from_key="ghost", to_key="j1", kind="governs"),
            ExtractedEdge(from_key="j1", to_key="missing", kind="has_step"),
        ],
    )  # fmt: skip
    code = Extraction(
        nodes=[
            node("r", "Rule", "password length 8-128", CODE, source="S2",
                 subject="Password maximum length", value="128"),
            node("j", "Journey", "checkout!", "Customers can check out."),  # duplicate of j1
        ]
    )  # fmt: skip
    graph, report = build_graph([prd, code], {"S1": PRD, "S2": CODE})

    journeys = graph.of_type("Journey")
    assert len(journeys) == 1 and journeys[0].label == "Checkout"
    rules = {n.label: n for n in graph.of_type("Rule")}
    assert set(rules) == {"Password length 8-64", "password length 8-128"}
    span = rules["Password length 8-64"].citations[0]
    assert PRD[span.start : span.end] == "Password must be 8 to 64 characters."

    [conflict] = graph.of_type("Conflict")
    assert "'128' vs '64'" in conflict.label
    assert {c.source for c in conflict.citations} == {"S1", "S2"}

    questions = {n.attrs["reason"]: n for n in graph.of_type("Question")}
    assert "'fast'" in questions["vague_terms"].label
    assert "Refunds within 3 days" in questions["quote_not_found"].label
    assert not any("ghost" in e.src or "Refunds" in e.src for e in graph.edges)
    kinds = sorted(e.kind for e in graph.edges)
    assert kinds == ["asks_about", "conflicts_with", "conflicts_with", "performs"]
    assert report.unverified == 1 and report.conflicts == 1 and report.questions == 2


def test_same_value_or_same_source_is_not_a_conflict() -> None:
    text = "Max 64 characters. Limit is 64 characters."
    ex = Extraction(nodes=[
        node("a", "Rule", "A", "Max 64 characters.", subject="max length", value="64"),
        node("b", "Rule", "B", "Limit is 64 characters.", subject="max length", value=" 64 "),
        node("c", "Rule", "C", "Limit is 64 characters.", subject="Max length", value="65"),
        node("d", "Rule", "D", "Max 64 characters.", subject="other"),
    ])  # fmt: skip
    _graph, report = build_graph([ex], {"S1": text})
    assert report.conflicts == 0  # a/b same value; a,b,c all cite the same single source


def test_unknown_source_and_repeated_quotes() -> None:
    ex = Extraction(nodes=[
        node("a", "Screen", "Login", "Login page shows the form", source="S9"),
        node("b", "Screen", "login", "Login page shows the form", source="S9"),
        node("c", "Screen", "LOGIN", "Login page shows the form."),
        node("d", "Screen", "Login", "Login  page shows the form."),
    ])  # fmt: skip
    graph, _ = build_graph([ex], {"S1": "Login page shows the form."})
    [screen] = graph.nodes.values()
    # S9 is not a known source; two spellings of the same S1 sentence give one citation.
    assert len(screen.quotes) == 3 and len(screen.citations) == 1


def test_vague_terms_and_labels() -> None:
    assert vague_terms("Fast, EASY and fast; as needed etc.") == [
        "fast",
        "easy",
        "as needed",
        "etc",
    ]
    assert vague_terms("Securely store fasting data") == []
    assert norm_label("  Check-Out  NOW! ") == "check out now"


def test_graph_link_ignores_unknown_and_self() -> None:
    g = Graph()
    g.add(GNode("a", "Screen", "A"))
    g.link("a", "a", "has_field")
    g.link("a", "zz", "has_field")
    assert g.edges == set()
