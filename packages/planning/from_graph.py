"""Read an approved Product Understanding Graph into planner inputs (pure, deterministic).

For each Journey node:
- roles       = Role nodes that `performs` it
- steps       = `has_step` targets; screens = their `on_screen` targets
- inputs      = Fields on those screens (+ limits/classes from Rules that `govern` them);
                a Rule with a limit that governs the journey or a step becomes its own input
- forbidden   = Rule attr `forbidden_roles` (comma list)
- transitions = Rule attr `transition`
Risk inputs come from Journey attrs `criticality` (1-5, default 3) and `change_frequency`
(0-5, default 2), plus the counts above. Rejected nodes must be filtered out by the caller.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from packages.contracts.plan import InputField, JourneySpec, Limit, RiskInputs

DEFAULT_CRITICALITY = 3
DEFAULT_CHANGE_FREQUENCY = 2
# A "-" right after a digit is a range dash ("8-64"), not a minus sign.
_NUMBER = re.compile(r"(?<![\d.])-?\d+(?:\.\d+)?")
_MAX_WORDS = ("max", "maximum", "at most", "up to", "no more than", "limit")
_MIN_WORDS = ("min", "minimum", "at least", "no less than")


@dataclass(frozen=True)
class NodeView:
    id: str
    type: str
    label: str
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EdgeView:
    src: str
    dst: str
    kind: str


def _num(text: Any) -> float | None:
    match = _NUMBER.search(str(text or ""))
    return float(match.group()) if match else None


def limit_from_rule(rule: NodeView) -> Limit | None:
    """`min`/`max` attrs win; else a range value ("8-64", "8 to 64"); else the subject's wording
    decides whether a single value is a minimum or a maximum."""
    name = str(rule.attrs.get("subject") or rule.label)
    low, high = _num(rule.attrs.get("min")), _num(rule.attrs.get("max"))
    if low is None and high is None:
        value = str(rule.attrs.get("value", ""))
        numbers = [float(n) for n in _NUMBER.findall(value)]
        if len(numbers) >= 2:
            low, high = min(numbers[:2]), max(numbers[:2])
        elif len(numbers) == 1:
            subject = name.lower()
            if any(w in subject for w in _MIN_WORDS):
                low = numbers[0]
            elif any(w in subject for w in _MAX_WORDS):
                high = numbers[0]
    if low is None and high is None:
        return None
    return Limit(name=name, min=low, max=high)


def _split(value: Any) -> list[str]:
    return [p.strip() for p in str(value or "").split(",") if p.strip()]


def _bounded(value: Any, default: int, low: int, high: int) -> int:
    number = _num(value)
    return default if number is None else max(low, min(high, int(number)))


def journeys_from_graph(
    nodes: list[NodeView], edges: list[EdgeView]
) -> list[tuple[JourneySpec, RiskInputs]]:
    by_id = {n.id: n for n in nodes}
    out: dict[tuple[str, str], list[str]] = defaultdict(list)
    into: dict[tuple[str, str], list[str]] = defaultdict(list)
    for e in edges:
        if e.src in by_id and e.dst in by_id:
            out[(e.src, e.kind)].append(e.dst)
            into[(e.dst, e.kind)].append(e.src)

    def targets(ids: list[str], kind: str) -> list[str]:
        return sorted({t for i in ids for t in out[(i, kind)]})

    result: list[tuple[JourneySpec, RiskInputs]] = []
    for journey in sorted((n for n in nodes if n.type == "Journey"), key=lambda n: n.label):
        roles = sorted(
            {by_id[r].label for r in into[(journey.id, "performs")] if by_id[r].type == "Role"}
        )
        steps = targets([journey.id], "has_step")
        screens = targets(steps, "on_screen")
        field_ids = [f for f in targets(screens, "has_field") if by_id[f].type == "Field"]
        scope = {journey.id, *steps, *screens, *field_ids}
        rules = sorted(
            {r for target in scope for r in into[(target, "governs")] if by_id[r].type == "Rule"}
        )

        inputs: list[InputField] = []
        for fid in field_ids:
            fnode = by_id[fid]
            limits = [
                lim
                for r in rules
                if fid in out[(r, "governs")] and (lim := limit_from_rule(by_id[r])) is not None
            ]
            inputs.append(
                InputField(
                    name=fnode.label, classes=_split(fnode.attrs.get("classes")), limits=limits
                )
            )
        for r in rules:
            if not set(out[(r, "governs")]) & set(field_ids):
                limit = limit_from_rule(by_id[r])
                if limit is not None:
                    inputs.append(InputField(name=limit.name, limits=[limit]))

        forbidden = sorted(
            {v for r in rules for v in _split(by_id[r].attrs.get("forbidden_roles"))}
        )
        transitions = sorted(
            {str(by_id[r].attrs["transition"]) for r in rules if by_id[r].attrs.get("transition")}
        )
        spec = JourneySpec(
            journey_id=journey.id,
            name=journey.label,
            roles=roles,
            inputs=inputs,
            forbidden=forbidden,
            transitions=transitions,
            screens=len(screens),
        )
        risk = RiskInputs(
            business_criticality=_bounded(
                journey.attrs.get("criticality"), DEFAULT_CRITICALITY, 1, 5
            ),
            rule_count=len(rules),
            input_count=len(inputs),
            change_frequency=_bounded(
                journey.attrs.get("change_frequency"), DEFAULT_CHANGE_FREQUENCY, 0, 5
            ),
            past_defects=_bounded(journey.attrs.get("past_defects"), 0, 0, 1000),
        )
        result.append((spec, risk))
    return result
