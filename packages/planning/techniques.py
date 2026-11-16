"""Named test-design techniques -> case counts with reasons (docs/04-design.md section 5).

Pure functions: the same journey always gives the same rows.
"""

from __future__ import annotations

from packages.contracts.plan import InputField, JourneySpec, Limit, TechniqueRow


def _fmt_bound(value: float | None) -> str:
    if value is None:
        return "?"
    return str(int(value)) if value == int(value) else str(value)


def _fmt_limit(field: InputField, limit: Limit) -> str:
    return f"{field.name} {limit.name} {_fmt_bound(limit.min)}-{_fmt_bound(limit.max)}"


def technique_rows(journey: JourneySpec) -> list[TechniqueRow]:
    """Return the technique rows for a journey, omitting techniques with zero cases.

    Every journey gets at least one happy-path case, even if no role is listed.
    """
    rows: list[TechniqueRow] = []

    if journey.roles:
        rows.append(
            TechniqueRow(
                technique="happy_path",
                count=len(journey.roles),
                reason="1 per role that can use the journey: " + ", ".join(journey.roles),
            )
        )
    else:
        rows.append(
            TechniqueRow(
                technique="happy_path",
                count=1,
                reason="No roles listed: 1 default happy path",
            )
        )

    classed = [f for f in journey.inputs if f.classes]
    if classed:
        rows.append(
            TechniqueRow(
                technique="equivalence_class",
                count=sum(len(f.classes) for f in classed),
                reason="1 per valid or invalid class: "
                + "; ".join(f"{f.name}: {', '.join(f.classes)}" for f in classed),
            )
        )

    limits = [(f, lim) for f in journey.inputs for lim in f.limits]
    if limits:
        rows.append(
            TechniqueRow(
                technique="boundary_value",
                count=2 * len(limits),
                reason="2 per limit (just inside and just outside): "
                + "; ".join(_fmt_limit(f, lim) for f, lim in limits),
            )
        )

    if journey.forbidden:
        rows.append(
            TechniqueRow(
                technique="negative_permission",
                count=len(journey.forbidden),
                reason="1 per forbidden role or state: " + ", ".join(journey.forbidden),
            )
        )

    if journey.transitions:
        rows.append(
            TechniqueRow(
                technique="state_transition",
                count=len(journey.transitions),
                reason="1 per important transition: " + ", ".join(journey.transitions),
            )
        )

    if journey.screens:
        rows.append(
            TechniqueRow(
                technique="accessibility",
                count=journey.screens,
                reason=f"1 accessibility scan per screen ({journey.screens} screen(s))",
            )
        )

    return rows
