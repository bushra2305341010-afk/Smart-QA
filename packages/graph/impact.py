"""Change impact for coding agents (P5, MCP `understand_change`): which journeys does a diff touch?

A node is touched when all words of its label (or its `subject` attr) appear in one changed
line of the diff, e.g. Endpoint "POST /orders" and a line `+ @router.post("/orders")`. Touched
nodes are traced up the graph (field → screen → step → journey; rule → what it governs) to the
journeys, and every journey comes with the lines that matched, so the answer is explainable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from packages.planning.from_graph import EdgeView, NodeView

_WORD = re.compile(r"[a-z0-9]+")
_UP = {"has_step", "on_screen", "has_field", "calls", "governs"}
MATCHABLE = {"Endpoint", "Field", "Screen", "Step", "Rule", "Journey"}


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if len(w) > 1}


def changed_lines(diff: str) -> list[str]:
    """Added/removed lines of a unified diff (or every line if it is not a diff)."""
    lines = diff.splitlines()
    marked = [ln[1:] for ln in lines if ln[:1] in ("+", "-") and not ln.startswith(("+++", "---"))]
    return [ln for ln in (marked or lines) if ln.strip()]


@dataclass
class Impact:
    journey: str
    reasons: list[str] = field(default_factory=list)


def affected_journeys(nodes: list[NodeView], edges: list[EdgeView], diff: str) -> list[Impact]:
    by_id = {n.id: n for n in nodes}
    parents: dict[str, set[str]] = {}
    for e in edges:
        if e.kind not in _UP or e.src not in by_id or e.dst not in by_id:
            continue
        if e.kind == "governs":  # a rule affects what it governs, and vice versa
            parents.setdefault(e.src, set()).add(e.dst)
        parents.setdefault(e.dst, set()).add(e.src)
    lines = [(ln, _words(ln)) for ln in changed_lines(diff)]
    impacts: dict[str, Impact] = {}
    for node in sorted(nodes, key=lambda n: (n.type, n.label)):
        if node.type not in MATCHABLE:
            continue
        need = _words(str(node.attrs.get("subject") or node.label))
        hit = next((ln for ln, words in lines if need and need <= words), None)
        if hit is None:
            continue
        seen, todo, journeys = {node.id}, [node.id], set()
        while todo:
            current = todo.pop()
            if by_id[current].type == "Journey":
                journeys.add(current)
            for p in parents.get(current, set()) - seen:
                seen.add(p)
                todo.append(p)
        for j in sorted(journeys, key=lambda j: by_id[j].label):
            impact = impacts.setdefault(j, Impact(by_id[j].label))
            impact.reasons.append(f"{node.type} '{node.label}' matches: {hit.strip()[:120]}")
    return sorted(impacts.values(), key=lambda i: i.journey)
