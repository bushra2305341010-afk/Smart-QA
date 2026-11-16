import pytest
from pydantic import ValidationError

from packages.contracts.citation import Chunk, Citation


def test_citation_is_frozen() -> None:
    c = Citation(source_id="s", start_offset=0, end_offset=3, quote="abc")
    with pytest.raises(ValidationError):
        c.quote = "changed"  # type: ignore[misc]


def test_citation_rejects_negative_offsets() -> None:
    with pytest.raises(ValidationError):
        Citation(source_id="s", start_offset=-1, end_offset=3, quote="abc")


def test_citation_rejects_end_before_start() -> None:
    with pytest.raises(ValidationError, match="end_offset"):
        Citation(source_id="s", start_offset=5, end_offset=3, quote="abc")


def test_chunk_page_and_line_are_one_based() -> None:
    with pytest.raises(ValidationError):
        Chunk(source_id="s", text="t", start_offset=0, end_offset=1, page=0, line=1)


def test_citation_json_roundtrip() -> None:
    c = Citation(source_id="s", start_offset=0, end_offset=3, quote="abc", status="verified")
    assert Citation.model_validate_json(c.model_dump_json()) == c
