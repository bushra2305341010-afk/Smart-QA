"""Bug draft template (F28): reproducible steps, expected result with its source quote, actual
result, evidence hashes. Everything is redacted; the draft is filed only after Gate 4."""

from __future__ import annotations

from dataclasses import dataclass

from packages.model_gateway.redact import redact

SEVERITY_BY_PRIORITY = {"Must": "high", "Should": "medium", "Could": "low"}


@dataclass(frozen=True)
class BugFacts:
    case_code: str
    case_title: str
    priority: str
    steps: list[str]
    data: dict[str, str]
    expected: str
    quote: str
    source: str
    actual: str
    environment: str
    evidence: list[str]  # "kind sha256" lines


@dataclass(frozen=True)
class BugDraft:
    title: str
    severity: str
    body_md: str


def draft_bug(f: BugFacts) -> BugDraft:
    title = redact(f"[{f.case_code}] {f.case_title}: {f.actual}"[:180]).text
    steps = "\n".join(f"{i}. {s}" for i, s in enumerate(f.steps, start=1)) or "_none recorded_"
    data = "\n".join(f"- `{k}`: {v}" for k, v in sorted(f.data.items())) or "_none_"
    evidence = "\n".join(f"- {e}" for e in f.evidence) or "_none captured_"
    body = f"""## Steps to reproduce
{steps}

### Test data
{data}

## Expected
{f.expected}

> {f.quote}
> — {f.source}

## Actual
{f.actual}

## Environment
{f.environment}

## Evidence (SHA-256)
{evidence}

_Test case {f.case_code}. Drafted by Smart QA, confirmed by a human before filing._
"""
    return BugDraft(
        title=title,
        severity=SEVERITY_BY_PRIORITY.get(f.priority, "medium"),
        body_md=redact(body).text,
    )
