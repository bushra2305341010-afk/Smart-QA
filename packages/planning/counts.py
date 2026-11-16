"""Suggested test count per segment = sum(technique rows) x risk multiplier, rounded once."""

from __future__ import annotations

import math

from packages.contracts.plan import JourneySpec, RiskInputs, RiskWeights, SegmentPlan
from packages.planning.risk import MAX_MULTIPLIER, MIN_MULTIPLIER, priority_for, risk_score
from packages.planning.techniques import technique_rows


def multiplier_for(score: float) -> float:
    """Linear map of a risk score in [0, 1] to [MIN_MULTIPLIER, MAX_MULTIPLIER]."""
    return MIN_MULTIPLIER + (MAX_MULTIPLIER - MIN_MULTIPLIER) * score


def _round_half_up(value: float) -> int:
    # Remove float noise first (e.g. 12.499999999 -> 12.5) so 12.5 rounds to 13.
    return math.floor(round(value, 6) + 0.5)


def suggest_segment(
    journey: JourneySpec,
    risk: RiskInputs,
    weights: RiskWeights | None = None,
    score_override: float | None = None,
) -> SegmentPlan:
    """Build the suggested plan for one journey.

    The count never drops below the number of happy-path cases (one per role), so trimming a
    low-risk journey can't remove its basic coverage. `score_override` is for tests and
    for replaying a stored score.
    """
    rows = technique_rows(journey)
    base = sum(r.count for r in rows)
    happy = next(r.count for r in rows if r.technique == "happy_path")
    score = risk_score(risk, weights) if score_override is None else score_override
    mult = multiplier_for(score)
    suggested = max(happy, _round_half_up(base * mult), 1)
    return SegmentPlan(
        journey_id=journey.journey_id,
        journey_name=journey.name,
        rows=rows,
        base_count=base,
        risk_score=score,
        multiplier=round(mult, 4),
        suggested_count=suggested,
        priority=priority_for(score),
    )
