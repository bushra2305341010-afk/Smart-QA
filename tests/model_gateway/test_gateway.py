import pytest
from pydantic import BaseModel

from packages.contracts.plan import PriceTable
from packages.model_gateway.cache import InMemoryReplayCache
from packages.model_gateway.cost import Budget
from packages.model_gateway.gateway import ModelGateway
from packages.model_gateway.types import ModelRequest, ProviderResponse, TaskSpec, Usage
from tests.model_gateway.fakes import FakeProvider, ok

PRICES = PriceTable(
    model="fake-model", input_per_mtok_usd=4, output_per_mtok_usd=20, cache_read_per_mtok_usd=0.2
)
TASK = TaskSpec(stage="designer", prompt_version="designer@1.0.0", effort="high")


class Case(BaseModel):
    title: str
    steps: list[str]


def _gw(provider: FakeProvider, **kw) -> ModelGateway:
    records: list = kw.pop("records", [])
    return ModelGateway(
        provider=provider,
        prices=PRICES,
        cache=kw.pop("cache", InMemoryReplayCache()),
        budget=kw.pop("budget", Budget(cap_usd=10)),
        recorder=records.append,
        **kw,
    )


def _req(user: str = "Design the login case") -> ModelRequest:
    return ModelRequest(system="You design test cases.", cached_context="graph", user=user)


def test_valid_output_is_parsed_and_recorded() -> None:
    records: list = []
    p = FakeProvider([ok('{"title": "Login", "steps": ["open", "submit"]}')])
    res = _gw(p, records=records).generate(TASK, _req(), Case)
    assert res.status == "ok"
    assert res.output == Case(title="Login", steps=["open", "submit"])
    assert res.attempts == 1 and res.from_cache is False
    assert res.cost_usd > 0
    [rec] = records
    assert rec.stage == "designer" and rec.prompt_version == "designer@1.0.0" and rec.status == "ok"


def test_second_identical_call_hits_replay_cache_with_zero_cost() -> None:
    p = FakeProvider([ok('{"title": "Login", "steps": []}')])
    gw = _gw(p)
    gw.generate(TASK, _req(), Case)
    again = gw.generate(TASK, _req(), Case)
    assert again.from_cache is True and again.cost_usd == 0
    assert len(p.calls) == 1


def test_invalid_json_is_retried_with_the_error_then_succeeds() -> None:
    p = FakeProvider([ok("not json"), ok('{"title": "T", "steps": []}')])
    res = _gw(p).generate(TASK, _req(), Case)
    assert res.status == "ok" and res.attempts == 2
    assert "failed validation" in p.calls[1].retry_feedback


def test_gives_up_after_max_attempts_and_never_returns_output() -> None:
    p = FakeProvider([ok("{}"), ok("{}"), ok("{}")])
    res = _gw(p).generate(TASK, _req(), Case)
    assert res.status == "invalid" and res.output is None and res.attempts == 3


def test_refusal_is_reported_not_parsed() -> None:
    p = FakeProvider(
        [
            ProviderResponse(
                text="",
                stop_reason="refusal",
                model="fake-model",
                usage=Usage(input_tokens=10, output_tokens=0),
                refusal_category="cyber",
            )
        ]
    )
    res = _gw(p).generate(TASK, _req(), Case)
    assert res.status == "refused" and res.output is None
    assert res.detail == "cyber"


def test_truncated_output_is_reported() -> None:
    p = FakeProvider(
        [
            ProviderResponse(
                text='{"title": "T"',
                stop_reason="max_tokens",
                model="fake-model",
                usage=Usage(input_tokens=10, output_tokens=5),
            )
        ]
    )
    assert _gw(p).generate(TASK, _req(), Case).status == "truncated"


def test_budget_is_checked_before_calling_the_provider() -> None:
    p = FakeProvider([ok('{"title": "T", "steps": []}')], token_estimate=10_000_000)
    res = _gw(p, budget=Budget(cap_usd=0.01)).generate(TASK, _req(), Case)
    assert res.status == "budget_exceeded"
    assert p.calls == []


def test_personal_data_is_redacted_before_the_call() -> None:
    p = FakeProvider([ok('{"title": "T", "steps": []}')])
    _gw(p).generate(TASK, _req("Login as jane@example.com"), Case)
    sent = p.calls[0]
    assert "jane@example.com" not in sent.user
    assert "[REDACTED:email]" in sent.user


def test_untrusted_blocks_are_wrapped_and_redacted() -> None:
    p = FakeProvider([ok('{"title": "T", "steps": []}')])
    req = ModelRequest(system="s", user="u", untrusted={"crawl:home": "mail me at a@b.io"})
    _gw(p).generate(TASK, req, Case)
    assert '<untrusted_data source="crawl:home">' in p.calls[0].user
    assert "a@b.io" not in p.calls[0].user


def test_cost_accumulates_in_budget() -> None:
    budget = Budget(cap_usd=10)
    p = FakeProvider([ok('{"title": "T", "steps": []}', input=1_000_000, output=0)])
    _gw(p, budget=budget).generate(TASK, _req(), Case)
    assert budget.spent_usd == pytest.approx(4.0)


@pytest.mark.parametrize("bad", [0, 4])
def test_max_attempts_bounds(bad: int) -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        _gw(FakeProvider([]), max_attempts=bad)
