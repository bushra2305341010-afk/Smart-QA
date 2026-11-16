import pytest

from packages.citations.normalize import normalize_text


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("plain text", "plain text"),
        ("a\r\nb\rc", "a\nb\nc"),  # Windows / old Mac line endings
        ("a\u00a0b\u2009c\u202fd", "a b c d"),  # no-break and thin spaces
        ("a  \t b", "a b"),  # runs of spaces and tabs collapse
        ("line  \nnext", "line\nnext"),  # trailing spaces removed
        ("\u201cquoted\u201d and \u2018single\u2019", "\"quoted\" and 'single'"),
        ("en\u2013dash em\u2014dash", "en-dash em-dash"),
        ("cafe\u0301", "caf\u00e9"),  # NFC composes e + combining accent
        ("zero\u200bwidth", "zerowidth"),  # zero-width space removed
        ("a\n\n\n\nb", "a\n\nb"),  # 3+ newlines collapse to a paragraph break
        ("  lead and trail  ", "lead and trail"),
    ],
)
def test_normalize_text(raw: str, expected: str) -> None:
    assert normalize_text(raw) == expected


def test_normalize_is_idempotent() -> None:
    text = "\u201cCards\u201d  expiring\u00a0in the\r\ncurrent month."
    once = normalize_text(text)
    assert normalize_text(once) == once
