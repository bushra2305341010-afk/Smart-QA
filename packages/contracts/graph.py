"""Product Understanding Graph contracts (docs/workflows/02, docs/07 node/edge/node_citation).

`Extraction` is what the Analyst model must return. Every node carries the exact sentence it is
based on (`quote`) and which numbered source it came from; code verifies the quote afterwards
(pillar P1), the model's word is never enough.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

NodeType = Literal[
    "Role",
    "Journey",
    "Step",
    "Screen",
    "Field",
    "Rule",
    "Endpoint",
    "Requirement",
    "Conflict",
    "Question",
]
EdgeKind = Literal[
    "performs",  # Role → Journey
    "has_step",  # Journey → Step
    "on_screen",  # Step → Screen
    "has_field",  # Screen → Field
    "governs",  # Rule → Field / Step / Endpoint
    "calls",  # Step / Screen → Endpoint
    "satisfies",  # Journey / Rule → Requirement
    "conflicts_with",  # Conflict → Rule
    "asks_about",  # Question → any
]
# Types the model may extract; Conflict and Question nodes are created by code.
ExtractableType = Literal[
    "Role", "Journey", "Step", "Screen", "Field", "Rule", "Endpoint", "Requirement"
]  # fmt: skip
CITED_TYPES = frozenset({"Rule", "Requirement"})


class Attr(BaseModel):
    """A name/value fact about a node. Rules use `subject` and `value` for conflict checks."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=60)
    value: str = Field(max_length=300)


class ExtractedNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str = Field(min_length=1, max_length=60, description="Local id, unique in this output")
    type: ExtractableType
    label: str = Field(min_length=1, max_length=200)
    attrs: list[Attr] = Field(default_factory=list, max_length=20)
    source: str = Field(description="Source label, e.g. S1")
    quote: str = Field(description="Exact sentence copied from that source")


class ExtractedEdge(BaseModel):
    model_config = ConfigDict(frozen=True)

    from_key: str
    to_key: str
    kind: EdgeKind


class Extraction(BaseModel):
    nodes: list[ExtractedNode] = Field(default_factory=list, max_length=400)
    edges: list[ExtractedEdge] = Field(default_factory=list, max_length=800)
