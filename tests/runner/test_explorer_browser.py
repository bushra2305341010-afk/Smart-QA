"""Explorer: read-only crawl, policy-checked, never clicks (M09c)."""

from __future__ import annotations

from http.server import ThreadingHTTPServer
from typing import Any

import pytest

from apps.runner.explorer import explore
from apps.runner.policy_hook import policy_context

pytestmark = pytest.mark.browser


def ctx(site: ThreadingHTTPServer) -> Any:
    host, port = site.server_address[:2]
    return policy_context({"kind": "local", "base_url": f"http://{host}:{port}"})


def test_explore_collects_screens_and_respects_policy(
    chromium: Any, site: ThreadingHTTPServer
) -> None:
    before = list(site.hits)  # type: ignore[attr-defined]
    page = chromium.new_context().new_page()
    result = explore(page, ctx(site))
    page.context.close()
    screens = {sc.path: sc for sc in result.screens}
    assert set(screens) == {"/", "/form", "/danger"}
    form = screens["/form"]
    by_label = {f.label: f for f in form.fields}
    assert by_label["Age"].required and (by_label["Age"].min, by_label["Age"].max) == ("5", "18")
    assert by_label["Country"].options == ["BD", "IN"] and by_label["Note"].max_length == 200
    assert "csrf" not in by_label and by_label["Country"].input_type == "select"
    assert "Delete student" in screens["/danger"].actions  # recorded, never clicked
    assert site.hits == before  # type: ignore[attr-defined]  # no POST/DELETE was sent
    reasons = " ".join(result.blocked)
    assert "evil.example" in reasons and "/students/4/delete" in reasons
    assert "CAPTCHA" in reasons and "HTTP 404" in reasons and "mailto" not in reasons
    assert not result.budget_exhausted and result.steps == 5


def test_budget_and_navigation_errors(chromium: Any, site: ThreadingHTTPServer) -> None:
    page = chromium.new_context().new_page()
    result = explore(page, ctx(site), budget=1)
    assert result.budget_exhausted and [s.path for s in result.screens] == ["/"]
    result = explore(page, ctx(site), "/slow", timeout_ms=200)
    assert result.screens == [] and "Timeout" in result.blocked[0]
    page.context.close()
