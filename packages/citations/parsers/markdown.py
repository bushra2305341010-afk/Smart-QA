"""Markdown / plain text: one page, kept as written (headings and lists stay readable)."""

from __future__ import annotations


def parse_markdown(data: bytes) -> list[str]:
    return [data.decode("utf-8-sig")]
