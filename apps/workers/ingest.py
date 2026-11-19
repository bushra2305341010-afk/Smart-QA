"""Ingest worker (pipeline stage 1): parse uploaded sources into citable chunks.

For each pending source: read the original from object storage → parse (raw page texts) →
`chunk_pages` (normalise once, offsets + page + line) → store the normalised text next to the
original → replace the source's chunks → `ready`. A file that cannot be parsed is flagged
`failed` with a reason; it never stops the other sources (docs/03 §3 "parsed or flagged").
"""

from __future__ import annotations

import logging
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.models import Chunk, Source
from apps.api.db.session import project_session
from apps.api.storage import ObjectStore, sha256_hex, source_key, text_key
from apps.orchestrator import engine
from apps.orchestrator.machine import TransitionError
from apps.workers.git_source import check_repo_url, clone, collect, split_ref
from packages.analyzers.code.facts import extract_facts, render_repo_text
from packages.citations.chunker import ChunkedDocument, chunk_pages
from packages.citations.parsers import parse

log = logging.getLogger(__name__)
WORKER = engine.Actor("system", "worker:ingest")
MAX_ERROR = 500


@dataclass(frozen=True)
class IngestSummary:
    ready: int
    failed: int


def _finish(factory: sessionmaker[Session], pid: uuid.UUID, sid: uuid.UUID, **values: Any) -> None:
    with project_session(factory, pid) as s:
        src = s.get_one(Source, sid)
        for name, value in values.items():
            setattr(src, name, value)


@dataclass(frozen=True)
class GitOptions:
    """Read-only token for private repos (from the environment) and allowed protocols."""

    token: str | None = None
    protocols: tuple[str, ...] = ("https",)


def _repo_doc(uri: str, sid: uuid.UUID, git: GitOptions) -> ChunkedDocument:
    url, ref = split_ref(uri)
    url = check_repo_url(url, git.protocols)
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "repo"
        commit = clone(url, dest, ref=ref, token=git.token, protocols=git.protocols)
        files = collect(dest, commit)
    label = f"{url}@{commit[:12]}"
    return chunk_pages(str(sid), [render_repo_text(label, extract_facts(files.code), files.docs)])


def ingest_source(
    factory: sessionmaker[Session],
    store: ObjectStore,
    pid: uuid.UUID,
    sid: uuid.UUID,
    git: GitOptions | None = None,
) -> str:
    """Parse one source. Returns its final status (`ready` or `failed`)."""
    with project_session(factory, pid) as s:
        src = s.get_one(Source, sid)
        src.status = "parsing"
        kind, sha, uri = src.kind, src.sha256, src.uri
    try:
        if kind == "repo":
            doc = _repo_doc(uri, sid, git or GitOptions())
            sha = sha256_hex(doc.text.encode("utf-8"))
        else:
            doc = chunk_pages(str(sid), parse(kind, store.get(source_key(sha))))
        if not doc.text.strip():
            raise ValueError("No text found (scanned PDF without a text layer?)")
    except KeyError:
        _finish(factory, pid, sid, status="failed", error="Original file was never uploaded")
        return "failed"
    except Exception as exc:  # any parser error flags the file, the run continues
        log.warning("ingest failed for source %s: %s", sid, exc)
        _finish(
            factory, pid, sid, status="failed", error=f"{type(exc).__name__}: {exc}"[:MAX_ERROR]
        )
        return "failed"
    store.put(text_key(sha), doc.text.encode("utf-8"), "text/plain; charset=utf-8")
    with project_session(factory, pid) as s:
        s.execute(delete(Chunk).where(Chunk.source_id == sid))
        s.add_all(
            Chunk(
                project_id=pid, source_id=sid, text=c.text, start_offset=c.start_offset,
                end_offset=c.end_offset, page=c.page, line=c.line,
            )
            for c in doc.chunks
        )  # fmt: skip
        src = s.get_one(Source, sid)
        src.status, src.text_key, src.error, src.sha256 = "ready", text_key(sha), None, sha
    return "ready"


def run_ingest(
    factory: sessionmaker[Session],
    store: ObjectStore,
    pid: uuid.UUID,
    git: GitOptions | None = None,
) -> IngestSummary:
    """Parse every pending (or interrupted) source of the project."""
    with project_session(factory, pid) as s:
        todo = s.scalars(
            select(Source.id)
            .where(Source.status.in_(("pending", "parsing")))
            .order_by(Source.created_at)
        ).all()
    results = [ingest_source(factory, store, pid, sid, git) for sid in todo]
    with project_session(factory, pid) as s:
        ready = len(s.scalars(select(Source.id).where(Source.status == "ready")).all())
    return IngestSummary(ready=ready, failed=results.count("failed"))


def _send(factory: sessionmaker[Session], pid: uuid.UUID, event: str, **payload: Any) -> bool:
    try:
        with project_session(factory, pid) as s:
            engine.transition(s, pid, event, WORKER, payload=payload or None)
        return True
    except TransitionError as exc:
        log.info("pipeline moved on; %s", exc)
        return False


def handle_ingest_job(
    factory: sessionmaker[Session],
    store: ObjectStore,
    message: dict[str, Any],
    git: GitOptions | None = None,
) -> None:
    """Job handler for `job.ingest`: report start, ingest, then complete or fail the stage."""
    pid = uuid.UUID(message["project_id"])
    _send(factory, pid, "job_started")  # a redelivered job may already be running
    summary = run_ingest(factory, store, pid, git)
    if summary.ready:
        _send(factory, pid, "sources_parsed", ready=summary.ready, failed=summary.failed)
    else:
        _send(factory, pid, "job_failed", reason="No source could be parsed", failed=summary.failed)
