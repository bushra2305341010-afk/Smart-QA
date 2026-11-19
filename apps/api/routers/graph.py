"""Product Understanding Graph: browse, review nodes, approve (Gate 1) — US-02, sector 02.

Routes are nested under the project so `require()` can scope row-level security before any
lookup. Approval is refused while any node is still pending, and it moves the pipeline in the
same transaction, so a graph can never be "approved" while the pipeline disagrees.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api import ids
from apps.api.auth.deps import ProjectContext, require
from apps.api.db import audit
from apps.api.db.models import (
    Chunk,
    Edge,
    Feedback,
    GraphVersion,
    Node,
    NodeCitation,
    Project,
    Source,
)
from apps.api.errors import ApiError, conflict, not_found
from apps.orchestrator import engine
from apps.orchestrator.guards import GuardError
from apps.orchestrator.machine import TransitionError
from packages.graph.brief import build_brief
from packages.planning.from_graph import EdgeView, NodeView

router = APIRouter(tags=["graph"])


class CitationOut(BaseModel):
    source_id: str
    file: str | None
    quote: str
    start_offset: int
    end_offset: int
    page: int | None
    line: int | None
    status: str


class NodeOut(BaseModel):
    id: str
    type: str
    label: str
    attrs: dict[str, Any]
    review_status: str
    citations: list[CitationOut]


class EdgeOut(BaseModel):
    from_id: str
    to_id: str
    kind: str


class VersionOut(BaseModel):
    id: str
    number: int
    status: str
    approved_at: datetime | None
    nodes: int
    pending: int


class GraphOut(BaseModel):
    version: VersionOut
    nodes: list[NodeOut]
    edges: list[EdgeOut]


class ReviewIn(BaseModel):
    review_status: Literal["approved", "rejected", "edited"]
    label: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def _label_for_edit(self) -> ReviewIn:
        if (self.review_status == "edited") != (self.label is not None):
            raise ValueError("label is required for 'edited' and only allowed with it")
        return self


def _version_out(s: Session, gv: GraphVersion) -> VersionOut:
    total, pending = s.execute(
        select(func.count(), func.count().filter(Node.review_status == "pending")).where(
            Node.graph_version_id == gv.id
        )
    ).one()
    return VersionOut(
        id=ids.encode("gv", gv.id),
        number=gv.number,
        status=gv.status,
        approved_at=gv.approved_at,
        nodes=total,
        pending=pending,
    )


def _version(s: Session, version_id: str) -> GraphVersion:
    gv = s.get(GraphVersion, ids.decode("gv", version_id, "Graph version"))
    if gv is None:
        raise not_found("Graph version")
    return gv


@router.get("/projects/{project_id}/graph")
def list_versions(ctx: ProjectContext = Depends(require("project.view"))) -> list[VersionOut]:
    with ctx.session() as s:
        versions = s.scalars(select(GraphVersion).order_by(GraphVersion.number.desc())).all()
        return [_version_out(s, gv) for gv in versions]


@router.get("/projects/{project_id}/graph/{version_id}")
def get_graph(
    version_id: str,
    ctx: ProjectContext = Depends(require("project.view")),
    type: str | None = None,
) -> GraphOut:
    """Nodes with their exact source quotes and locations; `?type=Conflict|Question|Rule…`."""
    with ctx.session() as s:
        gv = _version(s, version_id)
        stmt = select(Node).where(Node.graph_version_id == gv.id).order_by(Node.type, Node.label)
        if type:
            stmt = stmt.where(Node.type == type)
        nodes = s.scalars(stmt).all()
        node_ids = [n.id for n in nodes]
        cites: dict[uuid.UUID, list[CitationOut]] = {n: [] for n in node_ids}
        rows = s.execute(
            select(
                NodeCitation,
                Chunk.source_id,
                Chunk.page,
                Chunk.line,
                Chunk.text,
                Chunk.start_offset,
                Source.filename,
            )
            .join(Chunk, Chunk.id == NodeCitation.chunk_id)
            .join(Source, Source.id == Chunk.source_id)
            .where(NodeCitation.node_id.in_(node_ids))
            .order_by(NodeCitation.start_offset)
        ).all()
        for c, source_id, page, line, chunk_text, chunk_start, filename in rows:
            # Line of the quote itself: the chunk's first line + newlines before the quote.
            before = chunk_text[: max(0, c.start_offset - chunk_start)]
            quote_line = None if line is None else line + before.count("\n")
            cites[c.node_id].append(
                CitationOut(
                    source_id=ids.encode("src", source_id),
                    file=filename,
                    quote=c.quote,
                    start_offset=c.start_offset,
                    end_offset=c.end_offset,
                    page=page,
                    line=quote_line,
                    status=c.status,
                )
            )
        edges = s.scalars(
            select(Edge).where(Edge.from_node_id.in_(node_ids), Edge.to_node_id.in_(node_ids))
        ).all()
        return GraphOut(
            version=_version_out(s, gv),
            nodes=[
                NodeOut(
                    id=ids.encode("nod", n.id),
                    type=n.type,
                    label=n.label,
                    attrs=n.attrs,
                    review_status=n.review_status,
                    citations=cites[n.id],
                )
                for n in nodes
            ],
            edges=[
                EdgeOut(
                    from_id=ids.encode("nod", e.from_node_id),
                    to_id=ids.encode("nod", e.to_node_id),
                    kind=e.kind,
                )
                for e in edges
            ],
        )


@router.patch("/projects/{project_id}/graph/{version_id}/nodes/{node_id}")
def review_node(
    version_id: str,
    node_id: str,
    body: ReviewIn,
    ctx: ProjectContext = Depends(require("graph.approve")),
) -> NodeOut:
    """Approve, reject or edit one node. Each decision is a human-confirmed label (docs/21)."""
    with ctx.session() as s:
        gv = _version(s, version_id)
        if gv.status != "draft":
            raise conflict("Only a draft graph version can be reviewed")
        node = s.get(Node, ids.decode("nod", node_id, "Node"))
        if node is None or node.graph_version_id != gv.id:
            raise not_found("Node")
        before = {"label": node.label, "review_status": node.review_status}
        node.review_status = body.review_status
        if body.label is not None:
            node.label = body.label
        after = {"label": node.label, "review_status": node.review_status}
        decision = {"approved": "confirm", "rejected": "reject", "edited": "edit"}[
            body.review_status
        ]
        s.add(
            Feedback(
                project_id=ctx.project_id,
                entity="node",
                entity_id=node.id,
                decision=decision,
                before=before,
                after=after,
                actor_id=ctx.principal.user_id,
            )
        )
        audit.record(
            s,
            project_id=ctx.project_id,
            actor=ids.encode("usr", ctx.principal.user_id),
            action=f"graph.node.{body.review_status}",
            entity=ids.encode("nod", node.id),
            payload={"before": before, "after": after},
        )
        return NodeOut(
            id=node_id,
            type=node.type,
            label=node.label,
            attrs=node.attrs,
            review_status=node.review_status,
            citations=[],
        )


@router.post("/projects/{project_id}/graph/{version_id}/approve")
def approve_graph(
    version_id: str, ctx: ProjectContext = Depends(require("graph.approve"))
) -> VersionOut:
    """Gate 1. Every node must be reviewed; the pipeline must be waiting at graph review."""
    actor = engine.Actor("user", ids.encode("usr", ctx.principal.user_id), ctx.role)
    try:
        with ctx.session() as s:
            gv = _version(s, version_id)
            if gv.status != "draft":
                raise conflict("Only a draft graph version can be approved")
            pending = s.scalars(
                select(Node.id)
                .where(Node.graph_version_id == gv.id, Node.review_status == "pending")
                .order_by(Node.id)
            ).all()
            if pending:
                raise ApiError(
                    409,
                    "GATE_NOT_APPROVED",
                    f"{len(pending)} node(s) still need review",
                    {"gate": 1, "pending_node_ids": [ids.encode("nod", n) for n in pending[:200]]},
                )
            for old in s.scalars(select(GraphVersion).where(GraphVersion.status == "approved")):
                old.status = "superseded"
            gv.status = "approved"
            gv.approved_by = ctx.principal.user_id
            gv.approved_at = datetime.now(UTC)
            s.flush()
            audit.record(
                s,
                project_id=ctx.project_id,
                actor=actor.id,
                action="gate1.approved",
                entity=ids.encode("gv", gv.id),
                payload={"number": gv.number},
            )
            engine.transition(
                s, ctx.project_id, "graph_approved", actor, payload={"graph_version": gv.number}
            )
            return _version_out(s, gv)
    except TransitionError as exc:
        raise ApiError(
            409, "STATE_CONFLICT", str(exc), {"stage": exc.stage, "status": exc.status}
        ) from None
    except GuardError as exc:  # pragma: no cover - gate 1 data and role are checked above
        raise ApiError(exc.status, exc.code, exc.message, exc.details) from None


class BriefOut(BaseModel):
    graph_version: int
    markdown: str


@router.get("/projects/{project_id}/brief")
def get_brief(ctx: ProjectContext = Depends(require("project.view"))) -> BriefOut:
    """Markdown brief of the approved graph (rejected nodes left out, every rule quoted)."""
    with ctx.session() as s:
        gv = s.scalar(select(GraphVersion).where(GraphVersion.status == "approved"))
        if gv is None:
            raise not_found("Approved graph")
        nodes = s.scalars(
            select(Node).where(Node.graph_version_id == gv.id, Node.review_status != "rejected")
        ).all()
        node_ids = [n.id for n in nodes]
        edges = s.scalars(
            select(Edge).where(Edge.from_node_id.in_(node_ids), Edge.to_node_id.in_(node_ids))
        ).all()
        quotes: dict[str, list[str]] = {}
        for node_id, quote in s.execute(
            select(NodeCitation.node_id, NodeCitation.quote)
            .where(NodeCitation.node_id.in_(node_ids))
            .order_by(NodeCitation.start_offset)
        ).all():
            quotes.setdefault(str(node_id), []).append(quote)
        project = s.get_one(Project, ctx.project_id)
        markdown = build_brief(
            project.name,
            [NodeView(str(n.id), n.type, n.label, dict(n.attrs)) for n in nodes],
            [EdgeView(str(e.from_node_id), str(e.to_node_id), e.kind) for e in edges],
            quotes,
        )
        return BriefOut(graph_version=gv.number, markdown=markdown)
