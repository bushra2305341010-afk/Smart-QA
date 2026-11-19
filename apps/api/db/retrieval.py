"""Semantic retrieval over chunks (pgvector cosine distance, HNSW index; T-204).

Retrieval only *finds* candidate passages; every quote that ends up in a graph node or an
expected result is still verified exactly against the source text (pillar P1).
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.db.models import Chunk


def similar_chunks(s: Session, vector: Sequence[float], k: int = 8) -> list[tuple[Chunk, float]]:
    """The `k` chunks of the scoped project closest to `vector`, with their cosine distance."""
    distance = Chunk.embedding.cosine_distance(list(vector))
    rows = s.execute(
        select(Chunk, distance).where(Chunk.embedding.is_not(None)).order_by(distance).limit(k)
    ).all()
    return [(chunk, float(d)) for chunk, d in rows]
