"""The part of the graph a journey needs (keeps design prompts small as graphs grow).

Scope of a journey = the journey, roles that perform it, everything reachable from it through
`has_step` → `on_screen` → `has_field` / `calls`, rules that govern any of those, requirements
linked by `satisfies`, and rules/requirements with no edges at all (never silently dropped).
An unknown journey id returns every node.
"""

from __future__ import annotations

from packages.planning.from_graph import EdgeView, NodeView

DOWN = {"has_step", "on_screen", "has_field", "calls"}
RULE_TYPES = {"Rule", "Requirement"}


def journey_scope(nodes: list[NodeView], edges: list[EdgeView], journey_id: str) -> set[str]:
    ids = {n.id for n in nodes}
    if journey_id not in ids:
        return ids
    by_id = {n.id: n for n in nodes}
    linked = {e.src for e in edges} | {e.dst for e in edges}
    scope = {journey_id}
    todo = [journey_id]
    while todo:
        current = todo.pop()
        for e in edges:
            if e.src == current and e.kind in DOWN and e.dst in ids - scope:
                scope.add(e.dst)
                todo.append(e.dst)
    for e in edges:
        if e.src not in ids or e.dst not in ids:
            continue
        if (e.kind == "performs" and e.dst == journey_id) or (
            e.kind == "governs" and e.dst in scope
        ):
            scope.add(e.src)
        elif e.kind == "satisfies" and e.src in scope:
            scope.add(e.dst)
    scope |= {n.id for n in nodes if n.type in RULE_TYPES and n.id not in linked}
    return {i for i in scope if i in by_id}
