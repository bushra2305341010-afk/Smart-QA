"""Mask personal data and secrets before any model call or log line (N33).

Order matters: specific token formats first, then emails, card numbers (Luhn-checked),
and phone numbers. `{{secret:name}}` placeholders are never touched.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{16,}=*")
_API_KEY = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|xox[abprs]-[A-Za-z0-9-]{10,}"
    r"|AKIA[0-9A-Z]{16})"
)
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_CARD = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")
_PHONE = re.compile(r"\+\d{1,3}[\s-]?\d{2,5}[\s-]?\d{3,4}[\s-]?\d{3,6}|\(\d{3}\)\s?\d{3}-\d{4}")


@dataclass(frozen=True)
class Redaction:
    """Redacted text plus how many values of each kind were masked."""

    text: str
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def redact(text: str) -> Redaction:
    """Return `text` with sensitive values replaced by `[REDACTED:<kind>]`."""
    counts: Counter[str] = Counter()

    def replacer(kind: str, keep_prefix: str = "") -> Callable[[re.Match[str]], str]:
        def _sub(_: re.Match[str]) -> str:
            counts[kind] += 1
            return f"{keep_prefix}[REDACTED:{kind}]"

        return _sub

    def card_sub(m: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        if not _luhn_ok(digits):
            return m.group(0)
        counts["card"] += 1
        return "[REDACTED:card]"

    out = _JWT.sub(replacer("jwt"), text)
    out = _BEARER.sub(replacer("bearer_token", "Bearer "), out)
    out = _API_KEY.sub(replacer("api_key"), out)
    out = _EMAIL.sub(replacer("email"), out)
    out = _CARD.sub(card_sub, out)
    out = _PHONE.sub(replacer("phone"), out)
    return Redaction(text=out, counts=dict(counts))
