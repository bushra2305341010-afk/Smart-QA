from pathlib import Path
from typing import Any

import pytest

from apps.runner.detectors import PageSnapshot, detect, env_down
from apps.runner.evidence import Collector
from apps.runner.policy_hook import RequestGuard, element_action, policy_context
from apps.runner.secrets import EnvSecrets, MissingSecretError, Resolver

ENV = {"kind": "local", "base_url": "http://127.0.0.1:8765", "allowed_hosts": [],
       "safe_actions": {}}  # fmt: skip


@pytest.mark.parametrize(
    ("snap", "signal"),
    [
        (PageSnapshot("http://x/", frame_urls=["https://www.google.com/recaptcha/api2/anchor"]),
         "captcha"),
        (PageSnapshot("http://x/", text="Please confirm I'm not a robot"), "captcha"),
        (PageSnapshot("http://x/", title="Attention Required!", status=403), "bot_wall"),
        (PageSnapshot("http://x/", text="Enter the 6-digit code"), "mfa"),
        (PageSnapshot("http://x/", has_otp_input=True), "mfa"),
        (PageSnapshot("http://x/login", text="Log in", has_password_input=True), "login_wall"),
        (PageSnapshot("http://x/", title="Access denied", status=200), None),
        (PageSnapshot("http://x/settings", text="Log in", has_password_input=True), None),
        (PageSnapshot("http://x/", text="Welcome"), None),
    ],
)  # fmt: skip
def test_detect(snap: PageSnapshot, signal: str | None) -> None:
    found = detect(snap)
    assert (found.signal if found else None) == signal


def test_login_expected_is_not_a_wall() -> None:
    snap = PageSnapshot("http://x/login", text="Sign in", has_password_input=True)
    assert detect(snap, expect_login=True) is None


def test_env_down() -> None:
    assert env_down(None, "net::ERR_CONNECTION_REFUSED at http://x").signal == "env_down"  # type: ignore[union-attr]
    assert env_down(503, None).signal == "env_down"  # type: ignore[union-attr]
    assert env_down(200, None) is None and env_down(None, "net::ERR_ABORTED") is None


def test_secrets_resolve_and_mask() -> None:
    r = Resolver(EnvSecrets({"SAQ_SECRET_PASSWORD": "hunter2-long"}), EnvSecrets({}))
    assert r.resolve("pw={{secret:password}}") == "pw=hunter2-long"
    assert r.mask("typed hunter2-long here") == "typed [secret] here"
    with pytest.raises(MissingSecretError):
        r.resolve("{{secret:missing}}")
    assert EnvSecrets().get("definitely_not_set_123") is None


def test_collector_dedupes_and_refs() -> None:
    c = Collector()
    sha = c.add("screenshot", b"png", 1)
    assert c.add("screenshot", b"png", 1) == sha and len(c.items) == 1
    c.add("console", b"log")
    assert c.refs()[1] == {"kind": "console", "sha256": c.items[1].sha256, "size": 3,
                           "step_n": None}  # fmt: skip


def test_element_action() -> None:
    a = element_action("click", {"text": "Delete", "aria": None, "title": "t",
                                 "href": "javascript:void(0)", "card": True}, "Delete")  # fmt: skip
    assert a.url is None and a.text == "Delete" and a.in_payment_form and a.title == "t"
    b = element_action("click", {"href": "https://evil.test/"}, "Go")
    assert b.url == "https://evil.test/"
    assert element_action("fill", {"href": "https://x/"}, "Email", "v").url is None
    assert element_action("press", None, None).text is None


class FakeRequest:
    def __init__(self, url: str, method: str = "GET", nav: bool = False) -> None:
        self.url, self.method, self._nav = url, method, nav

    def is_navigation_request(self) -> bool:
        return self._nav


class FakeRoute:
    def __init__(self, req: FakeRequest) -> None:
        self.request, self.calls = req, []

    def continue_(self) -> None:
        self.calls.append("continue")

    def abort(self, code: str) -> None:
        self.calls.append(code)


def test_request_guard() -> None:
    guard = RequestGuard(policy_context(ENV, Path("/nonexistent")))
    routes = [FakeRoute(FakeRequest(u, m, n)) for u, m, n in [
        ("data:image/png;base64,xx", "GET", False),
        ("http://127.0.0.1:8765/app.js", "GET", False),
        ("https://fonts.example/x.css", "GET", False),  # silently aborted
    ]]  # fmt: skip
    for r in routes:
        guard.handle(r)
    assert [r.calls for r in routes] == [["continue"], ["continue"], ["blockedbyclient"]]
    assert guard.blocked is None and guard.aborted == 1
    post = FakeRoute(FakeRequest("http://127.0.0.1:8765/api/students/1", "DELETE"))
    guard.handle(post)
    assert guard.blocked is not None and guard.blocked.category == "delete"
    nav = RequestGuard(policy_context(ENV))
    nav.handle(FakeRoute(FakeRequest("https://evil.test/", "GET", True)))
    assert nav.blocked is not None and nav.blocked.category == "off_domain"
    first: Any = nav.blocked
    nav.handle(FakeRoute(FakeRequest("http://127.0.0.1:8765/x/delete", "POST")))
    assert nav.blocked is first  # the first block is the reported one
