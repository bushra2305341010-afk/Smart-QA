"""Test-case contracts (docs/04-design.md §4, sector 04).

`CaseBatch` is what the Designer model returns. The expected result must quote the source
sentence that states it; code verifies the quote (pillar P1). A case whose quote does not
verify is kept but marked Unable to Verify — never guessed, never approvable as is.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from packages.contracts.graph import Attr
from packages.contracts.plan import Technique


class DesignedStep(BaseModel):
    model_config = ConfigDict(frozen=True)

    action: str = Field(min_length=1, max_length=500)


class DesignedCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=100)
    technique: Technique
    preconditions: list[str] = Field(default_factory=list, max_length=20)
    steps: list[DesignedStep] = Field(min_length=1, max_length=40)
    data: list[Attr] = Field(default_factory=list, max_length=30)
    expected_text: str = Field(min_length=1, max_length=1000)
    source: str = Field(description="Source label of the quote, e.g. S1")
    quote: str = Field(
        description="Exact sentence from that source that states the expected result"
    )
    requirement_id: str | None = Field(default=None, max_length=60)


class CaseBatch(BaseModel):
    cases: list[DesignedCase] = Field(default_factory=list, max_length=100)
