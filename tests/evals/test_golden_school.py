"""Golden project 2 (school): data integrity, ingestibility and the scorer."""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

from evals import run_graph_eval
from evals.scoring import score_graph
from packages.citations.chunker import chunk_pages
from packages.citations.parsers import detect_kind, parse
from packages.citations.verify import verify_quote

GOLDEN = Path("evals/golden_projects/school")
EXPECTED = json.loads((GOLDEN / "expected_graph.json").read_text())


def _text(name: str) -> str:
    data = (GOLDEN / name).read_bytes()
    return chunk_pages(name, parse(detect_kind(data), data)).text


def test_every_expected_quote_verifies_against_the_ingested_prd() -> None:
    text = _text("PRD.md")
    quotes = [n["quote"] for n in EXPECTED["nodes"] if "quote" in n]
    assert len(quotes) == 19
    assert len(quotes) == len({q.split(":")[0] for q in quotes})  # one quote per REQ id
    for quote in quotes:
        assert verify_quote(text, quote, None, None).verified, quote


def test_every_rule_in_the_prd_is_in_the_graph_except_the_vague_one() -> None:
    ids = set(re.findall(r"^(REQ-[A-Z]+-\d+):", (GOLDEN / "PRD.md").read_text(), re.M))
    in_graph = {n["quote"].split(":")[0] for n in EXPECTED["nodes"] if "quote" in n}
    assert ids - in_graph == {"REQ-RPT-1"} and in_graph <= ids


def test_openapi_shows_the_seeded_conflict_and_vague_term_is_in_the_prd() -> None:
    data = (GOLDEN / "openapi.yaml").read_bytes()
    assert detect_kind(data) == "openapi"
    [api] = parse("openapi", data)
    assert "Body field name (string, required, minLength 2, maxLength 60)" in api
    assert "must load quickly" in (GOLDEN / "PRD.md").read_text()
    assert EXPECTED["conflicts"][0]["values"] == ["50", "60"]


def test_manual_is_ingestible_and_quotes_the_prd_messages() -> None:
    manual = _text("manual.md")
    for quote in ('the message "Class is full"', "A name must be 2 to 50 characters long"):
        assert verify_quote(manual, quote, None, None).verified, quote


def _perfect() -> list[dict]:
    produced = []
    for n in EXPECTED["nodes"]:
        node = {"type": n["type"], "label": n["label"], "review_status": "approved"}
        if n["type"] == "Rule":
            node["citations"] = [{"status": "verified"}]
        produced.append(node)
    produced += [
        {"type": "Conflict", "label": "Sources disagree on name maximum length: '50' vs '60'"},
        {
            "type": "Question",
            "label": "What exactly does 'quickly' mean: The class page must load quickly?",
        },
    ]
    return produced


def test_perfect_graph_passes() -> None:
    score = score_graph(EXPECTED, _perfect())
    assert (score.precision, score.recall, score.citation_accuracy) == (1.0, 1.0, 1.0)
    assert score.conflicts_found and score.vague_questions_found and score.passes()
    assert score.missing == [] and score.unmatched == []


def test_aliases_match_and_missing_conflict_is_reported() -> None:
    produced = [
        {"type": "Role", "label": "Admin"},
        {"type": "Journey", "label": "Enroll student"},
        {
            "type": "Requirement",
            "label": "REQ-GRD-2 letter grades",
            "citations": [{"status": "verified"}],
        },
        {"type": "Journey", "label": "Pay school fees"},  # not in the product
    ]
    score = score_graph(EXPECTED, produced)
    assert score.precision == 3 / 4
    assert "Journey: Pay school fees" in score.unmatched
    assert "Journey: Mark attendance" in score.missing
    assert not score.conflicts_found and not score.vague_questions_found


def test_runner_against_a_fake_api(capsys) -> None:  # type: ignore[no-untyped-def]
    nodes = [{"id": f"nod_{i}", **n} for i, n in enumerate(_perfect())]

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/graph"):
            return httpx.Response(200, json=[{"id": "gv_1"}])
        return httpx.Response(200, json={"nodes": nodes})

    client = httpx.Client(base_url="http://x/api/v1", transport=httpx.MockTransport(handler))
    assert run_graph_eval.main(["--project", "prj_1", "--golden", str(GOLDEN)], client) == 0
    assert json.loads(capsys.readouterr().out)["citation_accuracy"] == 1.0
