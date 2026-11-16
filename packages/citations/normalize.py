"""Text normalisation shared by ingest and quote verification.

The same function must run on stored source text and on quotes before comparing them.
Changing it requires re-ingesting sources (docs/workflows/01-connect-and-ingest.md).
"""

from __future__ import annotations

import re
import unicodedata

_TRANSLATE = str.maketrans(
    {
        "\u201c": '"',  # left double quotation mark
        "\u201d": '"',  # right double quotation mark
        "\u201e": '"',  # double low-9 quotation mark
        "\u2018": "'",  # left single quotation mark
        "\u2019": "'",  # right single quotation mark
        "\u201a": "'",  # single low-9 quotation mark
        "\u2013": "-",  # en dash
        "\u2014": "-",  # em dash
        "\u2212": "-",  # minus sign
        "\u00a0": " ",  # no-break space
        "\u2007": " ",  # figure space
        "\u2009": " ",  # thin space
        "\u202f": " ",  # narrow no-break space
        "\u200b": None,  # zero-width space
        "\u200c": None,  # zero-width non-joiner
        "\u200d": None,  # zero-width joiner
        "\ufeff": None,  # byte-order mark
    }
)
_SPACES = re.compile(r"[ \t\f\v]+")
_TRAILING = re.compile(r" +\n")
_BLANK_RUNS = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    """Return `text` in canonical form: NFC, plain quotes/dashes/spaces, tidy whitespace.

    Line breaks are kept (needed for line numbers); runs of 3+ newlines become one blank line.
    The function is idempotent.
    """
    out = unicodedata.normalize("NFC", text)
    out = out.replace("\r\n", "\n").replace("\r", "\n")
    out = out.translate(_TRANSLATE)
    out = _SPACES.sub(" ", out)
    out = _TRAILING.sub("\n", out)
    out = _BLANK_RUNS.sub("\n\n", out)
    return out.strip()
