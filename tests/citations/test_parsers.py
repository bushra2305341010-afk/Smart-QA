"""Parsers + type detection (docs/workflows/01): text in the right order, offsets citable."""

import io
import json
import zipfile

import pytest

from packages.citations.chunker import chunk_pages
from packages.citations.parsers import UnsupportedSourceError, detect_kind, parse
from packages.citations.parsers.openapi import load_openapi, parse_openapi
from packages.citations.verify import verify_quote
from tests.citations.fixtures import OPENAPI_YAML, make_docx, make_pdf


def test_pdf_pages_and_citable_offsets() -> None:
    data = make_pdf(["Password must be 8 to 64 characters.", "Coupons expire after 30 days."])
    assert detect_kind(data) == "pdf"
    pages = parse("pdf", data)
    assert len(pages) == 2 and "8 to 64" in pages[0] and "30 days" in pages[1]
    doc = chunk_pages("src", pages)
    second = next(c for c in doc.chunks if c.page == 2)
    quote = "Coupons expire after 30 days."
    start = doc.text.index(quote)
    assert verify_quote(doc.text, quote, start, start + len(quote)).verified
    assert second.start_offset <= start < second.end_offset


def test_pdf_page_without_text() -> None:
    assert parse("pdf", make_pdf([""])) == [""]


def test_docx_paragraphs_and_tables_in_order() -> None:
    data = make_docx(
        ["Checkout rules", "", "Totals include VAT."],
        table=[["Field", "Rule"], ["Email", "Required"], ["", ""]],
    )
    assert detect_kind(data) == "docx"
    [text] = parse("docx", data)
    assert text == "Checkout rules\n\nTotals include VAT.\n\nField | Rule\nEmail | Required"


def test_markdown_keeps_text_and_strips_bom() -> None:
    data = "﻿# Login\n\nLock after 5 failed attempts.\n".encode()
    assert detect_kind(data) == "md"
    assert parse("md", data) == ["# Login\n\nLock after 5 failed attempts.\n"]


def test_openapi_yaml_rendering_is_stable() -> None:
    assert detect_kind(OPENAPI_YAML) == "openapi"
    [text] = parse("openapi", OPENAPI_YAML)
    assert text.startswith("Shop API 1.2\n\nOrders and checkout.\n\nGET /orders")
    assert "Parameter coupon (query, optional, string): Discount code" in text
    assert "Parameter X-Trace (header, required, any)" in text
    assert "Request body (required): application/json" in text
    assert "Request body (optional): application/json" in text  # $ref body: no fields listed
    assert "Body field total (number, required, minimum 0)" in text
    assert "Body field note (string, optional, maxLength 200)" in text
    assert "Body field weird (any, optional)" in text
    assert "Response 422: Coupon expired" in text and "Response default\n" not in text
    assert text.endswith("Response default:")
    assert parse("openapi", OPENAPI_YAML) == [text]


def test_openapi_json_and_swagger() -> None:
    doc = {"swagger": "2.0", "info": {}, "paths": {"/a": {"get": {"responses": {}}}}}
    data = json.dumps(doc).encode()
    assert detect_kind(data) == "openapi"
    assert parse_openapi(data) == ["API\n\nGET /a"]


@pytest.mark.parametrize(
    "text",
    ["key: [unclosed", "just: yaml\nwithout: paths", "[1, 2, 3]", '{"openapi": "3.0.0"}'],
)
def test_not_openapi(text: str) -> None:
    assert load_openapi(text) is None
    assert detect_kind(text.encode()) == "md"


def test_parse_openapi_rejects_other_text() -> None:
    with pytest.raises(ValueError, match="Not an OpenAPI"):
        parse_openapi(b"# hello")


def _zip(names: list[str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for n in names:
            zf.writestr(n, "x")
    return buf.getvalue()


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (_zip(["a.txt"]), "not a .docx"),
        (b"PK\x03\x04garbage", "not a .docx"),
        (b"\xff\xfe\x00binary", "binary"),
        (b"text\x00with nul", "binary"),
    ],
)
def test_unsupported_bytes(data: bytes, message: str) -> None:
    with pytest.raises(UnsupportedSourceError, match=message):
        detect_kind(data)


def test_unknown_kind() -> None:
    with pytest.raises(UnsupportedSourceError, match="No parser"):
        parse("repo", b"")
