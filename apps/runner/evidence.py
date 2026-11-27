"""Evidence per step (F21): content-addressed, hashed before upload, masked of secrets."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Literal

Kind = Literal["screenshot", "trace", "video", "har", "console", "request"]


@dataclass(frozen=True)
class Item:
    kind: Kind
    sha256: str
    data: bytes
    step_n: int | None

    @property
    def size(self) -> int:
        return len(self.data)


@dataclass
class Collector:
    items: list[Item] = field(default_factory=list)

    def add(self, kind: Kind, data: bytes, step_n: int | None = None) -> str:
        sha = hashlib.sha256(data).hexdigest()
        if not any(i.sha256 == sha and i.kind == kind and i.step_n == step_n for i in self.items):
            self.items.append(Item(kind, sha, data, step_n))
        return sha

    def refs(self) -> list[dict[str, object]]:
        return [
            {"kind": i.kind, "sha256": i.sha256, "size": i.size, "step_n": i.step_n}
            for i in self.items
        ]
