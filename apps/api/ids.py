"""Prefixed public IDs (docs/06-api.md §1): `prj_<32 hex>` outside, UUID inside the DB."""

from __future__ import annotations

import uuid
from typing import Literal

from apps.api.errors import not_found

Kind = Literal[
    "usr", "prj", "src", "env", "idn", "chk", "gv", "nod", "pln", "seg", "tc", "run", "res",
    "ver", "bug", "tok", "evt",
]  # fmt: skip


def encode(kind: Kind, value: uuid.UUID) -> str:
    return f"{kind}_{value.hex}"


def decode(kind: Kind, public_id: str, what: str = "Resource") -> uuid.UUID:
    """Parse `kind_<hex>`. A malformed or wrong-kind ID is simply "not found"."""
    prefix, _, rest = public_id.partition("_")
    if prefix != kind or len(rest) != 32:
        raise not_found(what)
    try:
        return uuid.UUID(hex=rest)
    except ValueError:
        raise not_found(what) from None
