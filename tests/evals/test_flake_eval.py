from pathlib import Path

from evals.run_flake_eval import TARGET, main, score


def test_flake_eval_meets_target_with_no_false_bugs() -> None:
    result = score()
    assert result.total >= 30
    assert result.accuracy >= TARGET
    assert result.false_bugs == 0 and result.false_bug_rate == 0
    assert main([]) == 0


def test_flake_eval_fails_below_target(tmp_path: Path) -> None:
    bad = tmp_path / "set.jsonl"
    row = ('{"id": "X", "label": "flaky", "first": {"attempt": 1, "status": "failed", '
           '"failure": {"kind": "assertion", "message": "m"}}, "rerun": {"attempt": 2, '
           '"status": "failed", "failure": {"kind": "assertion", "message": "m"}, '
           '"evidence_count": 1}}\n\n')  # fmt: skip
    bad.write_text(row)
    result = score(bad)
    assert result.false_bugs == 1 and result.false_bug_rate == 1.0 and result.misses
    assert main(["--set", str(bad)]) == 1
    empty = tmp_path / "empty.jsonl"
    empty.write_text("")
    assert score(empty).accuracy == 0.0 and score(empty).false_bug_rate == 0.0
