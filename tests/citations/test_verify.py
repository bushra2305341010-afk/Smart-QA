import random

import pytest

from packages.citations.normalize import normalize_text
from packages.citations.verify import MIN_QUOTE_CHARS, verify_citation, verify_quote
from packages.contracts.citation import Citation, Location

SOURCE = normalize_text(
    "Payments\n\n"
    "Cards expiring in the current month must be accepted.\n"
    "Expired cards must be rejected with a clear message.\n\n"
    "Refunds\n\n"
    "Refunds are processed within 5 business days."
)
QUOTE = "Cards expiring in the current month must be accepted."
START = SOURCE.index(QUOTE)


def test_exact_quote_at_given_offsets_is_verified() -> None:
    res = verify_quote(SOURCE, QUOTE, START, START + len(QUOTE))
    assert res.verified
    assert (res.start, res.end) == (START, START + len(QUOTE))
    assert res.reason == "exact match at offsets"


def test_wrong_offsets_are_corrected_when_quote_exists() -> None:
    res = verify_quote(SOURCE, QUOTE, 0, len(QUOTE))
    assert res.verified
    assert (res.start, res.end) == (START, START + len(QUOTE))
    assert res.reason == "offsets corrected"


def test_missing_offsets_are_located() -> None:
    res = verify_quote(SOURCE, QUOTE, None, None)
    assert res.verified and res.start == START


def test_typographic_quote_matches_after_normalisation() -> None:
    curly = "Cards expiring in the current  month must be accepted."  # double space
    res = verify_quote(SOURCE, curly, None, None)
    assert res.verified


def test_paraphrase_is_not_verified() -> None:
    res = verify_quote(SOURCE, "Cards that expire this month should be accepted.", None, None)
    assert not res.verified
    assert res.reason == "quote not found in source"
    assert res.start is None and res.end is None


def test_single_word_change_is_not_verified() -> None:
    altered = QUOTE.replace("must", "may")
    assert not verify_quote(SOURCE, altered, START, START + len(altered)).verified


@pytest.mark.parametrize("quote", ["", "   ", "\n"])
def test_empty_quote_is_rejected(quote: str) -> None:
    res = verify_quote(SOURCE, quote, None, None)
    assert not res.verified and res.reason == "empty quote"


def test_too_short_quote_is_rejected() -> None:
    short = "Refunds"
    assert len(short) < MIN_QUOTE_CHARS
    res = verify_quote(SOURCE, short, None, None)
    assert not res.verified and res.reason == "quote too short to be evidence"


@pytest.mark.parametrize(("start", "end"), [(-1, 10), (5, 3), (0, 10_000)])
def test_invalid_offsets_fall_back_to_search(start: int, end: int) -> None:
    res = verify_quote(SOURCE, QUOTE, start, end)
    assert res.verified and res.reason == "offsets corrected"


def test_ambiguous_quote_picks_occurrence_nearest_to_hint() -> None:
    text = normalize_text("The user must be logged in. Later: The user must be logged in.")
    q = "The user must be logged in."
    second = text.rindex(q)
    res = verify_quote(text, q, second + 3, None)
    assert res.verified and res.start == second


def test_ambiguous_quote_without_hint_picks_first() -> None:
    text = normalize_text("The user must be logged in. Later: The user must be logged in.")
    res = verify_quote(text, "The user must be logged in.", None, None)
    assert res.verified and res.start == 0


def test_random_substrings_always_verify() -> None:
    rng = random.Random(42)
    for _ in range(300):
        a = rng.randrange(0, len(SOURCE) - MIN_QUOTE_CHARS)
        b = rng.randrange(a + MIN_QUOTE_CHARS, len(SOURCE) + 1)
        quote = SOURCE[a:b]
        if not quote.strip() or len(normalize_text(quote)) < MIN_QUOTE_CHARS:
            continue
        assert verify_quote(SOURCE, quote, a, b).verified, quote


def test_verify_citation_returns_updated_copy() -> None:
    cit = Citation(
        source_id="src_1",
        start_offset=0,
        end_offset=5,
        quote=QUOTE,
        location=Location(file="PRD-v3.pdf", page=12, line=4),
    )
    out = verify_citation(SOURCE, cit)
    assert out.status == "verified"
    assert out.start_offset == START
    assert cit.status == "unverified"  # original untouched (frozen model)


def test_verify_citation_marks_unverified() -> None:
    cit = Citation(source_id="src_1", start_offset=0, end_offset=5, quote="Not in the PRD at all.")
    assert verify_citation(SOURCE, cit).status == "unverified"
