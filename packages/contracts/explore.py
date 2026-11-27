"""Explorer observations (F04, M09c): what the running UI shows, not what documents say.

Observed Screens and Fields become *pending* graph nodes for Gate 1. They carry no quote, so they
can never justify an expected result (only cited Rules/Requirements can, pillar P1).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ObservedField(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: str = Field(min_length=1, max_length=200)
    input_type: str = Field(default="text", max_length=40)
    required: bool = False
    min: str | None = Field(default=None, max_length=40)
    max: str | None = Field(default=None, max_length=40)
    max_length: int | None = None
    options: list[str] = Field(default_factory=list, max_length=50)


class ObservedScreen(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str = Field(min_length=1, max_length=500)
    title: str = Field(default="", max_length=200)
    headings: list[str] = Field(default_factory=list, max_length=20)
    fields: list[ObservedField] = Field(default_factory=list, max_length=100)
    actions: list[str] = Field(default_factory=list, max_length=100)  # button names, not clicked
    links: list[str] = Field(default_factory=list, max_length=200)  # in-scope paths


class Exploration(BaseModel):
    base_url: str
    screens: list[ObservedScreen] = Field(default_factory=list, max_length=500)
    steps: int = 0
    blocked: list[str] = Field(default_factory=list, max_length=500)  # "url: reason"
    budget_exhausted: bool = False
