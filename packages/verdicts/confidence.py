"""Confidence from fixed signals (docs/08-agent.md §5 rule 7). No model decides the level; an
optional semantic judge score is one bounded signal among several."""

from __future__ import annotations

from dataclasses import dataclass

from packages.contracts.run import ConfidenceLevel

HIGH, MEDIUM = 0.8, 0.5


@dataclass(frozen=True)
class Signals:
    same_failure_twice: bool = False
    http_status_known: bool = False
    dom_match: bool = False  # the assertion captured expected vs actual from the page
    evidence: bool = False  # at least one stored artifact (screenshot/trace)
    judge_score: float | None = None  # 0..1 semantic match from the Judge model, if used


WEIGHTS = {"same": 0.35, "http": 0.15, "dom": 0.25, "evidence": 0.15, "judge": 0.10}


def score(sig: Signals) -> float:
    total = (
        WEIGHTS["same"] * sig.same_failure_twice
        + WEIGHTS["http"] * sig.http_status_known
        + WEIGHTS["dom"] * sig.dom_match
        + WEIGHTS["evidence"] * sig.evidence
    )
    if sig.judge_score is None:
        total /= 1 - WEIGHTS["judge"]  # rescale so a missing judge does not cap confidence
    else:
        total += WEIGHTS["judge"] * min(max(sig.judge_score, 0.0), 1.0)
    return round(min(total, 1.0), 4)


def level(value: float) -> ConfidenceLevel:
    if value >= HIGH:
        return "high"
    if value >= MEDIUM:
        return "medium"
    return "low"
