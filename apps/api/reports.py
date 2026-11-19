"""Read a run from the database into export/bug data (used by the API and the reporter)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api import ids
from apps.api.db.models import (
    Bug,
    Environment,
    Evidence,
    Plan,
    Project,
    Result,
    Run,
    Segment,
    Source,
    Step,
    TestCase,
    Verdict,
)
from packages.exporters.bug import BugFacts
from packages.exporters.model import (
    BugRow,
    CaseRow,
    CoverageRow,
    EvidenceRow,
    ResultRow,
    RunExport,
)


def _steps(s: Session, case_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
    out: dict[uuid.UUID, list[str]] = {c: [] for c in case_ids}
    for st in s.scalars(select(Step).where(Step.test_case_id.in_(case_ids)).order_by(Step.n)):
        out[st.test_case_id].append(st.action)
    return out


def _source_name(s: Session, citation: dict[str, Any] | None) -> str:
    sid = (citation or {}).get("source_id")
    if not sid:
        return ""
    src = s.get(Source, uuid.UUID(sid))
    return (src.filename or src.uri) if src else ""


def _evidence(s: Session, result_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[Evidence]]:
    out: dict[uuid.UUID, list[Evidence]] = {r: [] for r in result_ids}
    for ev in s.scalars(
        select(Evidence).where(Evidence.result_id.in_(result_ids)).order_by(Evidence.created_at)
    ):
        out[ev.result_id].append(ev)
    return out


def bug_facts(s: Session, verdict: Verdict) -> BugFacts:
    result = s.get_one(Result, verdict.result_id)
    case = s.get_one(TestCase, result.test_case_id)
    run = s.get_one(Run, result.run_id)
    env = s.get_one(Environment, run.env_id)
    citation = case.citation or {}
    evidence = _evidence(s, [result.id])[result.id]
    return BugFacts(
        case_code=case.code,
        case_title=str((case.preconditions or {}).get("title", case.code)),
        priority=case.priority,
        steps=_steps(s, [case.id])[case.id],
        data={k: str(v) for k, v in (case.data or {}).items()},
        expected=case.expected_text,
        quote=str(citation.get("quote", "")),
        source=_source_name(s, citation),
        actual=verdict.reason,
        environment=f"{env.name} ({env.kind}) {env.base_url}",
        evidence=[f"{e.kind} {e.sha256}" for e in evidence],
    )


def collect_run_export(s: Session, run: Run) -> RunExport:
    project = s.get_one(Project, run.project_id)
    plan = s.get_one(Plan, run.plan_id)
    segments = list(s.scalars(select(Segment).where(Segment.plan_id == plan.id)))
    seg_by_id = {seg.id: seg for seg in segments}
    cases = list(
        s.scalars(
            select(TestCase).where(TestCase.segment_id.in_(seg_by_id)).order_by(TestCase.code)
        )
    )
    steps = _steps(s, [c.id for c in cases])
    case_rows = []
    for c in cases:
        cit = c.citation or {}
        journey = str(seg_by_id[c.segment_id].techniques.get("journey", ""))
        case_rows.append(
            CaseRow(
                code=c.code,
                journey=journey,
                segment=journey,
                role=c.role,
                technique=c.technique,
                priority=c.priority,
                preconditions=list((c.preconditions or {}).get("items", [])),
                steps=steps[c.id],
                data={k: str(v) for k, v in (c.data or {}).items()},
                expected=c.expected_text,
                source=_source_name(s, cit),
                quote=str(cit.get("quote", "")),
                citation_status=str(cit.get("status", "")),
                requirement_id=c.requirement_id,
                review_status=c.review_status,
            )
        )
    code_by_id = {c.id: c.code for c in cases}
    results = list(
        s.scalars(
            select(Result)
            .where(Result.run_id == run.id)
            .order_by(Result.created_at, Result.attempt)
        )
    )
    verdicts = {
        v.result_id: v
        for v in s.scalars(select(Verdict).where(Verdict.result_id.in_([r.id for r in results])))
    }
    evidence = _evidence(s, [r.id for r in results])
    run_code = ids.encode("run", run.id)
    result_rows = []
    counts: dict[uuid.UUID, dict[str, int]] = {seg: {} for seg in seg_by_id}
    executed: dict[uuid.UUID, set[uuid.UUID]] = {seg: set() for seg in seg_by_id}
    seg_of_case = {c.id: c.segment_id for c in cases}
    for r in results:
        v = verdicts.get(r.id)
        verdict = v.verdict if v else r.status
        result_rows.append(
            ResultRow(
                run=run_code,
                case_code=code_by_id.get(r.test_case_id, "?"),
                verdict=verdict,
                confidence=v.confidence if v else None,
                reason=v.reason if v else "",
                duration_ms=r.duration_ms,
                browser=r.browser,
                evidence=[f"{e.kind} {e.sha256}" for e in evidence[r.id]],
                attempt=r.attempt,
                rule=v.rule if v else None,
            )
        )
        seg = seg_of_case.get(r.test_case_id)
        if seg is not None and v is not None:
            executed[seg].add(r.test_case_id)
            counts[seg][v.verdict] = counts[seg].get(v.verdict, 0) + 1
    bug_rows = []
    for bug, bug_verdict in s.execute(
        select(Bug, Verdict)
        .join(Verdict, Verdict.id == Bug.verdict_id)
        .join(Result, Result.id == Verdict.result_id)
        .where(Result.run_id == run.id)
        .order_by(Bug.created_at)
    ).all():
        facts = bug_facts(s, bug_verdict)
        bug_rows.append(
            BugRow(
                code=f"{facts.case_code}:{ids.encode('bug', bug.id)}",
                title=bug.title,
                severity=bug.severity,
                steps=facts.steps,
                expected=facts.expected,
                quote=facts.quote,
                actual=facts.actual,
                evidence=facts.evidence,
                environment=facts.environment,
                tracker_ref=bug.tracker_ref,
                status=bug.status,
            )
        )
    coverage = [
        CoverageRow(
            segment=str(seg.techniques.get("journey", "")),
            suggested=seg.suggested_count,
            approved=seg.approved_count or 0,
            executed=len(executed[seg.id]),
            counts=counts[seg.id],
        )
        for seg in sorted(segments, key=lambda x: str(x.techniques.get("journey", "")))
    ]
    evidence_rows = [
        EvidenceRow(
            ids.encode("res", e.result_id) + f":{e.step_n or 0}",
            e.kind,
            e.sha256,
            e.object_key,
            e.created_at.isoformat(),
        )
        for r in results
        for e in evidence[r.id]
    ]
    return RunExport(
        project=project.name,
        run=run_code,
        cases=case_rows,
        results=result_rows,
        bugs=bug_rows,
        coverage=coverage,
        evidence=evidence_rows,
    )
