"""Split a document into citable chunks with exact offsets, page and line numbers."""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field

from packages.citations.normalize import normalize_text
from packages.contracts.citation import Chunk

PAGE_SEPARATOR = "\n\n"


@dataclass(frozen=True)
class ChunkedDocument:
    """Normalised full text of a source plus its chunks. Offsets index into `text`."""

    source_id: str
    text: str
    chunks: list[Chunk] = field(default_factory=list)


def _split_long(text: str, base: int, max_chars: int) -> list[tuple[int, int]]:
    """Split one paragraph into spans of at most `max_chars`, preferring whitespace."""
    spans: list[tuple[int, int]] = []
    i = 0
    n = len(text)
    while i < n:
        j = min(i + max_chars, n)
        if j < n:
            cut = text.rfind(" ", i, j + 1)
            if cut > i:
                j = cut
        spans.append((base + i, base + j))
        # Text is normalised (single spaces), so at most one space separates pieces.
        i = j + 1 if j < n and text[j] == " " else j
    return spans


def chunk_pages(source_id: str, pages: list[str], max_chars: int = 1200) -> ChunkedDocument:
    """Normalise each page, join them, and cut paragraph-aligned chunks.

    Every chunk satisfies `doc.text[chunk.start_offset:chunk.end_offset] == chunk.text`.
    """
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")

    norm_pages = [normalize_text(p) for p in pages]
    page_starts: list[int] = []
    parts: list[str] = []
    offset = 0
    for p in norm_pages:
        page_starts.append(offset)
        parts.append(p)
        offset += len(p) + len(PAGE_SEPARATOR)
    text = PAGE_SEPARATOR.join(parts)

    spans: list[tuple[int, int]] = []
    for page_start, page_text in zip(page_starts, norm_pages, strict=True):
        para_start = 0
        for para in page_text.split("\n\n"):
            if para.strip():
                base = page_start + para_start
                if len(para) <= max_chars:
                    spans.append((base, base + len(para)))
                else:
                    spans.extend(_split_long(para, base, max_chars))
            para_start += len(para) + 2

    merged: list[tuple[int, int]] = []
    for s, e in spans:
        same_page = merged and bisect.bisect_right(
            page_starts, merged[-1][0]
        ) == bisect.bisect_right(page_starts, s)
        if merged and same_page and e - merged[-1][0] <= max_chars:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))

    chunks: list[Chunk] = []
    for s, e in merged:
        page_idx = bisect.bisect_right(page_starts, s) - 1
        line = text.count("\n", page_starts[page_idx], s) + 1
        chunks.append(
            Chunk(
                source_id=source_id,
                text=text[s:e],
                start_offset=s,
                end_offset=e,
                page=page_idx + 1,
                line=line,
            )
        )
    return ChunkedDocument(source_id=source_id, text=text, chunks=chunks)
