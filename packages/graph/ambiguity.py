"""Ambiguity checker (N08): vague words in requirements and rules become Questions.

Deterministic word list, so results are explainable and testable. Example: "Search must be
fast" → Question "What exactly does 'fast' mean here: Search must be fast?" (US-03).
"""

from __future__ import annotations

import re

from packages.graph.model import GNode, Graph

VAGUE_TERMS = (
    "fast",
    "quick",
    "quickly",
    "slow",
    "easy",
    "easily",
    "simple",
    "intuitive",
    "user friendly",
    "user-friendly",
    "appropriate",
    "appropriately",
    "reasonable",
    "adequate",
    "sufficient",
    "efficient",
    "robust",
    "secure",
    "flexible",
    "modern",
    "soon",
    "as needed",
    "as appropriate",
    "if possible",
    "etc",
    "and so on",
    "several",
    "many",
    "some",
    "few",
    "usually",
    "normally",
    "approximately",
    "about",
    "minimal",
    "large",
    "small",
)
_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in sorted(VAGUE_TERMS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def vague_terms(text: str) -> list[str]:
    """Distinct vague terms in `text`, lower-case, in order of appearance."""
    found: list[str] = []
    for match in _PATTERN.finditer(text):
        term = match.group(1).lower()
        if term not in found:
            found.append(term)
    return found


def add_questions(graph: Graph) -> int:
    """Add one Question per vague Requirement/Rule. Returns how many were added."""
    added = 0
    for node in graph.of_type("Requirement", "Rule"):
        terms = vague_terms(" ".join([node.label, *(c.quote for c in node.citations)]))
        if not terms:
            continue
        listed = ", ".join(f"'{t}'" for t in terms)
        question = graph.add(
            GNode(
                key=f"Question:vague:{node.key}",
                type="Question",
                label=f"What exactly do {listed} mean here: {node.label}?",
                attrs={"reason": "vague_terms", "terms": ",".join(terms)},
                citations=list(node.citations),
            )
        )
        graph.link(question.key, node.key, "asks_about")
        added += 1
    return added
