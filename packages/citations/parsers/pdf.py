"""PDF: one text per page with pypdf (BSD licence; PyMuPDF is AGPL).

Scanned PDFs without a text layer produce empty pages; the ingest worker flags them.
"""

from __future__ import annotations

import io

from pypdf import PdfReader


def parse_pdf(data: bytes) -> list[str]:
    reader = PdfReader(io.BytesIO(data))
    return [page.extract_text() or "" for page in reader.pages]
