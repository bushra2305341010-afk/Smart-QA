"""The runner against real Chromium and a local site: evidence, policy, detectors, errors."""

from __future__ import annotations

from http.server import ThreadingHTTPServer
from typing import Any

import pytest

from apps.runner.evidence import Collector
from apps.runner.executor import CaseRunner, absolute
from apps.runner.main import Browser, run_job
from apps.runner.policy_hook import policy_context
from apps.runner.secrets import EnvSecrets, Resolver
from packages.contracts.run import AttemptResult, CompiledAction, CompiledCase, Locator

pytestmark = pytest.mark.browser


def env(site: ThreadingHTTPServer, **safe: Any) -> dict[str, Any]:
    host, port = site.server_address[:2]
    return {"kind": "local", "base_url": f"http://{host}:{port}", "allowed_hosts": [],
            "safe_actions": safe}  # fmt: skip


def act(
    kind: str,
    n: int,
    by: str | None = None,
    value: str | None = None,
    *,
    role: str | None = None,
    v: str | None = None,
    expected: bool = False,
) -> CompiledAction:
    loc = Locator(by=by, value=value, role=role) if by and value else None  # type: ignore[arg-type]
    return CompiledAction(kind=kind, step_n=n, locator=loc, value=v, expected=expected)  # type: ignore[arg-type]


def run(chromium: Any, site: ThreadingHTTPServer, actions: list[CompiledAction],
        secrets: dict[str, str] | None = None, unparsed: list[int] | None = None,
        timeout_ms: int = 1500, **safe: Any) -> tuple[AttemptResult, Collector]:  # fmt: skip
    case = CompiledCase(case_id="c", code="TC-1", actions=actions, unparsed_steps=unparsed or [])
    e = env(site, **safe)
    context = chromium.new_context()
    page = context.new_page()
    collector = Collector()
    runner = CaseRunner(page, case, e, policy_context(e), Resolver(EnvSecrets(secrets or {})),
                        collector, timeout_ms=timeout_ms)  # fmt: skip
    runner.install()
    try:
        return runner.run(1), collector
    finally:
        context.close()


FORM = [
    act("goto", 1, v="/form"),
    act("fill", 2, "label", "Email", v="a@example.com"),
    act("fill", 3, "label", "Password", v="{{secret:password}}"),
    act("select", 4, "label", "Country", v="IN"),
    act("check", 5, "label", "I agree"),
    act("click", 6, "role", "Save", role="button"),
]


def test_pass_with_evidence_per_step(chromium: Any, site: ThreadingHTTPServer) -> None:
    actions = [*FORM, act("expect_text", 7, "text", "Saved a@example.com 12 IN true",
                          expected=True), act("expect_url", 7, v="/form"),
               act("expect_hidden", 7, "text", "Nope")]  # fmt: skip
    result, ev = run(chromium, site, actions, {"SAQ_SECRET_PASSWORD": "s3cret-value"})
    assert result.status == "passed", result
    assert result.expectations_checked == 3 and result.console_errors == 1
    shots = [i.step_n for i in ev.items if i.kind == "screenshot"]
    assert shots == [1, 2, 3, 4, 5, 6, 7]
    console = next(i for i in ev.items if i.kind == "console")
    assert b"boom" in console.data and result.http_status == 200


def test_assertion_failure_is_product_fail(chromium: Any, site: ThreadingHTTPServer) -> None:
    actions = [*FORM, act("expect_text", 7, "text", "Order placed", expected=True)]
    result, ev = run(chromium, site, actions, {"SAQ_SECRET_PASSWORD": "s3cret-value"})
    assert result.status == "failed" and result.failure is not None
    assert result.failure.kind == "assertion" and result.failure.expected == "Order placed"
    assert result.failure.actual is not None and "s3cret-value" not in result.failure.actual
    assert [i.step_n for i in ev.items if i.kind == "screenshot"][-1] == 7


def test_missing_element_is_our_fault(chromium: Any, site: ThreadingHTTPServer) -> None:
    result, _ = run(chromium, site, [act("goto", 1, v="/form"),
                                     act("click", 2, "role", "Nope", role="button")])  # fmt: skip
    assert result.status == "failed" and result.failure and result.failure.kind == "locator"


def test_missing_secret_and_unparsed_are_errors(chromium: Any, site: ThreadingHTTPServer) -> None:
    result, _ = run(chromium, site, FORM[:3])
    assert result.status == "error" and "password" in result.failure.message  # type: ignore[union-attr]
    result, ev = run(chromium, site, FORM[:1], unparsed=[2, 3])
    assert result.status == "error" and "2, 3" in result.failure.message  # type: ignore[union-attr]
    assert ev.items == []


def test_no_locator_is_script_error(chromium: Any, site: ThreadingHTTPServer) -> None:
    result, _ = run(chromium, site, [act("goto", 1, v="/form"), act("click", 2)])
    assert result.status == "error"


@pytest.mark.parametrize(
    ("actions", "reason"),
    [
        ([act("goto", 1, v="/danger"), act("click", 2, "role", "Delete student", role="button")],
         "Destructive"),
        ([act("goto", 1, v="/danger"), act("click", 2, "role", "Archive", role="button"),
          act("expect_text", 3, "text", "Student list")], "Destructive"),
        ([act("goto", 1, v="https://evil.example/")], "allowed hosts"),
        ([act("goto", 1, v="/"), act("click", 2, "role", "Elsewhere", role="link")],
         "allowed hosts"),
    ],
)  # fmt: skip
def test_policy_blocks_before_acting(
    chromium: Any, site: ThreadingHTTPServer, actions: list[CompiledAction], reason: str
) -> None:
    before = len(site.hits)  # type: ignore[attr-defined]
    result, _ = run(chromium, site, actions)
    assert result.blocked == "policy" and reason in (result.blocked_reason or "")
    assert [h for h in site.hits[before:] if h[0] == "DELETE"] == []  # type: ignore[attr-defined]
    assert ("POST", "/api/students/1/delete") not in site.hits[before:]  # type: ignore[attr-defined]


def test_env_can_allow_delete(chromium: Any, site: ThreadingHTTPServer) -> None:
    actions = [act("goto", 1, v="/danger"), act("click", 2, "role", "Delete student", role="button"),
               act("expect_text", 3, "text", "Student list", expected=True)]  # fmt: skip
    result, _ = run(chromium, site, actions, allow=["delete"])
    assert result.status == "passed"


@pytest.mark.parametrize(
    ("path", "signal"), [("/captcha", "captcha"), ("/login", "login_wall"), ("/down", "env_down")]
)
def test_blocked_detectors(
    chromium: Any, site: ThreadingHTTPServer, path: str, signal: str
) -> None:
    result, _ = run(chromium, site, [act("goto", 1, v=path), act("expect_text", 2, "text", "x")])
    assert result.blocked == signal and result.status == "failed"


def test_unreachable_env(chromium: Any) -> None:
    import socket

    with socket.socket() as sock:  # a free port nobody listens on
        sock.bind(("127.0.0.1", 0))
        free = sock.getsockname()[1]

    class Dead:
        server_address = ("127.0.0.1", free)

    result, _ = run(chromium, Dead(), [act("goto", 1, v="/")])  # type: ignore[arg-type]
    assert result.blocked == "env_down"


def test_timeout_is_timed_out(chromium: Any, site: ThreadingHTTPServer) -> None:
    result, _ = run(
        chromium,
        site,
        [act("goto", 1, v="/flaky"), act("expect_text", 2, "text", "Never")],
        timeout_ms=200,
    )
    assert result.status == "failed" and result.failure and result.failure.kind == "assertion"


def test_run_job_with_fresh_context_and_trace(chromium: Any, site: ThreadingHTTPServer) -> None:
    case = CompiledCase(
        case_id="c",
        code="TC-2",
        actions=[act("goto", 1, v="/flaky"), act("expect_text", 2, "text", "Ready", expected=True)],
    )
    job = {"case": case.model_dump(mode="json"), "env": env(site), "attempt": 2}
    result, ev = run_job(job, Browser(chromium.new_context, "chromium"), [EnvSecrets({})])
    assert result.status == "passed" and result.attempt == 2
    assert {i.kind for i in ev.items} >= {"screenshot", "trace"}
    assert result.evidence_count == len(ev.items)


def test_absolute() -> None:
    assert absolute("http://a:1/", "/x") == "http://a:1/x"
    assert absolute("http://a:1", "https://b/") == "https://b/"
    assert absolute("http://a:1", None) == "http://a:1/"


def test_other_locators_press_and_server_errors(chromium: Any, site: ThreadingHTTPServer) -> None:
    actions = [
        act("goto", 1, v="/misc"),
        act("fill", 2, "placeholder", "Search", v="shoes"),
        act("click", 3, "css", "#q"),
        act("press", 3, v="End"),
        act("click", 4, "test_id", "go"),
        act("expect_text", 5, "text", "Done shoes", expected=True),
    ]
    result, _ = run(chromium, site, actions)
    assert result.status == "passed", result
    assert result.network_errors >= 1  # the 500 from /boom is counted as noise


def test_navigation_timeout(chromium: Any, site: ThreadingHTTPServer) -> None:
    result, _ = run(chromium, site, [act("goto", 1, v="/slow")], timeout_ms=200)
    assert result.status == "timed_out" and result.failure and result.failure.kind == "timeout"


def test_classify_and_locate() -> None:
    from playwright.sync_api import Error

    from apps.runner.executor import classify

    assert classify(Error("net::ERR_FAILED at x"), 2).kind == "network"
    assert classify(ValueError(""), 1).message == "ValueError"
