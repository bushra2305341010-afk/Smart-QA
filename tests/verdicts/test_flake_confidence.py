from packages.contracts.run import AttemptResult, Failure
from packages.verdicts.confidence import Signals, level, score
from packages.verdicts.flake import features, signature


def res(**kw: object) -> AttemptResult:
    base: dict[str, object] = {"attempt": 1, "status": "failed", "duration_ms": 1000}
    return AttemptResult(**{**base, **kw})


def test_signature_ignores_volatile_numbers() -> None:
    a = res(failure=Failure(kind="timeout", message="Timeout 3000ms at id 7f3a9b2c1d", step_n=2))
    b = res(failure=Failure(kind="timeout", message="Timeout 5000ms at id 0a1b2c3d4e", step_n=2))
    assert signature(a) == signature(b)
    assert signature(res()) is None


def test_features() -> None:
    quiet = res()
    assert not features(quiet, quiet).noisy
    assert features(res(status="timed_out"), quiet).timing_noise
    assert features(res(failure=Failure(kind="timeout")), quiet).timing_noise
    assert features(res(duration_ms=100), quiet).timing_noise
    assert features(res(failure=Failure(kind="network")), quiet).network_noise
    assert features(res(http_status=503), res(http_status=200)).network_noise
    assert not features(res(http_status=503), res(http_status=503)).network_noise
    assert features(res(console_errors=1), quiet).console_noise
    same = res(failure=Failure(kind="assertion", message="x"))
    assert features(same, same).same_signature
    assert not features(quiet, quiet).same_signature


def test_confidence_levels() -> None:
    assert score(Signals()) == 0
    full = Signals(True, True, True, True)
    assert score(full) == 1.0 and level(score(full)) == "high"
    assert score(Signals(True, True, True, True, judge_score=1.0)) == 1.0
    assert score(Signals(judge_score=5.0)) == 0.1  # clamped
    assert score(Signals(judge_score=-1.0)) == 0
    assert level(0.5) == "medium" and level(0.49) == "low" and level(0.8) == "high"
