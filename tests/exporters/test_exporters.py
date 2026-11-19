"""Workbook (US-09), bug template and GitHub adapter (US-08)."""

import io
import json

import httpx
import pytest
from openpyxl import load_workbook

from packages.exporters.bug import BugFacts, draft_bug
from packages.exporters.excel import HEADERS, build_workbook, safe_text
from packages.exporters.model import (
    BugRow,
    CaseRow,
    CoverageRow,
    EvidenceRow,
    ResultRow,
    RunExport,
)
from packages.exporters.trackers.github import GitHubTracker, TrackerError

CASE = CaseRow(
    code="TC-SIG-001", journey="Sign up", segment="Sign up", role="Customer",
    technique="boundary_value", priority="Must", preconditions=["On page"],
    steps=["Type", "Submit"],
    data={"email": "real.person@gmail.com"}, expected="=HYPERLINK(\"http://x\")", source="prd.md",
    quote="Password must be 8 to 64 characters.", citation_status="verified",
    requirement_id="REQ-1", review_status="approved",
)  # fmt: skip


def _export(**kw) -> RunExport:  # type: ignore[no-untyped-def]
    return RunExport(project="Shop", run="run_1", **kw)


def test_workbook_sheets_safety_and_colours() -> None:
    data = _export(
        cases=[CASE, CaseRow(**{**CASE.__dict__, "code": "TC-SIG-002", "requirement_id": None})],
        results=[
            ResultRow("run_1", "TC-SIG-001", "fail", 0.9, "+cmd|' /C calc'!A0", 1200, "chromium",
                      ["screenshot ab12"], 1, "J3"),
            ResultRow("run_1", "TC-SIG-001", "pass", None, "ok", None, None, [], 2, None),
            ResultRow("run_1", "TC-OTHER", "mystery", True, "x", 1, "b", [], 1, None),
        ],
        bugs=[BugRow("TC-SIG-001:1", "Sign up 500", "high", ["a"], "e", "q", "500", ["sha"],
                     "staging", None, "draft")],
        coverage=[CoverageRow("Sign up", 4, 3, 3, {"pass": 2, "fail": 1})],
        evidence=[EvidenceRow("ev_1", "screenshot", "ab" * 32, "s3://e/ab", "2026-11-20")],
    )  # fmt: skip
    wb = load_workbook(io.BytesIO(build_workbook(data)))
    assert wb.sheetnames == list(HEADERS)
    cases = wb["Test Cases"]
    assert [c.value for c in cases[1]] == HEADERS["Test Cases"]
    assert cases.freeze_panes == "A2" and cases.auto_filter.ref == "A1:O3"
    assert cases["J2"].value.startswith("'=")  # formula injection neutralised
    assert "gmail.com" not in cases["I2"].value  # redacted
    assert cases["G2"].value == "1. On page" and cases["H2"].value == "1. Type\n2. Submit"
    results = wb["Run Results"]
    assert results["C2"].fill.fgColor.rgb.endswith("FEE2E2") and results["E2"].value.startswith(
        "'+"
    )
    assert results["C3"].fill.fgColor.rgb.endswith("DCFCE7")
    assert results["D4"].value == "True" and results["F3"].value is None
    trace = wb["Traceability"]
    assert [c.value for c in trace[2]] == ["REQ-1", "1. TC-SIG-001", "1. pass", 1, "covered"]
    assert [c.value for c in wb["Coverage"][2]] == ["Sign up", 4, 3, 3, 2, 1, 0, 0, 0, 0]
    assert wb["Evidence Index"]["C2"].value == "ab" * 32


def test_traceability_statuses() -> None:
    other = CaseRow(**{**CASE.__dict__, "code": "TC-X-1", "requirement_id": "REQ-2"})
    third = CaseRow(**{**CASE.__dict__, "code": "TC-X-2", "requirement_id": "REQ-3"})
    data = _export(
        cases=[other, third], results=[ResultRow("r", "TC-X-1", "fail", 1, "", 1, "", [], 1, "")]
    )
    rows = list(load_workbook(io.BytesIO(build_workbook(data)))["Traceability"].values)[1:]
    assert [(r[0], r[-1]) for r in rows] == [("REQ-2", "at risk"), ("REQ-3", "not run")]


def test_safe_text() -> None:
    assert safe_text("@SUM(1)") == "'@SUM(1)" and safe_text("plain") == "plain"


def test_bug_draft() -> None:
    facts = BugFacts(
        case_code="TC-SIG-001", case_title="64 chars ok", priority="Must", steps=["Type", "Submit"],
        data={"password": "x"}, expected="Account is created",
        quote="Password must be 8 to 64 characters.", source="prd.md p1 l3",
        actual="Server error 500 for admin@shop.example", environment="staging",
        evidence=["screenshot ab12"],
    )  # fmt: skip
    draft = draft_bug(facts)
    assert draft.severity == "high" and draft.title.startswith(
        "[TC-SIG-001] 64 chars ok: Server error"
    )
    assert "> Password must be 8 to 64 characters." in draft.body_md
    assert "1. Type\n2. Submit" in draft.body_md and "admin@shop.example" not in draft.body_md
    empty = draft_bug(
        BugFacts(**{**facts.__dict__, "steps": [], "data": {}, "evidence": [], "priority": "?"})
    )
    assert (
        empty.severity == "medium"
        and "_none captured_" in empty.body_md
        and "_none_" in empty.body_md
    )


def _tracker(handler) -> GitHubTracker:  # type: ignore[no-untyped-def]
    client = httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(handler))
    return GitHubTracker("acme/shop", "secret-token", client)


def test_github_find_and_file() -> None:
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if req.url.path == "/search/issues":
            return httpx.Response(
                200, json={"items": [{"number": 7, "title": "Sign up 500", "html_url": "u7"}]}
            )
        return httpx.Response(201, json={"number": 8, "title": "t", "html_url": "u8"})

    gh = _tracker(handler)
    [dup] = gh.find_duplicates('Sign "up" 500 on submit')
    assert dup.number == 7 and "repo:acme/shop" in seen[0].url.params["q"]
    issue = gh.file("t", "body", ["smart-qa"])
    assert issue.url == "u8" and json.loads(seen[1].content)["labels"] == ["smart-qa"]
    assert seen[1].headers["Authorization"] == "Bearer secret-token"


def test_github_errors() -> None:
    gh = _tracker(lambda req: httpx.Response(403, text="rate limited"))
    with pytest.raises(TrackerError, match="403"):
        gh.file("t", "b", [])
    with pytest.raises(ValueError, match="owner/name"):
        GitHubTracker("bad", "t")
    assert GitHubTracker("a/b", "t").repo == "a/b"
