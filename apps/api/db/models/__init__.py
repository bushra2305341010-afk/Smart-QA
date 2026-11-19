"""All ORM models. Importing this package registers every table on `Base.metadata`."""

from apps.api.db.models.auth import ApiToken, AuthSession
from apps.api.db.models.core import (
    AppUser,
    Chunk,
    Environment,
    Identity,
    Membership,
    Project,
    Source,
)
from apps.api.db.models.graph import Edge, GraphVersion, Node, NodeCitation
from apps.api.db.models.ops import (
    AuditEvent,
    Feedback,
    Lesson,
    ModelCall,
    Outbox,
    PipelineState,
    ProjectRule,
    RegressionMemory,
    ReplayCache,
    TrainedModel,
)
from apps.api.db.models.plan import Plan, Segment, Step, TestCase
from apps.api.db.models.run import Bug, Evidence, Result, Run, Verdict

__all__ = [
    "ApiToken",
    "AppUser",
    "AuditEvent",
    "AuthSession",
    "Bug",
    "Chunk",
    "Edge",
    "Environment",
    "Evidence",
    "Feedback",
    "GraphVersion",
    "Identity",
    "Lesson",
    "Membership",
    "ModelCall",
    "Node",
    "NodeCitation",
    "Outbox",
    "PipelineState",
    "Plan",
    "Project",
    "ProjectRule",
    "RegressionMemory",
    "ReplayCache",
    "Result",
    "Run",
    "Segment",
    "Source",
    "Step",
    "TestCase",
    "TrainedModel",
    "Verdict",
]
