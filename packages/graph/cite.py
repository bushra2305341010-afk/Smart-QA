"""Verify every node's quote against the stored source text (pillar P1, code not prompt).

A quote counts only if `packages.citations.verify_quote` finds it exactly (after the shared
normalisation). Rules and Requirements without one verified quote are not kept as facts: they
become Questions for a human ("Could not verify ..."), so nothing uncited can drive a test.
"""

from __future__ import annotations

from packages.citations.verify import verify_quote
from packages.contracts.graph import CITED_TYPES
from packages.graph.model import CitedSpan, GNode, Graph


def attach_citations(graph: Graph, texts: dict[str, str]) -> list[str]:
    """Fill `node.citations` from `texts` (source label → normalised text).

    Returns the keys of nodes that were demoted to Questions.
    """
    demoted: list[str] = []
    for key in list(graph.nodes):
        node = graph.nodes[key]
        for quote in node.quotes:
            text = texts.get(quote.source)
            if text is None:
                continue
            check = verify_quote(text, quote.text, None, None)
            if check.verified and check.start is not None and check.end is not None:
                span = CitedSpan(
                    quote.source, check.start, check.end, text[check.start : check.end]
                )
                if span not in node.citations:
                    node.citations.append(span)
        if node.type in CITED_TYPES and not node.citations:
            demoted.append(key)
            _demote(graph, node)
    return demoted


def _demote(graph: Graph, node: GNode) -> None:
    del graph.nodes[node.key]
    graph.edges = {e for e in graph.edges if node.key not in (e.src, e.dst)}
    graph.add(
        GNode(
            key=f"Question:unverified:{node.key}",
            type="Question",
            label=f"Could not verify this {node.type.lower()} in the sources: {node.label}",
            attrs={"reason": "quote_not_found", "original_type": node.type},
            quotes=node.quotes,
        )
    )
