"""Coverage-planning contracts (docs/04-design.md section 5, docs/workflows/03-coverage-planner.md).

Numbers in a plan are always computed by `packages.planning` (deterministic code). The Planner
LLM only writes human explanations on top; it never chooses counts.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Technique = Literal[
    "happy_path",
    "equivalence_class",
    "boundary_value",
    "negative_permission",
    "state_transition",
    "accessibility",
]
Priority = Literal["Must", "Should", "Could"]


class Limit(BaseModel):
    """A numeric or length limit on an input (e.g. password length 8 to 64)."""

    model_config = ConfigDict(frozen=True)

    name: str
    min: float | None = None
    max: float | None = None

    @model_validator(mode="after")
    def _at_least_one_bound(self) -> Self:
        if self.min is None and self.max is None:
            raise ValueError("a limit needs min, max or both")
        if self.min is not None and self.max is not None and self.max < self.min:
            raise ValueError("limit max must be >= min")
        return self


class InputField(BaseModel):
    """One input of a journey with its equivalence classes and limits."""

    model_config = ConfigDict(frozen=True)

    name: str
    classes: list[str] = Field(default_factory=list)
    limits: list[Limit] = Field(default_factory=list)


class JourneySpec(BaseModel):
    """What the planner needs to know about one approved journey from the graph."""

    model_config = ConfigDict(frozen=True)

    journey_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    roles: list[str] = Field(default_factory=list)
    inputs: list[InputField] = Field(default_factory=list)
    forbidden: list[str] = Field(default_factory=list)
    transitions: list[str] = Field(default_factory=list)
    screens: int = Field(default=0, ge=0)


class RiskInputs(BaseModel):
    """Signals for the transparent risk score (N12)."""

    model_config = ConfigDict(frozen=True)

    business_criticality: int = Field(ge=1, le=5)
    rule_count: int = Field(ge=0)
    input_count: int = Field(ge=0)
    change_frequency: int = Field(ge=0, le=5)
    past_defects: int = Field(default=0, ge=0)


class RiskWeights(BaseModel):
    """Per-project weights for the risk score. Defaults live in packages.planning.risk."""

    model_config = ConfigDict(frozen=True)

    business_criticality: float = Field(default=0.30, ge=0)
    rules: float = Field(default=0.20, ge=0)
    inputs: float = Field(default=0.15, ge=0)
    change_frequency: float = Field(default=0.20, ge=0)
    past_defects: float = Field(default=0.15, ge=0)

    @model_validator(mode="after")
    def _not_all_zero(self) -> Self:
        total = (
            self.business_criticality
            + self.rules
            + self.inputs
            + self.change_frequency
            + self.past_defects
        )
        if total <= 0:
            raise ValueError("at least one risk weight must be positive")
        return self


class TechniqueRow(BaseModel):
    """One line of the plan's 'why this many cases' explanation."""

    model_config = ConfigDict(frozen=True)

    technique: Technique
    count: int = Field(ge=0)
    reason: str


class SegmentPlan(BaseModel):
    """Suggested coverage for one journey. `approved_count` is set at Gate 2 by a human."""

    model_config = ConfigDict(frozen=True)

    journey_id: str
    journey_name: str
    rows: list[TechniqueRow]
    base_count: int = Field(ge=0)
    risk_score: float = Field(ge=0, le=1)
    multiplier: float
    suggested_count: int = Field(ge=1)
    priority: Priority
    approved_count: int | None = Field(default=None, ge=0)


class PriceTable(BaseModel):
    """Model prices in USD per million tokens. Load from settings; verify against the
    provider's current price page before relying on an estimate."""

    model_config = ConfigDict(frozen=True)

    model: str
    input_per_mtok_usd: float = Field(ge=0)
    output_per_mtok_usd: float = Field(ge=0)
    cache_read_per_mtok_usd: float = Field(ge=0)


class CostAssumptions(BaseModel):
    """Planning assumptions for a design run. Replace with measured values (docs/09 9.1)."""

    model_config = ConfigDict(frozen=True)

    fixed_context_tokens: int = Field(default=20_000, ge=0)
    input_tokens_per_case: int = Field(default=3_000, ge=0)
    output_tokens_per_case: int = Field(default=2_000, ge=0)
    cached_fraction: float = Field(default=0.5, ge=0, le=1)
    seconds_per_case: float = Field(default=10, ge=0)


class CostEstimate(BaseModel):
    """Estimated tokens, money and time shown before generation (N13, NFR-6)."""

    model_config = ConfigDict(frozen=True)

    model: str
    input_tokens: int
    output_tokens: int
    usd: float
    minutes: float

    def exceeds(self, budget_usd: float) -> bool:
        """True if this estimate is above the given budget cap."""
        return self.usd > budget_usd
