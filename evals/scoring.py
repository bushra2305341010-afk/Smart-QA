"""Graph evaluation against a hand-made golden graph (docs/08-agent.md §6).

Deterministic so numbers are comparable across prompt and model versions:
- a produced node matches an expected node of the same class (Rule and Requirement are one
  class) when the word-set Jaccard of its label against the expected label or any alias is
  at least `threshold`; matching is one-to-one, best scores first;
- precision = matched produced / produced; recall = matched required / required (optional
  expected nodes never hurt recall and count as correct when produced);
- citation accuracy = produced Rule/Requirement nodes with at least one verified citation;
- conflicts and vague-term questions are checked separately.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_WORD = re.compile(r"[a-z0-9]+")
FACT_TYPES = {"Role", "Journey", "Step", "Screen", "Field", "Rule", "Endpoint", "Requirement"}


def _class(node_type: str) -> str:
    return "Rule" if node_type in {"Rule", "Requirement"} else node_type


def _words(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def similarity(a: str, b: str) -> float:
    wa, wb = _words(a), _words(b)
    return len(wa & wb) / len(wa | wb) if wa and wb else 0.0


@dataclass
class GraphScore:
    precision: float
    recall: float
    citation_accuracy: float
    conflicts_found: bool
    vague_questions_found: bool
    missing: list[str] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)

    def passes(
        self, min_precision: float = 0.8, min_recall: float = 0.75, min_citations: float = 0.9
    ) -> bool:
        return (
            self.precision >= min_precision
            and self.recall >= min_recall
            and self.citation_accuracy >= min_citations
        )


def score_graph(
    expected: dict[str, Any], produced: list[dict[str, Any]], threshold: float = 0.5
) -> GraphScore:
    facts = [
        n for n in produced if n["type"] in FACT_TYPES and n.get("review_status") != "rejected"
    ]
    exp = expected["nodes"]
    pairs = []
    for i, e in enumerate(exp):
        names = [e["label"], *e.get("aliases", [])]
        for j, p in enumerate(facts):
            if _class(e["type"]) == _class(p["type"]):
                best = max(similarity(name, p["label"]) for name in names)
                if best >= threshold:
                    pairs.append((best, i, j))
    used_e: set[int] = set()
    used_p: set[int] = set()
    for _, i, j in sorted(pairs, key=lambda t: (-t[0], t[1], t[2])):
        if i not in used_e and j not in used_p:
            used_e.add(i)
            used_p.add(j)
    required = [i for i, e in enumerate(exp) if not e.get("optional")]
    rules = [p for p in facts if _class(p["type"]) == "Rule"]
    verified = [
        p for p in rules if any(c.get("status") == "verified" for c in p.get("citations", []))
    ]
    conflicts = [n for n in produced if n["type"] == "Conflict"]
    conflicts_found = all(
        any(all(v in c["label"] for v in want["values"]) for c in conflicts)
        for want in expected.get("conflicts", [])
    )
    questions = " ".join(n["label"].lower() for n in produced if n["type"] == "Question")
    return GraphScore(
        precision=len(used_p) / len(facts) if facts else 0.0,
        recall=len(used_e & set(required)) / len(required) if required else 1.0,
        citation_accuracy=len(verified) / len(rules) if rules else 0.0,
        conflicts_found=conflicts_found,
        vague_questions_found=all(t in questions for t in expected.get("vague_terms", [])),
        missing=[f"{exp[i]['type']}: {exp[i]['label']}" for i in required if i not in used_e],
        unmatched=[
            f"{facts[j]['type']}: {facts[j]['label']}" for j in range(len(facts)) if j not in used_p
        ],
    )
