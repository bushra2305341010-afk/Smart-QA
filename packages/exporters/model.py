"""Plain data for exports (filled by the API/worker from the database; no DB code here)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CaseRow:
    code: str
    journey: str
    segment: str
    role: str
    technique: str
    priority: str
    preconditions: list[str]
    steps: list[str]
    data: dict[str, str]
    expected: str
    source: str
    quote: str
    citation_status: str
    requirement_id: str | None
    review_status: str


@dataclass(frozen=True)
class ResultRow:
    run: str
    case_code: str
    verdict: str
    confidence: float | None
    reason: str
    duration_ms: int | None
    browser: str | None
    evidence: list[str]
    attempt: int
    rule: str | None


@dataclass(frozen=True)
class BugRow:
    code: str
    title: str
    severity: str
    steps: list[str]
    expected: str
    quote: str
    actual: str
    evidence: list[str]
    environment: str
    tracker_ref: str | None
    status: str


@dataclass(frozen=True)
class CoverageRow:
    segment: str
    suggested: int
    approved: int
    executed: int
    counts: dict[str, int]


@dataclass(frozen=True)
class EvidenceRow:
    evidence_id: str
    kind: str
    sha256: str
    link: str
    captured_at: str


@dataclass(frozen=True)
class RunExport:
    project: str
    run: str
    cases: list[CaseRow] = field(default_factory=list)
    results: list[ResultRow] = field(default_factory=list)
    bugs: list[BugRow] = field(default_factory=list)
    coverage: list[CoverageRow] = field(default_factory=list)
    evidence: list[EvidenceRow] = field(default_factory=list)
