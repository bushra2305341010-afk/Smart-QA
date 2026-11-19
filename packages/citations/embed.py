"""Chunk embeddings through a local, OpenAI-compatible `/v1/embeddings` server (T-204).

Ollama, vLLM, llama.cpp and LM Studio all serve this endpoint. The server must be on an internal
host: chunks are company documents and never leave the network for retrieval (pillar P4). The
schema stores `vector(1024)`; `bge-m3` (1024 dimensions) is the default model.
"""

from __future__ import annotations

from collections.abc import Sequence

import httpx

from packages.model_gateway.factory import PolicyViolationError, is_internal_url

DIMENSIONS = 1024
BATCH = 32


class EmbeddingError(Exception):
    pass


class LocalEmbedder:
    def __init__(
        self,
        base_url: str,
        model: str = "bge-m3",
        client: httpx.Client | None = None,
        timeout_s: float = 60.0,
    ) -> None:
        if not is_internal_url(base_url):
            raise PolicyViolationError(f"Embedding server {base_url} is not an internal host")
        self.model = model
        self.client = client or httpx.Client(base_url=base_url.rstrip("/") + "/", timeout=timeout_s)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """One vector per text, in order, in batches."""
        vectors: list[list[float]] = []
        for i in range(0, len(texts), BATCH):
            batch = list(texts[i : i + BATCH])
            try:
                res = self.client.post("v1/embeddings", json={"model": self.model, "input": batch})
            except httpx.HTTPError as exc:
                raise EmbeddingError(f"Embedding server unreachable: {exc}") from exc
            if res.status_code >= 400:
                raise EmbeddingError(f"Embedding server {res.status_code}: {res.text[:200]}")
            data = sorted(res.json()["data"], key=lambda d: d["index"])
            if len(data) != len(batch):
                raise EmbeddingError("Embedding server returned the wrong number of vectors")
            for item in data:
                vector = [float(x) for x in item["embedding"]]
                if len(vector) != DIMENSIONS:
                    got = len(vector)
                    raise EmbeddingError(
                        f"Model {self.model} gives {got} dimensions; the schema needs {DIMENSIONS}"
                    )
                vectors.append(vector)
        return vectors
