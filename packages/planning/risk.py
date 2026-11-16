"""Transparent risk score (N12) and Must/Should/Could priority (N14).

score = weighted average of normalised signals, each in [0, 1]:
  business_criticality (1-5)  -> (value - 1) / 4
  rule_count, input_count,
  past_defects                -> min(value, CAP) / CAP
  change_frequency (0-5)      -> value / 5
"""

from __future__ import annotations

from packages.contracts.plan import Priority, RiskInputs, RiskWeights

COUNT_CAP = 10
MIN_MULTIPLIER = 0.7
MAX_MULTIPLIER = 1.5
MUST_THRESHOLD = 0.66
SHOULD_THRESHOLD = 0.33


def _capped(value: int) -> float:
    return min(value, COUNT_CAP) / COUNT_CAP


def risk_score(inputs: RiskInputs, weights: RiskWeights | None = None) -> float:
    """Return the risk score in [0, 1], rounded to 4 decimals for stable comparisons."""
    w = weights or RiskWeights()
    parts = [
        (w.business_criticality, (inputs.business_criticality - 1) / 4),
        (w.rules, _capped(inputs.rule_count)),
        (w.inputs, _capped(inputs.input_count)),
        (w.change_frequency, inputs.change_frequency / 5),
        (w.past_defects, _capped(inputs.past_defects)),
    ]
    total_weight = sum(weight for weight, _ in parts)
    score = sum(weight * value for weight, value in parts) / total_weight
    return round(score, 4)


def priority_for(score: float) -> Priority:
    """Map a risk score to Must / Should / Could."""
    if score >= MUST_THRESHOLD:
        return "Must"
    if score >= SHOULD_THRESHOLD:
        return "Should"
    return "Could"
