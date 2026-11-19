"""Reporter (sector 07): bug drafts from Fail verdicts, run workbook, filing after Gate 4.

- `draft_bugs` turns every `fail` verdict of a run without a bug into a draft (never `flaky`,
  `blocked`, `test_error` or `unable_to_verify`: those are not product bugs). The Judge stage
  calls it before `verdicts_ready`.
- `job.report` (after Gate 4) stores the run workbook in object storage and files each
  *confirmed*, unfiled bug to the project's tracker, then completes the pipeline.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from apps.api import ids
from apps.api.db import audit
from apps.api.db.models import Bug, Project, Result, Run, Verdict
from apps.api.db.session import project_session
from apps.api.reports import bug_facts, collect_run_export
from apps.api.storage import ObjectStore
from apps.api.trackers import TrackerFactory
from apps.orchestrator import engine
from apps.orchestrator.machine import TransitionError
from packages.exporters.bug import draft_bug
from packages.exporters.evidence_pack import build_evidence_pack
from packages.exporters.excel import build_workbook
from packages.exporters.trackers.github import TrackerError

log = logging.getLogger(__name__)
WORKER = engine.Actor("system", "worker:reporter")
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def draft_bugs(factory: sessionmaker[Session], pid: uuid.UUID, run_id: uuid.UUID) -> int:
    """Create a draft for each Fail verdict of the run that has no bug yet."""
    created = 0
    with project_session(factory, pid) as s:
        verdicts = s.scalars(
            select(Verdict)
            .join(Result, Result.id == Verdict.result_id)
            .outerjoin(Bug, Bug.verdict_id == Verdict.id)
            .where(Result.run_id == run_id, Verdict.verdict == "fail", Bug.id.is_(None))
            .order_by(Verdict.created_at)
        ).all()
        for verdict in verdicts:
            draft = draft_bug(bug_facts(s, verdict))
            s.add(
                Bug(
                    project_id=pid,
                    verdict_id=verdict.id,
                    title=draft.title,
                    severity=draft.severity,
                    body_md=draft.body_md,
                )
            )
            created += 1
    return created


def report_key(run_id: uuid.UUID) -> str:
    return f"reports/{run_id}.xlsx"


def pack_key(run_id: uuid.UUID) -> str:
    return f"reports/{run_id}-evidence.html"


def file_confirmed(
    factory: sessionmaker[Session], make_tracker: TrackerFactory, pid: uuid.UUID
) -> tuple[int, int]:
    """File confirmed bugs. Returns (filed, failed). No tracker configured → nothing filed."""
    with project_session(factory, pid) as s:
        settings = s.scalar(select(Project.settings).where(Project.id == pid)) or {}
        tracker = make_tracker(settings)
        todo = [
            (b.id, b.title, b.body_md, b.severity)
            for b in s.scalars(
                select(Bug).where(Bug.status == "confirmed", Bug.tracker_ref.is_(None))
            )
        ]
    if tracker is None:
        return 0, 0
    filed = failed = 0
    for bug_id, title, body, severity in todo:
        try:
            issue = tracker.file(title, body, ["smart-qa", f"severity:{severity}"])
        except TrackerError as exc:
            log.warning("filing %s failed: %s", bug_id, exc)
            failed += 1
            continue
        with project_session(factory, pid) as s:
            bug = s.get_one(Bug, bug_id)
            bug.status, bug.tracker, bug.tracker_ref = "filed", "github", issue.url
            audit.record(
                s, project_id=pid, actor=WORKER.id, action="bug.filed",
                entity=ids.encode("bug", bug_id), payload={"tracker_ref": issue.url},
            )  # fmt: skip
        filed += 1
    return filed, failed


def handle_report_job(
    factory: sessionmaker[Session],
    store: ObjectStore,
    make_tracker: TrackerFactory,
    message: dict[str, Any],
) -> None:
    pid = uuid.UUID(message["project_id"])

    def send(event: str, **payload: Any) -> None:
        try:
            with project_session(factory, pid) as s:
                engine.transition(s, pid, event, WORKER, payload=payload or None)
        except TransitionError as exc:
            log.info("pipeline moved on; %s", exc)

    send("job_started")
    with project_session(factory, pid) as s:
        run = s.scalar(select(Run).order_by(Run.created_at.desc()).limit(1))
        export = collect_run_export(s, run) if run else None
        run_id = run.id if run else None
    if export is not None and run_id is not None:
        store.put(report_key(run_id), build_workbook(export), XLSX)
        store.put(
            pack_key(run_id), build_evidence_pack(export).encode(), "text/html; charset=utf-8"
        )
    filed, failed = file_confirmed(factory, make_tracker, pid)
    if failed:
        send("job_failed", reason=f"{failed} bug(s) could not be filed", filed=filed)
        return
    send("reported", filed=filed, workbook=report_key(run_id) if run_id else None)
