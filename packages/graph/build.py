"""One entry point: extractions + source texts → verified graph with conflicts and questions."""

from __future__ import annotations

from dataclasses import dataclass

from packages.contracts.graph import Extraction
from packages.graph.ambiguity import add_questions
from packages.graph.cite import attach_citations
from packages.graph.conflicts import find_conflicts
from packages.graph.merge import merge
from packages.graph.model import Graph


@dataclass(frozen=True)
class BuildReport:
    nodes: int
    edges: int
    unverified: int
    conflicts: int
    questions: int


def build_graph(extractions: list[Extraction], texts: dict[str, str]) -> tuple[Graph, BuildReport]:
    graph = merge(extractions)
    demoted = attach_citations(graph, texts)
    conflicts = find_conflicts(graph)
    questions = add_questions(graph)
    report = BuildReport(
        nodes=len(graph.nodes),
        edges=len(graph.edges),
        unverified=len(demoted),
        conflicts=conflicts,
        questions=questions + len(demoted),
    )
    return graph, report
