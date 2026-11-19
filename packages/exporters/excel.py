"""Run workbook (N22, docs/14-integration.md §4): six sheets, fixed columns, no secrets.

- Every text cell is redacted (emails, tokens, card numbers…) and escaped against formula
  injection: a value starting with = + - @ or a control character is stored as text with a
  leading apostrophe, so a cell can never execute.
- Header row frozen, autofilter on, verdict cells coloured with the design tokens.
"""

from __future__ import annotations

import io
from collections.abc import Iterable
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from packages.exporters.model import RunExport
from packages.model_gateway.redact import redact

VERDICTS = ("pass", "fail", "flaky", "blocked", "test_error", "unable_to_verify")
# docs/05-frontend-ui-design.md verdict tokens: (text colour, background)
VERDICT_COLOURS = {
    "pass": ("15803D", "DCFCE7"),
    "fail": ("B91C1C", "FEE2E2"),
    "flaky": ("B45309", "FEF3C7"),
    "blocked": ("475569", "E2E8F0"),
    "test_error": ("7E22CE", "F3E8FF"),
    "unable_to_verify": ("1D4ED8", "DBEAFE"),
}
_DANGEROUS = ("=", "+", "-", "@", "\t", "\r")
HEADERS: dict[str, list[str]] = {
    "Test Cases": [
        "Case ID", "Journey", "Segment", "Role", "Technique", "Priority", "Preconditions",
        "Steps", "Test data", "Expected", "Source", "Source quote", "Citation status",
        "Requirement ID", "Review status",
    ],
    "Run Results": [
        "Run ID", "Case ID", "Verdict", "Confidence", "Reason", "Duration (ms)", "Browser",
        "Evidence", "Attempt", "Judge rule",
    ],
    "Bugs": [
        "Bug ID", "Title", "Severity", "Steps", "Expected", "Source quote", "Actual",
        "Evidence", "Environment", "Tracker link", "Status",
    ],
    "Traceability": ["Requirement ID", "Cases", "Last verdicts", "Bugs", "Coverage status"],
    "Coverage": [
        "Segment", "Suggested", "Approved", "Executed", "Passed", "Failed", "Flaky",
        "Blocked", "Test Error", "Unable to Verify",
    ],
    "Evidence Index": ["Evidence ID", "Type", "SHA-256", "Link", "Captured at"],
}  # fmt: skip


def safe_text(value: str) -> str:
    """Redact, then neutralise formula injection."""
    text = redact(value).text
    return "'" + text if text.startswith(_DANGEROUS) else text


def _cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int | float):
        return value
    if isinstance(value, list):
        return safe_text("\n".join(f"{i}. {v}" for i, v in enumerate(value, start=1)))
    if isinstance(value, dict):
        return safe_text("\n".join(f"{k}: {v}" for k, v in value.items()))
    return safe_text(str(value))


def _sheet(
    wb: Workbook, title: str, rows: Iterable[list[Any]], verdict_col: int | None = None
) -> Worksheet:
    ws: Worksheet = wb.create_sheet(title)
    ws.append(HEADERS[title])
    for c in range(1, len(HEADERS[title]) + 1):
        ws.cell(row=1, column=c).font = Font(bold=True)
    for row in rows:
        ws.append([_cell(v) for v in row])
        if verdict_col is not None:
            cell = ws.cell(row=ws.max_row, column=verdict_col)
            colours = VERDICT_COLOURS.get(str(cell.value))
            if colours:
                cell.font = Font(color=colours[0], bold=True)
                cell.fill = PatternFill("solid", fgColor=colours[1])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(HEADERS[title]))}{max(ws.max_row, 1)}"
    return ws


def build_workbook(data: RunExport) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)  # type: ignore[arg-type]
    _sheet(wb, "Test Cases", (
        [c.code, c.journey, c.segment, c.role, c.technique, c.priority, c.preconditions,
         c.steps, c.data, c.expected, c.source, c.quote, c.citation_status, c.requirement_id,
         c.review_status]
        for c in data.cases
    ))  # fmt: skip
    _sheet(wb, "Run Results", (
        [r.run, r.case_code, r.verdict, r.confidence, r.reason, r.duration_ms, r.browser,
         r.evidence, r.attempt, r.rule]
        for r in data.results
    ), verdict_col=3)  # fmt: skip
    _sheet(wb, "Bugs", (
        [b.code, b.title, b.severity, b.steps, b.expected, b.quote, b.actual, b.evidence,
         b.environment, b.tracker_ref, b.status]
        for b in data.bugs
    ))  # fmt: skip
    _sheet(wb, "Traceability", _traceability(data))
    _sheet(wb, "Coverage", (
        [c.segment, c.suggested, c.approved, c.executed, *(c.counts.get(v, 0) for v in VERDICTS)]
        for c in data.coverage
    ))  # fmt: skip
    _sheet(wb, "Evidence Index", (
        [e.evidence_id, e.kind, e.sha256, e.link, e.captured_at] for e in data.evidence
    ))  # fmt: skip
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _traceability(data: RunExport) -> list[list[Any]]:
    verdicts: dict[str, list[str]] = {}
    for r in data.results:
        verdicts.setdefault(r.case_code, []).append(r.verdict)
    bugs_by_case: dict[str, int] = {}
    for b in data.bugs:
        case_code = b.code.split(":", 1)[0]
        bugs_by_case[case_code] = bugs_by_case.get(case_code, 0) + 1
    by_req: dict[str, list[str]] = {}
    for c in data.cases:
        if c.requirement_id:
            by_req.setdefault(c.requirement_id, []).append(c.code)
    rows = []
    for req, codes in sorted(by_req.items()):
        last = [verdicts[c][-1] for c in codes if c in verdicts]
        status = (
            "not run" if not last else ("covered" if all(v == "pass" for v in last) else "at risk")
        )
        rows.append([req, codes, last, sum(bugs_by_case.get(c, 0) for c in codes), status])
    return rows
