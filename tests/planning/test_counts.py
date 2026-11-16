import pytest

from packages.contracts.plan import JourneySpec, RiskInputs
from packages.planning.counts import multiplier_for, suggest_segment


def test_neutral_risk_keeps_login_close_to_base(login: JourneySpec, neutral_risk) -> None:
    seg = suggest_segment(login, neutral_risk)
    assert seg.base_count == 10
    assert seg.journey_id == "jrn_login"
    assert 9 <= seg.suggested_count <= 12
    assert seg.approved_count is None


def test_high_risk_adds_cases_low_risk_trims(login: JourneySpec) -> None:
    low = RiskInputs(business_criticality=1, rule_count=0, input_count=0, change_frequency=0)
    high = RiskInputs(
        business_criticality=5, rule_count=40, input_count=40, change_frequency=5, past_defects=20
    )
    assert suggest_segment(login, low).suggested_count == 7  # 10 x 0.7
    assert suggest_segment(login, high).suggested_count == 15  # 10 x 1.5
    assert suggest_segment(login, high).priority == "Must"
    assert suggest_segment(login, low).priority == "Could"


def test_trimming_never_drops_happy_paths() -> None:
    j = JourneySpec(journey_id="j", name="Checkout", roles=["A", "B", "C"])
    low = RiskInputs(business_criticality=1, rule_count=0, input_count=0, change_frequency=0)
    seg = suggest_segment(j, low)
    assert seg.base_count == 3
    assert seg.suggested_count == 3  # 3 x 0.7 = 2.1, but never fewer than one per role


@pytest.mark.parametrize(("score", "expected"), [(0.0, 0.7), (0.5, 1.1), (1.0, 1.5)])
def test_multiplier_is_linear_between_bounds(score: float, expected: float) -> None:
    assert multiplier_for(score) == pytest.approx(expected)


def test_rounding_is_half_up_and_done_once(login: JourneySpec) -> None:
    # 10 x 1.25 = 12.5 → 13 (half up, not banker's rounding to 12)
    seg = suggest_segment(
        login,
        RiskInputs(business_criticality=1, rule_count=0, input_count=0, change_frequency=0),
        score_override=0.6875,
    )
    assert seg.multiplier == pytest.approx(1.25)
    assert seg.suggested_count == 13


def test_segment_is_deterministic(login: JourneySpec, neutral_risk) -> None:
    assert suggest_segment(login, neutral_risk) == suggest_segment(login, neutral_risk)
