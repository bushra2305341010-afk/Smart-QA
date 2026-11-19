"""Golden project 1 (shop): data integrity, ingestibility and the scorer."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from evals import run_graph_eval
from evals.scoring import score_graph, similarity
from packages.citations.chunker import chunk_pages
from packages.citations.parsers import detect_kind, parse
from packages.citations.verify import verify_quote

GOLDEN = Path("evals/golden_projects/shop")
EXPECTED = json.loads((GOLDEN / "expected_graph.json").read_text())


def test_every_expected_quote_verifies_against_the_ingested_prd() -> None:
    data = (GOLDEN / "PRD.md").read_bytes()
    text = chunk_pages("prd", parse(detect_kind(data), data)).text
    quotes = [n["quote"] for n in EXPECTED["nodes"] if "quote" in n]
    assert len(quotes) == 12
    for quote in quotes:
        assert verify_quote(text, quote, None, None).verified, quote


def test_openapi_shows_the_seeded_conflict_and_vague_term_is_in_the_prd() -> None:
    data = (GOLDEN / "openapi.yaml").read_bytes()
    assert detect_kind(data) == "openapi"
    [api] = parse("openapi", data)
    assert "Body field password (string, optional, minLength 8, maxLength 128)" in api
    assert "must load fast" in (GOLDEN / "PRD.md").read_text()


def _perfect() -> list[dict]:
    produced = []
    for n in EXPECTED["nodes"]:
        node = {"type": n["type"], "label": n["label"], "review_status": "approved"}
        if n["type"] == "Rule":
            node["citations"] = [{"status": "verified"}]
        produced.append(node)
    produced += [
        {"type": "Conflict", "label": "Sources disagree on password maximum length: '64' vs '128'"},
        {
            "type": "Question",
            "label": "What exactly do 'fast' mean here: Search results must load fast?",
        },
    ]
    return produced


def test_perfect_graph_passes() -> None:
    score = score_graph(EXPECTED, _perfect())
    assert (score.precision, score.recall, score.citation_accuracy) == (1.0, 1.0, 1.0)
    assert score.conflicts_found and score.vague_questions_found and score.passes()
    assert score.missing == [] and score.unmatched == []


def test_partial_graph_with_aliases_extras_and_rejections() -> None:
    produced = [
        {"type": "Role", "label": "Admin"},  # alias
        {
            "type": "Requirement",
            "label": "REQ-AUTH-1 password length",
            "citations": [{"status": "verified"}],
        },
        {"type": "Rule", "label": "Coupon expiry", "citations": [{"status": "unverified"}]},
        {"type": "Journey", "label": "Wishlist"},  # not in the product
        {"type": "Journey", "label": "Checkout", "review_status": "rejected"},  # ignored
        {"type": "Screen", "label": "Cart page"},  # optional: correct, no recall credit needed
    ]
    score = score_graph(EXPECTED, produced)
    assert score.precision == pytest.approx(4 / 5)
    required = [n for n in EXPECTED["nodes"] if not n.get("optional")]
    assert score.recall == pytest.approx(3 / len(required))
    assert score.citation_accuracy == 0.5
    assert not score.conflicts_found and not score.vague_questions_found and not score.passes()
    assert "Journey: Wishlist" in score.unmatched and "Journey: Checkout" in score.missing


def test_edge_cases() -> None:
    empty = score_graph({"nodes": []}, [])
    assert (empty.precision, empty.recall, empty.citation_accuracy) == (0.0, 1.0, 0.0)
    assert similarity("", "x") == 0.0 and similarity("Log in", "login page") == 0.0


def test_runner_against_a_fake_api(capsys) -> None:  # type: ignore[no-untyped-def]
    nodes = [{"id": "nod_1", **n} for n in _perfect()]

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/graph"):
            return httpx.Response(200, json=[{"id": "gv_1"}])
        return httpx.Response(200, json={"nodes": nodes})

    client = httpx.Client(base_url="http://x/api/v1", transport=httpx.MockTransport(handler))
    assert run_graph_eval.main(["--project", "prj_1", "--golden", str(GOLDEN)], client) == 0
    assert json.loads(capsys.readouterr().out)["recall"] == 1.0
    none = httpx.Client(
        base_url="http://x/api/v1",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=[])),
    )
    with pytest.raises(SystemExit, match="No graph"):
        run_graph_eval.main(["--project", "prj_1", "--golden", str(GOLDEN)], none)
