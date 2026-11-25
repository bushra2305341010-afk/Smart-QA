"""Judge decision rules J1-J7 (docs/08-agent.md §5, sector 06). Pure code, 100% branches.

Guard order is the safety property: Blocked and Test Error are checked first (they are not about
the product), then the citation. **No path returns `pass` unless the expected result's quote is
verified** and at least one expectation was actually checked (pillar P3).

`decide(first, rerun, citation_verified)` returns a `VerdictDecision`, or `RERUN` when the first
attempt failed and no clean re-run exists yet (rule J1).
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.contracts.run import AttemptResult, VerdictDecision, VerdictValue
from packages.verdicts.confidence import Signals, level, score
from packages.verdicts.flake import features

FAILED = frozenset({"failed", "timed_out"})
OUR_FAULT = frozenset({"locator", "script"})
DETERMINISTIC = 0.9  # detectors and the policy are code, so their verdicts are high confidence


@dataclass(frozen=True)
class Rerun:
    reason: str = "Failed once; re-running in a clean browser context (J1)"


RERUN = Rerun()


def _verdict(
    verdict: VerdictValue, rule: str, reason: str, confidence: float = DETERMINISTIC
) -> VerdictDecision:
    return VerdictDecision(
        verdict=verdict, confidence=confidence, level=level(confidence), reason=reason, rule=rule
    )


def _blocked(r: AttemptResult) -> VerdictDecision | None:
    if r.blocked is None:
        return None
    detail = f": {r.blocked_reason}" if r.blocked_reason else ""
    return _verdict("blocked", f"J5.{r.blocked}", f"Blocked by {r.blocked}{detail}")


def _test_error(r: AttemptResult) -> VerdictDecision | None:
    if r.status == "error" or (r.failure is not None and r.failure.kind in OUR_FAULT):
        what = r.failure.message if r.failure and r.failure.message else "the test script failed"
        return _verdict(
            "test_error", "J4.our_fault", f"Our test is at fault, not the product: {what}"
        )
    return None


def _not_product(r: AttemptResult) -> VerdictDecision | None:
    return _blocked(r) or _test_error(r)


def _signals(r: AttemptResult, same: bool, judge_score: float | None) -> Signals:
    dom = r.failure is not None and r.failure.actual is not None and r.failure.expected is not None
    return Signals(
        same_failure_twice=same,
        http_status_known=r.http_status is not None,
        dom_match=dom,
        evidence=r.evidence_count > 0,
        judge_score=judge_score,
    )


def decide(
    first: AttemptResult,
    rerun: AttemptResult | None,
    *,
    citation_verified: bool,
    judge_score: float | None = None,
) -> VerdictDecision | Rerun:
    early = _not_product(first)
    if early:
        return early
    if not citation_verified:
        return _verdict(
            "unable_to_verify", "J6.no_verified_quote",
            "The expected result has no verified source quote, so no verdict can be claimed",
        )  # fmt: skip
    if first.status == "skipped":
        return _verdict("unable_to_verify", "J6.not_run", "The case did not run")
    if first.status == "passed":
        if first.expectations_checked == 0:
            return _verdict(
                "unable_to_verify", "J6.nothing_checked",
                "The test finished but checked no expected result",
            )  # fmt: skip
        conf = 0.95 if first.evidence_count > 0 else 0.7
        return _verdict(
            "pass", "J0.pass_verified", "Expected result observed; quote verified", conf
        )

    # first attempt failed or timed out
    if rerun is None:
        return RERUN
    early = _not_product(rerun)
    if early:
        return early
    feats = features(first, rerun)
    if rerun.status == "passed":
        if feats.noisy:
            return _verdict(
                "flaky", "J2.pass_on_rerun_with_noise",
                "Failed, then passed on a clean re-run, with timing/network noise",
                0.8,
            )  # fmt: skip
        return _verdict(
            "unable_to_verify", "J2.pass_on_rerun_no_noise",
            "Failed, then passed on a clean re-run without noise evidence; a human should look",
            0.4,
        )  # fmt: skip
    if rerun.status not in FAILED:  # skipped re-run
        return _verdict("unable_to_verify", "J6.rerun_not_run", "The clean re-run did not run")
    if feats.same_signature:
        sig = _signals(rerun, True, judge_score)
        if not (sig.evidence or sig.dom_match):
            return _verdict(
                "unable_to_verify", "J6.weak_evidence",
                "Failed the same way twice but no evidence was captured",
                0.3,
            )  # fmt: skip
        value = score(sig)
        message = rerun.failure.message if rerun.failure else ""
        return _verdict(
            "fail", "J3.fail_same_twice", f"Failed the same way twice: {message}", value
        )
    if feats.noisy:
        return _verdict(
            "flaky", "J2.different_failures_with_noise",
            "Failed differently on each attempt, with timing/network noise",
            0.6,
        )  # fmt: skip
    return _verdict(
        "unable_to_verify", "J6.different_failures",
        "Failed differently on each attempt; a human should look",
        0.3,
    )  # fmt: skip
