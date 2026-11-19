"""Build real PDF and DOCX bytes in memory for parser tests (no binary files in the repo)."""

from __future__ import annotations

import io

from docx import Document


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(pages: list[str]) -> bytes:
    """A minimal valid PDF with one Helvetica text line per input line."""
    objects: dict[int, str] = {
        1: "<< /Type /Catalog /Pages 2 0 R >>",
        3: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    kids: list[int] = []
    next_id = 4
    for text in pages:
        page_id, content_id = next_id, next_id + 1
        next_id += 2
        shown = " ".join(f"({_esc(line)}) Tj T*" for line in text.split("\n")) if text else ""
        stream = f"BT /F1 12 Tf 72 720 Td 14 TL {shown} ET"
        objects[content_id] = f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream"
        objects[page_id] = (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
        )
        kids.append(page_id)
    objects[2] = (
        f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>"
    )
    out = b"%PDF-1.4\n"
    offsets: dict[int, int] = {}
    for i in sorted(objects):
        offsets[i] = len(out)
        out += f"{i} 0 obj\n{objects[i]}\nendobj\n".encode()
    xref, size = len(out), max(objects) + 1
    out += f"xref\n0 {size}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{offsets[i]:010d} 00000 n \n".encode() for i in range(1, size))
    out += f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


def make_docx(paragraphs: list[str], table: list[list[str]] | None = None) -> bytes:
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    if table:
        t = doc.add_table(rows=len(table), cols=len(table[0]))
        for r, row in enumerate(table):
            for c, value in enumerate(row):
                t.cell(r, c).text = value
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


OPENAPI_YAML = b"""openapi: 3.0.0
info:
  title: Shop API
  version: "1.2"
  description: Orders and checkout.
paths:
  /orders:
    post:
      summary: Place an order
      parameters:
        - name: coupon
          in: query
          description: Discount code
          schema: {type: string}
        - name: X-Trace
          in: header
          required: true
        - just-a-string
      requestBody:
        required: true
        content:
          application/json:
            schema:
              required: [total]
              properties:
                total: {type: number, minimum: 0}
                note: {type: string, maxLength: 200}
                weird: 5
      responses:
        "201": {description: Order created}
        "422": {description: Coupon expired}
        default: plain
    get:
      description: List orders
      requestBody:
        content:
          application/json:
            schema: {$ref: "#/components/schemas/Filter"}
    parameters: []
  /health: null
"""
