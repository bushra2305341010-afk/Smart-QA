"""Flake classification eval (sector 06 Change safety, target >= 85%).

`python -m evals.run_flake_eval [--set evals/datasets/flakes.jsonl]`

Each row is a labelled pair of attempts (first failure + clean re-run) with the human label
`flaky` or `fail`. The Judge rules run on them with a verified quote; we report:
- accuracy: verdict == label (Unable to Verify counts as a miss, it is a safe miss);
- false-bug rate: share of `flaky` rows the rules call `fail` (a false bug, must stay 0).
The shipped set is a seed set written from typical failure shapes; replace or extend it with
human-confirmed labels from real runs (docs/21 A2) before trusting the number.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from packages.contracts.run import AttemptResult, VerdictDecision
from packages.verdicts.rules import decide

DEFAULT = Path(__file__).parent / "datasets" / "flakes.jsonl"
TARGET = 0.85


@dataclass(frozen=True)
class FlakeScore:
    total: int
    correct: int
    false_bugs: int
    flaky_rows: int
    misses: list[str]

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    @property
    def false_bug_rate(self) -> float:
        return self.false_bugs / self.flaky_rows if self.flaky_rows else 0.0


def score(path: Path = DEFAULT) -> FlakeScore:
    total = correct = false_bugs = flaky_rows = 0
    misses: list[str] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        out = decide(
            AttemptResult.model_validate(row["first"]),
            AttemptResult.model_validate(row["rerun"]),
            citation_verified=True,
        )
        verdict = out.verdict if isinstance(out, VerdictDecision) else "rerun"
        total += 1
        flaky_rows += row["label"] == "flaky"
        if verdict == row["label"]:
            correct += 1
        else:
            misses.append(f"{row['id']}: label {row['label']}, judged {verdict}")
        false_bugs += row["label"] == "flaky" and verdict == "fail"
    return FlakeScore(total, correct, false_bugs, flaky_rows, misses)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set", type=Path, default=DEFAULT)
    args = parser.parse_args(argv)
    result = score(args.set)
    print(f"rows {result.total}  accuracy {result.accuracy:.1%}  "
          f"false-bug rate {result.false_bug_rate:.1%}  (target >= {TARGET:.0%})")  # fmt: skip
    for miss in result.misses:
        print("  miss", miss)
    return 0 if result.accuracy >= TARGET and result.false_bugs == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
