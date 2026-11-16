import pytest
from pydantic import ValidationError

from packages.contracts.plan import RiskInputs, RiskWeights
from packages.planning.risk import MAX_MULTIPLIER, MIN_MULTIPLIER, priority_for, risk_score


def test_lowest_inputs_give_zero_score() -> None:
    r = RiskInputs(business_criticality=1, rule_count=0, input_count=0, change_frequency=0)
    assert risk_score(r) == 0.0


def test_highest_inputs_give_score_one() -> None:
    r = RiskInputs(
        business_criticality=5, rule_count=99, input_count=99, change_frequency=5, past_defects=99
    )
    assert risk_score(r) == 1.0


def test_score_is_monotonic_in_each_input(neutral_risk: RiskInputs) -> None:
    base = risk_score(neutral_risk)
    for field in ("business_criticality", "rule_count", "input_count", "change_frequency"):
        bumped = neutral_risk.model_copy(update={field: getattr(neutral_risk, field) + 1})
        assert risk_score(bumped) >= base, field


def test_custom_weights_change_the_score(neutral_risk: RiskInputs) -> None:
    only_defects = RiskWeights(
        business_criticality=0, rules=0, inputs=0, change_frequency=0, past_defects=1
    )
    assert risk_score(neutral_risk, only_defects) == pytest.approx(2 / 10)


def test_weights_must_not_all_be_zero() -> None:
    with pytest.raises(ValidationError, match="weight"):
        RiskWeights(business_criticality=0, rules=0, inputs=0, change_frequency=0, past_defects=0)


def test_risk_inputs_are_validated() -> None:
    with pytest.raises(ValidationError):
        RiskInputs(business_criticality=6, rule_count=0, input_count=0, change_frequency=0)
    with pytest.raises(ValidationError):
        RiskInputs(business_criticality=3, rule_count=-1, input_count=0, change_frequency=0)


@pytest.mark.parametrize(
    ("score", "priority"),
    [
        (0.0, "Could"),
        (0.32, "Could"),
        (0.33, "Should"),
        (0.65, "Should"),
        (0.66, "Must"),
        (1.0, "Must"),
    ],
)
def test_priority_thresholds(score: float, priority: str) -> None:
    assert priority_for(score) == priority


def test_multiplier_bounds_are_documented_values() -> None:
    assert (MIN_MULTIPLIER, MAX_MULTIPLIER) == (0.7, 1.5)
