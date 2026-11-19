"""Merge per-source extractions into one graph, deduplicating by type + normalised label."""

from __future__ import annotations

from packages.contracts.graph import Extraction
from packages.graph.model import GNode, Graph, Quote, norm_label


def merge(extractions: list[Extraction]) -> Graph:
    """Same (type, label) from any source → one node with every quote and all attrs.

    Node keys are stable (`<type>:<normalised label>`), so re-running gives the same graph.
    Edges whose ends were not extracted are dropped.
    """
    graph = Graph()
    for extraction in extractions:
        local: dict[str, str] = {}
        for item in extraction.nodes:
            key = f"{item.type}:{norm_label(item.label)}"
            node = graph.nodes.get(key) or graph.add(
                GNode(key=key, type=item.type, label=item.label)
            )
            for attr in item.attrs:
                node.attrs.setdefault(attr.name, attr.value)
            quote = Quote(item.source, item.quote)
            if quote not in node.quotes:
                node.quotes.append(quote)
            local[item.key] = key
        for edge in extraction.edges:
            if edge.from_key in local and edge.to_key in local:
                graph.link(local[edge.from_key], local[edge.to_key], edge.kind)
    return graph
