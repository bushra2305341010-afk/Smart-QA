"""Citation and chunk contracts (docs/04-design.md §4, ADR-005).

Shared by ingest, graph, designer, judge and reporter. Changing a field is a contract change:
bump consumers and run their tests (docs/workflows/00-bug-triage-map.md §2).
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

CitationStatus = Literal["verified", "unverified"]


class Location(BaseModel):
    """Human-readable place of a quote in the original file."""

    model_config = ConfigDict(frozen=True)

    file: str
    page: int | None = Field(default=None, ge=1)
    line: int | None = Field(default=None, ge=1)


class Citation(BaseModel):
    """A quote that supports a rule or an expected result.

    `status` is set only by `packages.citations.verify`, never by a model.
    Offsets index into the source's normalised text.
    """

    model_config = ConfigDict(frozen=True)

    source_id: str = Field(min_length=1)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    quote: str
    location: Location | None = None
    status: CitationStatus = "unverified"

    @model_validator(mode="after")
    def _end_not_before_start(self) -> Self:
        if self.end_offset < self.start_offset:
            raise ValueError("end_offset must be >= start_offset")
        return self


class Chunk(BaseModel):
    """A citable slice of a source's normalised text."""

    model_config = ConfigDict(frozen=True)

    source_id: str = Field(min_length=1)
    text: str
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    page: int = Field(ge=1)
    line: int = Field(ge=1)
