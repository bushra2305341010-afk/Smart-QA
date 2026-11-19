"""DOCX: paragraphs and tables in document order (tables are a common home for rules).

Table rows become `cell | cell | cell` lines. A DOCX has no fixed pages, so it is one page.
"""

from __future__ import annotations

import io

from docx import Document
from docx.text.paragraph import Paragraph


def parse_docx(data: bytes) -> list[str]:
    doc = Document(io.BytesIO(data))
    blocks: list[str] = []
    for item in doc.iter_inner_content():
        if isinstance(item, Paragraph):
            if item.text.strip():
                blocks.append(item.text)
        else:  # Table (iter_inner_content yields only paragraphs and tables)
            rows = [" | ".join(cell.text.strip() for cell in row.cells) for row in item.rows]
            blocks.append("\n".join(r for r in rows if r.strip(" |")))
    return ["\n\n".join(blocks)]
