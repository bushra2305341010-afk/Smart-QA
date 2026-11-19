"""Source parsers: bytes in, raw page texts out (docs/workflows/01-connect-and-ingest.md).

Parsers only extract text. Normalisation and chunking with offsets happen once, in
`packages.citations.chunker.chunk_pages`, so the quote verifier and the chunks always agree.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Callable
from typing import Literal

from packages.citations.parsers.docx import parse_docx
from packages.citations.parsers.markdown import parse_markdown
from packages.citations.parsers.openapi import load_openapi, parse_openapi
from packages.citations.parsers.pdf import parse_pdf

MAX_BYTES = 50 * 1024 * 1024
UploadKind = Literal["pdf", "docx", "md", "openapi"]


class UnsupportedSourceError(ValueError):
    """The file type is not supported or the bytes do not match the type."""


def detect_kind(data: bytes) -> UploadKind:
    """Decide the type from the bytes themselves (magic numbers), never from the filename."""
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                if "word/document.xml" in zf.namelist():
                    return "docx"
        except zipfile.BadZipFile:
            pass
        raise UnsupportedSourceError("ZIP file is not a .docx document")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise UnsupportedSourceError("Unsupported binary file") from None
    if "\x00" in text:
        raise UnsupportedSourceError("Unsupported binary file")
    if load_openapi(text) is not None:
        return "openapi"
    return "md"


PARSERS: dict[str, Callable[[bytes], list[str]]] = {
    "pdf": parse_pdf,
    "docx": parse_docx,
    "md": parse_markdown,
    "openapi": parse_openapi,
}


def parse(kind: str, data: bytes) -> list[str]:
    """Raw text per page for `kind`. Raises UnsupportedSourceError for unknown kinds."""
    parser = PARSERS.get(kind)
    if parser is None:
        raise UnsupportedSourceError(f"No parser for '{kind}'")
    return parser(data)


__all__ = ["MAX_BYTES", "UnsupportedSourceError", "detect_kind", "parse"]
