"""Execution contracts shared by compiler, runner, judge and reporter (sectors 05, 06).

`CompiledCase` is the plan lock: the runner executes only these typed actions, never page text
or live model output (docs/08-agent.md "Plan lock"). `AttemptResult` is what the runner reports
for one attempt of one case; the Judge turns one or two attempts into a verdict.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

VerdictValue = Literal["pass", "fail", "flaky", "blocked", "test_error", "unable_to_verify"]
ConfidenceLevel = Literal["high", "medium", "low"]
AttemptStatus = Literal["passed", "failed", "error", "skipped", "timed_out"]
# What went wrong. `assertion` = the product did not do what the quote says (a product fault);
# `locator` / `script` = our test is at fault; `timeout` / `network` = possibly noise.
FailureKind = Literal["assertion", "locator", "script", "timeout", "network", "navigation"]
BlockedSignal = Literal["captcha", "mfa", "bot_wall", "login_wall", "policy", "env_down"]

LocatorBy = Literal["role", "label", "text", "placeholder", "test_id", "css"]
ActionKind = Literal[
    "goto", "click", "fill", "select", "check", "press",
    "expect_text", "expect_url", "expect_visible", "expect_hidden",
]  # fmt: skip
EXPECTATIONS = frozenset({"expect_text", "expect_url", "expect_visible", "expect_hidden"})


class Locator(BaseModel):
    model_config = ConfigDict(frozen=True)

    by: LocatorBy
    value: str = Field(min_length=1, max_length=300)
    role: str | None = Field(default=None, max_length=40)  # for by="role": button, link, ...


class CompiledAction(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: ActionKind
    step_n: int = Field(ge=1)  # the designed step it came from
    locator: Locator | None = None
    value: str | None = Field(default=None, max_length=2000)  # url, text, {{secret:name}}
    expected: bool = False  # True for the step(s) that check the cited expected result


class CompiledCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    code: str
    actions: list[CompiledAction] = Field(min_length=1, max_length=120)
    unparsed_steps: list[int] = Field(default_factory=list)  # steps the compiler could not map


class Failure(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: FailureKind
    message: str = Field(default="", max_length=4000)
    step_n: int | None = None
    expected: str | None = None  # for assertions: what the quote says
    actual: str | None = None  # what the page showed


class AttemptResult(BaseModel):
    """One attempt of one case, as reported by the runner."""

    model_config = ConfigDict(frozen=True)

    attempt: int = Field(ge=1)
    status: AttemptStatus
    duration_ms: int = Field(default=0, ge=0)
    failure: Failure | None = None
    blocked: BlockedSignal | None = None
    blocked_reason: str | None = None
    http_status: int | None = None  # status of the last main-frame or API response
    network_errors: int = Field(default=0, ge=0)  # failed requests, 5xx, 429
    console_errors: int = Field(default=0, ge=0)
    evidence_count: int = Field(default=0, ge=0)
    expectations_checked: int = Field(default=0, ge=0)


class VerdictDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    verdict: VerdictValue
    confidence: float = Field(ge=0, le=1)
    level: ConfidenceLevel
    reason: str
    rule: str  # deciding rule id, e.g. "J3.fail_same_twice"; always stored (sector 06)
