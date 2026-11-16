import pytest

from packages.citations.chunker import chunk_pages
from packages.citations.verify import verify_quote


def _pages() -> list[str]:
    return [
        "Title\n\nIntro paragraph one.\nSecond line of intro.",
        "Payments\n\nCards expiring in the current month must be accepted.",
    ]


def test_chunks_cover_text_and_offsets_slice_back_exactly() -> None:
    doc = chunk_pages("src_1", _pages(), max_chars=40)
    assert doc.chunks, "expected at least one chunk"
    for ch in doc.chunks:
        assert doc.text[ch.start_offset : ch.end_offset] == ch.text
        assert ch.source_id == "src_1"


def test_chunk_reports_page_and_line() -> None:
    doc = chunk_pages("src_1", _pages(), max_chars=200)
    target = next(c for c in doc.chunks if "Cards expiring" in c.text)
    assert target.page == 2
    # "Payments" is line 1, blank line 2, the rule is line 3 of page 2
    assert target.line in (1, 3)


def test_quote_from_a_chunk_verifies_against_document_text() -> None:
    doc = chunk_pages("src_1", _pages(), max_chars=60)
    q = "Cards expiring in the current month must be accepted."
    start = doc.text.index(q)
    assert verify_quote(doc.text, q, start, start + len(q)).verified


def test_long_paragraph_is_split_on_whitespace() -> None:
    para = " ".join(f"word{i}" for i in range(100))
    doc = chunk_pages("src_1", [para], max_chars=50)
    assert len(doc.chunks) > 1
    for ch in doc.chunks:
        assert len(ch.text) <= 50
        assert not ch.text.startswith(" ") and not ch.text.endswith(" ")


def test_unbreakable_token_is_hard_split() -> None:
    doc = chunk_pages("src_1", ["x" * 120], max_chars=50)
    assert [len(c.text) for c in doc.chunks] == [50, 50, 20]


def test_empty_pages_produce_no_chunks() -> None:
    doc = chunk_pages("src_1", ["", "   "], max_chars=50)
    assert doc.chunks == []


def test_page_lookup_for_every_chunk() -> None:
    doc = chunk_pages("src_1", ["a" * 30, "b" * 30, "c" * 30], max_chars=30)
    assert [c.page for c in doc.chunks] == [1, 2, 3]


@pytest.mark.parametrize("bad", [0, -5])
def test_max_chars_must_be_positive(bad: int) -> None:
    with pytest.raises(ValueError, match="max_chars"):
        chunk_pages("src_1", ["text"], max_chars=bad)
