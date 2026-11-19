"""In-memory graph built by the pipeline before it is saved as a draft graph version."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


def norm_label(label: str) -> str:
    """Matching key for labels: NFKC, case-folded, punctuation and extra spaces removed."""
    text = unicodedata.normalize("NFKC", label).casefold()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


@dataclass(frozen=True)
class Quote:
    source: str  # source label (S1, S2, ...)
    text: str


@dataclass(frozen=True)
class CitedSpan:
    source: str
    start: int
    end: int
    quote: str


@dataclass
class GNode:
    key: str
    type: str
    label: str
    attrs: dict[str, str] = field(default_factory=dict)
    quotes: list[Quote] = field(default_factory=list)
    citations: list[CitedSpan] = field(default_factory=list)


@dataclass(frozen=True)
class GEdge:
    src: str
    dst: str
    kind: str


@dataclass
class Graph:
    nodes: dict[str, GNode] = field(default_factory=dict)
    edges: set[GEdge] = field(default_factory=set)

    def add(self, node: GNode) -> GNode:
        self.nodes[node.key] = node
        return node

    def link(self, src: str, dst: str, kind: str) -> None:
        if src in self.nodes and dst in self.nodes and src != dst:
            self.edges.add(GEdge(src, dst, kind))

    def of_type(self, *types: str) -> list[GNode]:
        return [n for n in self.nodes.values() if n.type in types]
