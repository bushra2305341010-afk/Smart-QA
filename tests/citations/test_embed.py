import json

import httpx
import pytest

from packages.citations.embed import BATCH, DIMENSIONS, EmbeddingError, LocalEmbedder
from packages.model_gateway.factory import PolicyViolationError


def _embedder(handler) -> LocalEmbedder:  # type: ignore[no-untyped-def]
    client = httpx.Client(base_url="http://ollama:11434/", transport=httpx.MockTransport(handler))
    return LocalEmbedder("http://ollama:11434", client=client)


def test_batches_order_and_dimensions() -> None:
    calls: list[list[str]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        assert req.url.path == "/v1/embeddings" and body["model"] == "bge-m3"
        calls.append(body["input"])
        data = [
            {"index": i, "embedding": [float(len(t))] * DIMENSIONS}
            for i, t in enumerate(body["input"])
        ]
        return httpx.Response(200, json={"data": list(reversed(data))})

    texts = [f"t{'x' * i}" for i in range(BATCH + 3)]
    vectors = _embedder(handler).embed(texts)
    assert [len(c) for c in calls] == [BATCH, 3]
    assert [v[0] for v in vectors] == [float(len(t)) for t in texts]
    assert _embedder(handler).embed([]) == []


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx.Response(500, text="oom"), "500"),
        (httpx.Response(200, json={"data": []}), "wrong number"),
        (
            httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1] * 768}]}),
            "768 dimensions",
        ),
    ],
)
def test_errors(response: httpx.Response, message: str) -> None:
    with pytest.raises(EmbeddingError, match=message):
        _embedder(lambda req: response).embed(["a"])


def test_unreachable_and_external_hosts() -> None:
    def down(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(EmbeddingError, match="unreachable"):
        _embedder(down).embed(["a"])
    with pytest.raises(PolicyViolationError, match="not an internal host"):
        LocalEmbedder("https://api.example.com")
    assert LocalEmbedder("http://localhost:11434").model == "bge-m3"
