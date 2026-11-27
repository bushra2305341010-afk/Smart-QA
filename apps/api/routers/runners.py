"""Runners: registration (users) and the runner protocol (runners), sector 05, T-103.

Protocol (`/runner/*`, `Authorization: Bearer saq_run_<project>_<secret>`):
`heartbeat` → `jobs/pull` (lease) → `PUT evidence/{sha256}` (content-addressed, hash checked)
→ `jobs/{id}/result` → next pull. A lease that is not renewed by heartbeats expires and the job
becomes claimable again; after `MAX_LEASES` losses the attempt is recorded as an error (Test
Error). Results are idempotent per (run, case, attempt).

mTLS: when a runner was registered with `cert_sha256`, every call must carry the client
certificate fingerprint in `X-Client-Cert-Sha256`, set by the TLS-terminating proxy (which must
strip any client-sent copy; deploy/README). Secrets never pass through here: jobs carry
`{{secret:name}}` placeholders and identity references, resolved on the runner (T-203).
"""

from __future__ import annotations

import hmac
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api import ids, runs
from apps.api.auth.deps import ProjectContext, get_factory, get_store, require
from apps.api.auth.tokens import hash_secret, new_secret
from apps.api.db import audit
from apps.api.db.models import Environment, Evidence, Identity, Run, Runner, RunnerJob, TestCase
from apps.api.db.session import project_session
from apps.api.errors import ApiError, not_found
from apps.api.storage import ObjectStore, evidence_key, sha256_hex
from apps.orchestrator import engine
from packages.contracts.run import AttemptResult, CompiledCase

router = APIRouter(tags=["runners"])
RUNNER_PREFIX = "saq_run_"
TOKEN = re.compile(r"^saq_run_([0-9a-f]{32})_([A-Za-z0-9_-]{20,})$")
LEASE = timedelta(minutes=10)
MAX_LEASES = 3
MAX_EVIDENCE_BYTES = 50 * 1024 * 1024
SHA256 = re.compile(r"^[0-9a-f]{64}$")
EvidenceKind = Literal["screenshot", "trace", "video", "har", "console", "request"]
CONTENT_TYPES = {
    "screenshot": "image/png", "trace": "application/zip", "video": "video/webm",
    "har": "application/json", "console": "text/plain", "request": "application/json",
}  # fmt: skip


# ---------- registration (users) ----------


class RunnerIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    cert_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class RunnerOut(BaseModel):
    id: str
    name: str
    status: str
    mtls: bool
    last_seen_at: datetime | None


class RunnerCreated(RunnerOut):
    token: str = Field(description="Shown once. Store it in the runner's environment.")


def _runner_out(r: Runner) -> RunnerOut:
    return RunnerOut(
        id=ids.encode("rnr", r.id), name=r.name, status=r.status,
        mtls=r.cert_sha256 is not None, last_seen_at=r.last_seen_at,
    )  # fmt: skip


@router.post("/projects/{project_id}/runners", status_code=201)
def register_runner(
    body: RunnerIn, ctx: ProjectContext = Depends(require("environments.manage"))
) -> RunnerCreated:
    token = f"{RUNNER_PREFIX}{ctx.project_id.hex}_{new_secret()}"
    with ctx.session() as s:
        runner = Runner(project_id=ctx.project_id, name=body.name, token_hash=hash_secret(token),
                        cert_sha256=body.cert_sha256)  # fmt: skip
        s.add(runner)
        s.flush()
        audit.record(
            s, project_id=ctx.project_id, actor=ids.encode("usr", ctx.principal.user_id),
            action="runner.registered", entity=ids.encode("rnr", runner.id),
            payload={"name": body.name, "mtls": body.cert_sha256 is not None},
        )  # fmt: skip
        return RunnerCreated(**_runner_out(runner).model_dump(), token=token)


@router.get("/projects/{project_id}/runners")
def list_runners(ctx: ProjectContext = Depends(require("project.view"))) -> list[RunnerOut]:
    with ctx.session() as s:
        return [_runner_out(r) for r in s.scalars(select(Runner).order_by(Runner.created_at))]


@router.delete("/projects/{project_id}/runners/{runner_id}", status_code=204)
def revoke_runner(
    runner_id: str, ctx: ProjectContext = Depends(require("environments.manage"))
) -> Response:
    rid = ids.decode("rnr", runner_id, "Runner")
    with ctx.session() as s:
        runner = s.get(Runner, rid)
        if runner is None:
            raise not_found("Runner")
        runner.status = "revoked"
        audit.record(
            s, project_id=ctx.project_id, actor=ids.encode("usr", ctx.principal.user_id),
            action="runner.revoked", entity=runner_id,
        )  # fmt: skip
    return Response(status_code=204)


# ---------- runner protocol ----------


class RunnerAuth(BaseModel):
    project_id: uuid.UUID
    runner_id: uuid.UUID

    @property
    def actor(self) -> engine.Actor:
        return engine.Actor("system", f"runner:{ids.encode('rnr', self.runner_id)}")


def runner_auth(
    request: Request, factory: sessionmaker[Session] = Depends(get_factory)
) -> RunnerAuth:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    m = TOKEN.match(token)
    if scheme.lower() != "bearer" or not m:
        raise ApiError(401, "UNAUTHENTICATED", "Use: Authorization: Bearer saq_run_...")
    pid = uuid.UUID(hex=m.group(1))
    with project_session(factory, pid) as s:
        runner = s.scalar(select(Runner).where(Runner.token_hash == hash_secret(token)))
        if runner is None or runner.status == "revoked":
            raise ApiError(401, "UNAUTHENTICATED", "Runner token is invalid or revoked")
        if runner.cert_sha256 is not None:
            sent = request.headers.get("x-client-cert-sha256", "").lower()
            if not hmac.compare_digest(sent, runner.cert_sha256):
                raise ApiError(401, "UNAUTHENTICATED", "Client certificate does not match")
        runner.status, runner.last_seen_at = "online", datetime.now(UTC)
        return RunnerAuth(project_id=pid, runner_id=runner.id)


class HeartbeatIn(BaseModel):
    version: str | None = Field(default=None, max_length=40)


class HeartbeatOut(BaseModel):
    ok: bool
    renewed: int


@router.post("/runner/heartbeat")
def heartbeat(
    body: HeartbeatIn,
    auth: RunnerAuth = Depends(runner_auth),
    factory: sessionmaker[Session] = Depends(get_factory),
) -> HeartbeatOut:
    """Renews this runner's leases; missing heartbeats let them expire (docs/06 §5)."""
    with project_session(factory, auth.project_id) as s:
        runner = s.get_one(Runner, auth.runner_id)
        runner.version = body.version or runner.version
        jobs = s.scalars(
            select(RunnerJob).where(
                RunnerJob.runner_id == auth.runner_id, RunnerJob.status == "leased"
            )
        ).all()
        for job in jobs:
            job.leased_until = datetime.now(UTC) + LEASE
        return HeartbeatOut(ok=True, renewed=len(jobs))


class EnvOut(BaseModel):
    kind: str
    base_url: str
    allowed_hosts: list[str]
    safe_actions: dict[str, object]


class IdentityRef(BaseModel):
    role_name: str
    secret_ref: str


class JobOut(BaseModel):
    job_id: str
    run_id: str
    case_id: str
    code: str
    attempt: int
    lease_seconds: int
    case: CompiledCase
    env: EnvOut
    identities: list[IdentityRef]


def _claim(s: Session, pid: uuid.UUID, runner_id: uuid.UUID) -> RunnerJob | None:
    now = datetime.now(UTC)
    while True:
        job = s.scalar(
            select(RunnerJob)
            .where(
                or_(
                    RunnerJob.status == "queued",
                    (RunnerJob.status == "leased") & (RunnerJob.leased_until < now),
                )
            )
            .order_by(RunnerJob.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if job is None:
            return None
        if job.status == "leased" and job.leases >= MAX_LEASES:  # lost too often: give up
            job.status = "lost"
            runs.write_result(s, pid, job.run_id, job.test_case_id, runs.error_result(
                job.attempt, f"Runner lost the job {job.leases} times"))  # fmt: skip
            runs.finish_if_done(s, pid, job.run_id, engine.Actor("system", "runner:lease"))
            continue
        job.status, job.runner_id = "leased", runner_id
        job.leased_until, job.leases = now + LEASE, job.leases + 1
        return job


@router.post("/runner/jobs/pull", response_model=None)
def pull_job(
    auth: RunnerAuth = Depends(runner_auth),
    factory: sessionmaker[Session] = Depends(get_factory),
    store: ObjectStore = Depends(get_store),
) -> JobOut | Response:
    with project_session(factory, auth.project_id) as s:
        job = _claim(s, auth.project_id, auth.runner_id)
        if job is None:
            return Response(status_code=204)
        run = s.get_one(Run, job.run_id)
        env = s.get_one(Environment, run.env_id)
        case = s.get_one(TestCase, job.test_case_id)
        compiled = CompiledCase.model_validate_json(store.get(f"compiled/{job.test_case_id}.json"))
        identities = [
            IdentityRef(role_name=i.role_name, secret_ref=i.secret_ref)
            for i in s.scalars(select(Identity).where(Identity.env_id == env.id))
        ]
        return JobOut(
            job_id=ids.encode("job", job.id), run_id=ids.encode("run", run.id),
            case_id=ids.encode("tc", case.id), code=case.code, attempt=job.attempt,
            lease_seconds=int(LEASE.total_seconds()), case=compiled,
            env=EnvOut(kind=env.kind, base_url=env.base_url, allowed_hosts=env.allowed_hosts,
                       safe_actions=env.safe_actions),
            identities=identities,
        )  # fmt: skip


@router.put("/runner/evidence/{sha256}", status_code=201)
async def upload_evidence(
    sha256: str,
    request: Request,
    kind: EvidenceKind,
    auth: RunnerAuth = Depends(runner_auth),
    store: ObjectStore = Depends(get_store),
) -> dict[str, object]:
    if not SHA256.match(sha256):
        raise ApiError(400, "VALIDATION_ERROR", "sha256 must be 64 lowercase hex characters")
    data = await request.body()
    if len(data) > MAX_EVIDENCE_BYTES:
        raise ApiError(413, "TOO_LARGE", "Evidence over 50 MB")
    if sha256_hex(data) != sha256:
        raise ApiError(422, "HASH_MISMATCH", "Body does not match its sha256")
    store.put(evidence_key(sha256), data, CONTENT_TYPES[kind])
    return {"sha256": sha256, "size": len(data)}


class EvidenceRef(BaseModel):
    kind: EvidenceKind
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size: int = Field(ge=0)
    step_n: int | None = None


class ResultIn(BaseModel):
    result: AttemptResult
    browser: str | None = Field(default=None, max_length=60)
    evidence: list[EvidenceRef] = Field(default_factory=list, max_length=500)


class ResultOut(BaseModel):
    result_id: str
    created: bool
    run_finished: bool


@router.post("/runner/jobs/{job_id}/result")
def report_result(
    job_id: str,
    body: ResultIn,
    auth: RunnerAuth = Depends(runner_auth),
    factory: sessionmaker[Session] = Depends(get_factory),
    store: ObjectStore = Depends(get_store),
) -> ResultOut:
    jid = ids.decode("job", job_id, "Job")
    with project_session(factory, auth.project_id) as s:
        job = s.get(RunnerJob, jid)
        if job is None:
            raise not_found("Job")
        if job.status == "leased" and job.runner_id != auth.runner_id:
            raise ApiError(409, "STATE_CONFLICT", "This job is leased by another runner")
        if body.result.attempt != job.attempt:
            raise ApiError(422, "VALIDATION_ERROR", "attempt does not match the job")
        for ref in body.evidence:
            try:
                stored = store.get(evidence_key(ref.sha256))
            except Exception:  # KeyError (memory) or NoSuchKey (S3)
                raise ApiError(422, "EVIDENCE_MISSING", f"Upload {ref.sha256} first") from None
            if sha256_hex(stored) != ref.sha256:
                raise ApiError(422, "HASH_MISMATCH", f"Stored evidence {ref.sha256} is corrupt")
        row, created = runs.write_result(
            s, auth.project_id, job.run_id, job.test_case_id, body.result, body.browser
        )
        if created:
            for ref in body.evidence:
                s.add(Evidence(project_id=auth.project_id, result_id=row.id, step_n=ref.step_n,
                               kind=ref.kind, sha256=ref.sha256, size=ref.size,
                               object_key=evidence_key(ref.sha256)))  # fmt: skip
        job.status = "done"
        finished = runs.finish_if_done(s, auth.project_id, job.run_id, auth.actor)
        return ResultOut(result_id=ids.encode("res", row.id), created=created,
                         run_finished=finished)  # fmt: skip
