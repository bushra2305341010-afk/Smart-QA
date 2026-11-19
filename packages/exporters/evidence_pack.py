"""Evidence pack (N23): one self-contained HTML file per run that a reviewer can open offline.

Every value is redacted and HTML-escaped (document and page text are untrusted), there is no
script, and every evidence item is listed with its SHA-256 so files can be checked later.
"""

from __future__ import annotations

from html import escape

from packages.exporters.excel import VERDICT_COLOURS
from packages.exporters.model import RunExport
from packages.model_gateway.redact import redact

CSS = """
body{font:14px/1.5 system-ui,sans-serif;color:#0F172A;margin:24px;max-width:1100px}
h1{color:#4338CA}table{border-collapse:collapse;width:100%;margin:12px 0 28px}
th,td{border:1px solid #E2E8F0;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#F1F5F9}code{font-size:12px;word-break:break-all}
.v{font-weight:600;padding:2px 8px;border-radius:999px;white-space:nowrap}
blockquote{margin:4px 0;padding-left:8px;border-left:3px solid #0D9488;color:#334155}
"""


def _t(value: object) -> str:
    return escape(redact("" if value is None else str(value)).text)


def _badge(verdict: str) -> str:
    fg, bg = VERDICT_COLOURS.get(verdict, ("0F172A", "F1F5F9"))
    return f'<span class="v" style="color:#{fg};background:#{bg}">{_t(verdict)}</span>'


def _table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def build_evidence_pack(data: RunExport) -> str:
    totals: dict[str, int] = {}
    for r in data.results:
        totals[r.verdict] = totals.get(r.verdict, 0) + 1
    summary = " ".join(f"{_badge(v)} {n}" for v, n in sorted(totals.items())) or "No results"
    cases = {c.code: c for c in data.cases}
    results = [
        [
            _t(r.case_code),
            _badge(r.verdict),
            _t(r.reason),
            (
                f"<blockquote>{_t(cases[r.case_code].quote)}</blockquote>"
                if r.case_code in cases
                else ""
            ),
            "<br>".join(f"<code>{_t(e)}</code>" for e in r.evidence),
        ]
        for r in data.results
    ]
    bugs = [[_t(b.title), _t(b.severity), _t(b.status), _t(b.tracker_ref or "")] for b in data.bugs]
    evidence = [
        [_t(e.evidence_id), _t(e.kind), f"<code>{_t(e.sha256)}</code>", _t(e.captured_at)]
        for e in data.evidence
    ]
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        f"<title>Evidence pack {_t(data.run)}</title><style>{CSS}</style></head><body>"
        f"<h1>Evidence pack</h1><p>Project <b>{_t(data.project)}</b>, "
        f"run <code>{_t(data.run)}</code></p>"
        f"<p>{summary}</p>"
        "<h2>Results</h2>"
        + _table(["Case", "Verdict", "Reason", "Expected (source quote)", "Evidence"], results)
        + "<h2>Bugs</h2>"
        + _table(["Title", "Severity", "Status", "Tracker"], bugs)
        + "<h2>Evidence index (SHA-256)</h2>"
        + _table(["Evidence", "Type", "SHA-256", "Captured"], evidence)
        + "</body></html>"
    )
