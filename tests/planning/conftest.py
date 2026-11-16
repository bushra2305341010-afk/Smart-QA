import pytest

from packages.contracts.plan import InputField, JourneySpec, Limit, RiskInputs


@pytest.fixture
def login() -> JourneySpec:
    """The worked Login example from docs/04-design.md §5 (expected base count = 10)."""
    return JourneySpec(
        journey_id="jrn_login",
        name="Login",
        roles=["Customer", "Admin"],
        inputs=[
            InputField(name="email", classes=["valid", "invalid format", "unregistered"]),
            InputField(name="password", limits=[Limit(name="length", min=8, max=64)]),
        ],
        forbidden=["locked account"],
        transitions=["5 failed tries then lock"],
        screens=1,
    )


@pytest.fixture
def neutral_risk() -> RiskInputs:
    return RiskInputs(
        business_criticality=3, rule_count=5, input_count=5, change_frequency=2, past_defects=2
    )
