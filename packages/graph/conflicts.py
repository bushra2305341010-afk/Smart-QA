"""Spec conflict finder (N07): two sources state different values for the same subject.

Rules carry `subject` and `value` attrs (e.g. subject "password maximum length", value "64").
Two verified Rules with the same normalised subject, different normalised values and citations
from different sources produce a Conflict node that cites both (US-03). Requiring both
citations keeps false positives down (sector 02 bug locator).
"""

from __future__ import annotations

from itertools import combinations

from packages.graph.model import GNode, Graph, norm_label


def _sources(node: GNode) -> set[str]:
    return {c.source for c in node.citations}


def find_conflicts(graph: Graph) -> int:
    """Add Conflict nodes. Returns how many were added."""
    by_subject: dict[str, list[GNode]] = {}
    for rule in graph.of_type("Rule"):
        subject, value = rule.attrs.get("subject"), rule.attrs.get("value")
        if subject and value and rule.citations:
            by_subject.setdefault(norm_label(subject), []).append(rule)
    added = 0
    for subject, rules in sorted(by_subject.items()):
        for a, b in combinations(sorted(rules, key=lambda r: r.key), 2):
            same_value = norm_label(a.attrs["value"]) == norm_label(b.attrs["value"])
            if same_value or _sources(a) == _sources(b):
                continue
            conflict = graph.add(
                GNode(
                    key=f"Conflict:{a.key}|{b.key}",
                    type="Conflict",
                    label=(
                        f"Sources disagree on {a.attrs['subject']}: "
                        f"'{a.attrs['value']}' vs '{b.attrs['value']}'"
                    ),
                    attrs={"subject": subject, "a": a.attrs["value"], "b": b.attrs["value"]},
                    citations=[*a.citations, *b.citations],
                )
            )
            graph.link(conflict.key, a.key, "conflicts_with")
            graph.link(conflict.key, b.key, "conflicts_with")
            added += 1
    return added
