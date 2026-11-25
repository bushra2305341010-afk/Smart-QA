"""One row per rule J0-J7 (docs/08-agent.md §5). A Pass without a verified quote is impossible."""

import itertools
from typing import Any

import pytest

from packages.contracts.run import AttemptResult, Failure, VerdictDecision
from packages.verdicts.rules import RERUN, Rerun, decide


def att(status: str = "passed", n: int = 1, **kw: Any) -> AttemptResult:
    defaults: dict[str, Any] = {"duration_ms": 1000, "evidence_count": 3, "expectations_checked": 1}
    return AttemptResult(attempt=n, status=status, **{**defaults, **kw})


def fail(n: int = 1, kind: str = "assertion", msg: str = "Expected 'Total 10' got 'Total 9'",
         **kw: Any) -> AttemptResult:  # fmt: skip
    failure = Failure(kind=kind, message=msg, step_n=3, expected="Total 10", actual="Total 9")
    return att("failed", n, failure=failure, **kw)


ROWS = [
    # (first, rerun, citation_verified, verdict, rule)
    (att(), None, True, "pass", "J0.pass_verified"),
    (att(), None, False, "unable_to_verify", "J6.no_verified_quote"),
    (att(expectations_checked=0), None, True, "unable_to_verify", "J6.nothing_checked"),
    (att("skipped"), None, True, "unable_to_verify", "J6.not_run"),
    (att("failed", blocked="captcha"), None, True, "blocked", "J5.captcha"),
    (
        att("failed", blocked="policy", blocked_reason="Delete blocked"),
        None,
        False,
        "blocked",
        "J5.policy",
    ),
    (att("error"), None, True, "test_error", "J4.our_fault"),
    (fail(kind="locator", msg="no element"), None, True, "test_error", "J4.our_fault"),
    (fail(), fail(2), False, "unable_to_verify", "J6.no_verified_quote"),
    (fail(), att(n=2), True, "unable_to_verify", "J2.pass_on_rerun_no_noise"),
    (fail(duration_ms=9000), att(n=2), True, "flaky", "J2.pass_on_rerun_with_noise"),
    (fail(network_errors=2), att(n=2), True, "flaky", "J2.pass_on_rerun_with_noise"),
    (fail(), att("skipped", 2), True, "unable_to_verify", "J6.rerun_not_run"),
    (fail(), att("failed", 2, blocked="env_down"), True, "blocked", "J5.env_down"),
    (fail(), fail(2, kind="script", msg="TypeError"), True, "test_error", "J4.our_fault"),
    (fail(), fail(2), True, "fail", "J3.fail_same_twice"),
    (fail(msg="took 1200ms"), fail(2, msg="took 1350ms"), True, "fail", "J3.fail_same_twice"),
    (
        fail(evidence_count=0),
        AttemptResult(
            attempt=2,
            status="failed",
            duration_ms=1000,
            failure=Failure(
                kind="assertion", message="Expected 'Total 10' got 'Total 9'", step_n=3
            ),
        ),
        True,
        "unable_to_verify",
        "J6.weak_evidence",
    ),
    (fail(), fail(2, msg="other text"), True, "unable_to_verify", "J6.different_failures"),
    (fail(console_errors=3), fail(2, msg="x"), True, "flaky", "J2.different_failures_with_noise"),
]


@pytest.mark.parametrize(("first", "rerun", "cited", "verdict", "rule"), ROWS)
def test_rules(
    first: AttemptResult, rerun: AttemptResult | None, cited: bool, verdict: str, rule: str
) -> None:
    out = decide(first, rerun, citation_verified=cited)
    assert isinstance(out, VerdictDecision)
    assert (out.verdict, out.rule) == (verdict, rule)
    assert out.reason


def test_first_failure_asks_for_rerun() -> None:
    assert decide(fail(), None, citation_verified=True) is RERUN
    assert isinstance(RERUN, Rerun) and RERUN.reason


def test_us07_fail_same_twice_is_high_confidence() -> None:
    out = decide(fail(http_status=200), fail(2, http_status=200), citation_verified=True)
    assert isinstance(out, VerdictDecision)
    assert out.verdict == "fail" and out.level == "high"


def test_pass_without_evidence_is_lower_confidence() -> None:
    out = decide(att(evidence_count=0), None, citation_verified=True)
    assert isinstance(out, VerdictDecision) and out.level == "medium"


def test_blocked_reason_mentions_detail() -> None:
    out = decide(
        att("failed", blocked="mfa", blocked_reason="OTP prompt"), None, citation_verified=True
    )
    assert isinstance(out, VerdictDecision) and "OTP prompt" in out.reason


STATUSES = ["passed", "failed", "error", "skipped", "timed_out"]
FAILURES: list[Failure | None] = [
    None,
    *(Failure(kind=k, message="m") for k in ("assertion", "locator", "timeout", "network")),
]


def grid(n: int) -> list[AttemptResult]:
    """Every combination of the inputs that steer the rules (exhaustive, small)."""
    return [
        AttemptResult(
            attempt=n,
            status=status,
            duration_ms=dur,
            failure=failure,
            blocked=blocked,
            network_errors=net,
            evidence_count=ev,
            expectations_checked=chk,
        )
        for status, failure, blocked, dur, net, ev, chk in itertools.product(
            STATUSES, FAILURES, [None, "captcha"], [100, 1000], [0, 1], [0, 1], [0, 1]
        )
    ]


FIRSTS = grid(1)
RERUNS: list[AttemptResult | None] = [None, *grid(2)[::7]]


def test_pass_is_impossible_without_verified_quote() -> None:
    for first, rerun in itertools.product(FIRSTS, RERUNS):
        out = decide(first, rerun, citation_verified=False)
        assert isinstance(out, Rerun) or (out.verdict != "pass" and out.rule)


def test_pass_requires_a_passed_first_attempt_with_a_checked_expectation() -> None:
    for first, rerun in itertools.product(FIRSTS, RERUNS):
        out = decide(first, rerun, citation_verified=True)
        if isinstance(out, VerdictDecision) and out.verdict == "pass":
            assert first.status == "passed" and first.expectations_checked > 0
            assert first.blocked is None
