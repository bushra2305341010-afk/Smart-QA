"""Run one compiled case in one browser page (F15, F21). Plan lock: only `CompiledCase` actions
run; nothing the page says can add a step.

Per action: Blocked detectors → policy check on the live element → act. A screenshot is taken
after every step, in `finally`, so a failing step still has evidence. Errors are classified for
the Judge: our locator/script (Test Error), assertion (product), timeout/network (maybe noise),
blocked (CAPTCHA, MFA, policy, environment down).
"""

from __future__ import annotations

import contextlib
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect

from apps.runner.detectors import Detection, PageSnapshot, detect, env_down
from apps.runner.evidence import Collector
from apps.runner.policy_hook import (
    ELEMENT_FACTS_JS,
    FOCUSED_FACTS_JS,
    RequestGuard,
    element_action,
)
from apps.runner.secrets import MissingSecretError, Resolver
from packages.contracts.run import (
    AttemptResult,
    AttemptStatus,
    BlockedSignal,
    CompiledAction,
    CompiledCase,
    Failure,
    FailureKind,
    Locator,
)
from packages.policy.actions import Action, PolicyContext, check

SNAPSHOT_JS = """() => ({
  title: document.title,
  text: (document.body ? document.body.innerText : '').slice(0, 5000),
  otp: !!document.querySelector('input[autocomplete="one-time-code"]'),
  password: !!document.querySelector('input[type="password"]'),
})"""


class Stop(Exception):  # noqa: N818 - control flow, not an error type
    def __init__(self, failure: Failure | None = None, blocked: Detection | None = None) -> None:
        super().__init__(failure.message if failure else blocked.reason if blocked else "")
        self.failure, self.blocked = failure, blocked


@dataclass
class Counters:
    console_errors: int = 0
    network_errors: int = 0
    last_status: int | None = None
    console_lines: list[str] = field(default_factory=list)


def locate(page: Any, loc: Locator) -> Any:
    match loc.by:
        case "role":
            return page.get_by_role(loc.role or "button", name=loc.value)
        case "label":
            return page.get_by_label(loc.value)
        case "text":
            return page.get_by_text(loc.value)
        case "placeholder":
            return page.get_by_placeholder(loc.value)
        case "test_id":
            return page.get_by_test_id(loc.value)
        case _:
            return page.locator(loc.value)


def absolute(base_url: str, value: str | None) -> str:
    target = value or "/"
    return (
        target
        if re.match(r"^[a-z]+:", target, re.I)
        else base_url.rstrip("/") + "/" + target.lstrip("/")
    )


def classify(exc: Exception, step_n: int) -> Failure:
    text = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
    kind: FailureKind = "script"
    if isinstance(exc, PlaywrightTimeout):
        kind = "timeout"
    elif isinstance(exc, PlaywrightError) and "net::" in text:
        kind = "network"
    return Failure(kind=kind, message=text[:1000], step_n=step_n)


class CaseRunner:
    def __init__(
        self,
        page: Any,
        case: CompiledCase,
        env: dict[str, Any],
        policy: PolicyContext,
        resolver: Resolver,
        collector: Collector,
        *,
        timeout_ms: int = 10_000,
        expect_login: bool = False,
    ) -> None:
        self.page, self.case, self.env, self.policy = page, case, env, policy
        self.resolver, self.collector = resolver, collector
        self.timeout_ms, self.expect_login = timeout_ms, expect_login
        self.guard = RequestGuard(policy)
        self.counters = Counters()
        self.checked = 0

    # ----- wiring -----

    def install(self) -> None:
        self.page.context.route("**/*", self.guard.handle)
        self.page.on("console", self._on_console)
        self.page.on("requestfailed", self._on_failed)
        self.page.on("response", self._on_response)

    def _on_console(self, msg: Any) -> None:
        if msg.type == "error":
            self.counters.console_errors += 1
        self.counters.console_lines.append(f"[{msg.type}] {self.resolver.mask(msg.text)}"[:2000])

    def _on_failed(self, req: Any) -> None:
        self.counters.network_errors += 1

    def _on_response(self, resp: Any) -> None:
        if resp.status >= 500 or resp.status == 429:
            self.counters.network_errors += 1
        if resp.request.is_navigation_request():
            self.counters.last_status = resp.status

    # ----- checks -----

    def _snapshot(self) -> PageSnapshot:
        facts = self.page.evaluate(SNAPSHOT_JS)
        return PageSnapshot(
            url=self.page.url, title=facts["title"], text=facts["text"],
            frame_urls=[f.url for f in self.page.frames], has_otp_input=facts["otp"],
            has_password_input=facts["password"], status=self.counters.last_status,
        )  # fmt: skip

    def _detect(self) -> None:
        if self.page.url in ("", "about:blank"):
            return
        found = detect(self._snapshot(), expect_login=self.expect_login)
        if found:
            raise Stop(blocked=found)

    def _allow(self, action: Action) -> None:
        decision = check(action, self.policy)
        if not decision.allowed:
            raise Stop(blocked=Detection("policy", decision.reason))

    def _guard_tripped(self) -> None:
        if self.guard.blocked is not None:
            raise Stop(blocked=Detection("policy", self.guard.blocked.reason))

    # ----- actions -----

    def _element(self, a: CompiledAction) -> Any:
        if a.locator is None:
            raise Stop(Failure(kind="script", message="Action has no locator", step_n=a.step_n))
        target = locate(self.page, a.locator).first
        try:
            target.wait_for(state="visible", timeout=self.timeout_ms)
        except PlaywrightTimeout:
            what = f"Element not found: {a.locator.by}={a.locator.value!r}"
            raise Stop(Failure(kind="locator", step_n=a.step_n, message=what)) from None
        return target

    def _value(self, a: CompiledAction) -> str:
        try:
            return self.resolver.resolve(a.value or "")
        except MissingSecretError as exc:
            what = f"Secret '{exc.args[0]}' is not set on this runner"
            raise Stop(Failure(kind="script", step_n=a.step_n, message=what)) from None

    def _assert(self, a: CompiledAction, check_fn: Callable[[], None]) -> None:
        self.checked += 1
        try:
            check_fn()
        except AssertionError:
            body = self.page.evaluate(SNAPSHOT_JS)["text"]
            wanted = a.value or (a.locator.value if a.locator else None)
            failure = Failure(
                kind="assertion",
                step_n=a.step_n,
                message=f"Expected {a.kind.removeprefix('expect_')} {wanted!r} not met",
                expected=wanted,
                actual=self.resolver.mask(body[:500]),
            )
            raise Stop(failure) from None

    def do(self, a: CompiledAction) -> None:
        t = self.timeout_ms
        if a.kind == "goto":
            url = absolute(self.policy.base_url, a.value)
            self._allow(Action(kind="navigate", url=url))
            try:
                resp = self.page.goto(url, wait_until="domcontentloaded", timeout=t * 2)
            except PlaywrightError as exc:
                self._guard_tripped()
                down = env_down(None, str(exc))
                if down:
                    raise Stop(blocked=down) from None
                raise
            down = env_down(resp.status if resp else None, None)
            if down:
                raise Stop(blocked=down)
            self._guard_tripped()
            self._detect()
            return
        self._detect()
        if a.kind in ("click", "fill", "select", "check"):
            target = self._element(a)
            facts = target.evaluate(ELEMENT_FACTS_JS)
            name = a.locator.value if a.locator else None
            value = self._value(a) if a.kind in ("fill", "select") else None
            self._allow(element_action(a.kind, facts, name, value))
            if a.kind == "click":
                target.click(timeout=t)
            elif a.kind == "fill":
                target.fill(value or "", timeout=t)
            elif a.kind == "select":
                target.select_option(value or "", timeout=t)
            else:
                target.check(timeout=t)
        elif a.kind == "press":
            facts = self.page.evaluate(FOCUSED_FACTS_JS)
            self._allow(element_action("press", facts, None))
            self.page.keyboard.press(a.value or "Enter")
        elif a.kind == "expect_url":
            pattern = re.compile(re.escape(a.value or ""))
            self._assert(a, lambda: expect(self.page).to_have_url(pattern, timeout=t))
        else:  # expect_text / expect_visible / expect_hidden
            if a.locator is None:
                raise Stop(Failure(kind="script", message="Check has no locator", step_n=a.step_n))
            target = locate(self.page, a.locator).first
            if a.kind == "expect_hidden":
                self._assert(a, lambda: expect(target).to_be_hidden(timeout=t))
            else:
                self._assert(a, lambda: expect(target).to_be_visible(timeout=t))
        with contextlib.suppress(PlaywrightTimeout):
            self.page.wait_for_load_state("domcontentloaded", timeout=t)
        self._guard_tripped()

    def _shot(self, step_n: int) -> None:
        with contextlib.suppress(PlaywrightError):  # page closed/crashed: failure is reported
            self.collector.add("screenshot", self.page.screenshot(full_page=False), step_n)

    def run(self, attempt: int) -> AttemptResult:
        start = time.monotonic()
        failure: Failure | None = None
        blocked: Detection | None = None
        status: AttemptStatus = "passed"
        if self.case.unparsed_steps:
            steps = ", ".join(map(str, self.case.unparsed_steps))
            failure = Failure(kind="script", message=f"Step(s) {steps} were not compiled")
            status = "error"
        else:
            step = 0
            try:
                for a in self.case.actions:
                    if a.step_n != step and step:
                        self._shot(step)
                    step = a.step_n
                    try:
                        self.do(a)
                    except Stop:
                        raise
                    except PlaywrightTimeout as exc:
                        raise Stop(classify(exc, a.step_n)) from None
                    except PlaywrightError as exc:
                        raise Stop(classify(exc, a.step_n)) from None
            except Stop as stop:
                failure, blocked = stop.failure, stop.blocked
                status = "failed"
                if failure and failure.kind == "script":
                    status = "error"
                elif failure and failure.kind == "timeout":
                    status = "timed_out"
            finally:
                if step:
                    self._shot(step)
        if self.counters.console_lines:
            self.collector.add("console", "\n".join(self.counters.console_lines).encode())
        signal: BlockedSignal | None = blocked.signal if blocked else None
        return AttemptResult(
            attempt=attempt, status=status, duration_ms=int((time.monotonic() - start) * 1000),
            failure=(failure.model_copy(update={"message": self.resolver.mask(failure.message)})
                     if failure else None),
            blocked=signal, blocked_reason=blocked.reason if blocked else None,
            http_status=self.counters.last_status, network_errors=self.counters.network_errors,
            console_errors=self.counters.console_errors,
            evidence_count=len(self.collector.items), expectations_checked=self.checked,
        )  # fmt: skip
