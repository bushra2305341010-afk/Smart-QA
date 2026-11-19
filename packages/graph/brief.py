"""Product brief (N10): a short markdown summary of the approved graph, every rule quoted."""

from __future__ import annotations

from packages.planning.from_graph import EdgeView, NodeView


def build_brief(
    project: str, nodes: list[NodeView], edges: list[EdgeView], quotes: dict[str, list[str]]
) -> str:
    by_type: dict[str, list[NodeView]] = {}
    for n in sorted(nodes, key=lambda n: n.label):
        by_type.setdefault(n.type, []).append(n)
    steps_of: dict[str, list[str]] = {}
    labels = {n.id: n.label for n in nodes}
    for e in edges:
        if e.kind == "has_step" and e.src in labels and e.dst in labels:
            steps_of.setdefault(e.src, []).append(labels[e.dst])

    lines = [f"# {project}: product brief", ""]

    def section(title: str, items: list[str]) -> None:
        if items:
            lines.extend([f"## {title}", *items, ""])

    section("Roles", [f"- {n.label}" for n in by_type.get("Role", [])])
    section(
        "Journeys",
        [
            f"- **{j.label}**"
            + (f": {' → '.join(sorted(steps_of[j.id]))}" if j.id in steps_of else "")
            for j in by_type.get("Journey", [])
        ],
    )
    section(
        "Rules",
        [
            f"- {r.label}" + "".join(f'\n  > "{q}"' for q in quotes.get(r.id, []))
            for r in by_type.get("Rule", []) + by_type.get("Requirement", [])
        ],
    )
    section("Endpoints", [f"- `{e.label}`" for e in by_type.get("Endpoint", [])])
    section("Open questions", [f"- {q.label}" for q in by_type.get("Question", [])])
    section("Spec conflicts", [f"- {c.label}" for c in by_type.get("Conflict", [])])
    return "\n".join(lines).rstrip() + "\n"
