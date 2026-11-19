"""Deterministic duplicate detection (N15) and human-readable case codes."""

from __future__ import annotations

import re

from packages.contracts.case import DesignedCase
from packages.graph.model import norm_label


def case_fingerprint(case: DesignedCase) -> tuple[str, str, str]:
    """Same role + same normalised steps + same normalised expected result = duplicate."""
    steps = " | ".join(norm_label(s.action) for s in case.steps)
    return norm_label(case.role), steps, norm_label(case.expected_text)


def dedupe(cases: list[DesignedCase]) -> tuple[list[DesignedCase], int]:
    """Keep the first of each fingerprint. Returns (unique cases, duplicates dropped)."""
    seen: set[tuple[str, str, str]] = set()
    unique: list[DesignedCase] = []
    for case in cases:
        key = case_fingerprint(case)
        if key not in seen:
            seen.add(key)
            unique.append(case)
    return unique, len(cases) - len(unique)


def code_prefix(journey: str) -> str:
    """`TC-<first 3 letters of the journey>`; e.g. "Sign up" → TC-SIG, "2FA" → TC-2FA."""
    letters = re.sub(r"[^A-Za-z0-9]", "", journey).upper()
    return f"TC-{(letters or 'GEN')[:3]}"


def next_codes(prefix: str, existing: list[str], count: int) -> list[str]:
    """Continue numbering after the highest existing `<prefix>-NNN`."""
    numbers = [
        int(m.group(1)) for c in existing if (m := re.fullmatch(rf"{re.escape(prefix)}-(\d+)", c))
    ]
    start = max(numbers, default=0) + 1
    return [f"{prefix}-{n:03d}" for n in range(start, start + count)]
