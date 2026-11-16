"""Quote verification: the code check behind "cited ground truth" (pillar P1, ADR-005).

A quote is verified only if its normalised form occurs *exactly* in the source's normalised
text. No model is involved. Unverified expected results become "Unable to Verify".
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.citations.normalize import normalize_text
from packages.contracts.citation import Citation

MIN_QUOTE_CHARS = 12
"""Quotes shorter than this (e.g. a single word) are too weak to count as evidence."""


@dataclass(frozen=True)
class QuoteCheck:
    """Outcome of verifying one quote."""

    verified: bool
    reason: str
    start: int | None = None
    end: int | None = None


def _occurrences(text: str, quote: str) -> list[int]:
    found: list[int] = []
    pos = text.find(quote)
    while pos != -1:
        found.append(pos)
        pos = text.find(quote, pos + 1)
    return found


def verify_quote(source_text: str, quote: str, start: int | None, end: int | None) -> QuoteCheck:
    """Check that `quote` appears exactly in `source_text` (already normalised at ingest).

    If the given offsets are wrong but the quote exists, offsets are corrected to the
    occurrence nearest to `start` (or the first one when no hint is given).
    """
    q = normalize_text(quote)
    if not q:
        return QuoteCheck(False, "empty quote")
    if len(q) < MIN_QUOTE_CHARS:
        return QuoteCheck(False, "quote too short to be evidence")

    offsets_valid = start is not None and end is not None and 0 <= start <= end <= len(source_text)
    if offsets_valid and normalize_text(source_text[start:end]) == q:
        return QuoteCheck(True, "exact match at offsets", start, end)

    hits = _occurrences(source_text, q)
    if not hits:
        return QuoteCheck(False, "quote not found in source")
    hint = start if start is not None else 0
    best = min(hits, key=lambda h: abs(h - hint))
    reason = "offsets corrected" if start is not None else "located in source"
    return QuoteCheck(True, reason, best, best + len(q))


def verify_citation(source_text: str, citation: Citation) -> Citation:
    """Return a copy of `citation` with status and offsets set by `verify_quote`."""
    check = verify_quote(source_text, citation.quote, citation.start_offset, citation.end_offset)
    if not check.verified or check.start is None or check.end is None:
        return citation.model_copy(update={"status": "unverified"})
    return citation.model_copy(
        update={"status": "verified", "start_offset": check.start, "end_offset": check.end}
    )
