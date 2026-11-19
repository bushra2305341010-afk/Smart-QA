"""Score a project's graph against a golden graph through the API.

    SAQ_URL=http://localhost:8000 SAQ_TOKEN=saq_pat_... \\
    uv run python -m evals.run_graph_eval --project prj_... --golden evals/golden_projects/shop

Exit code 0 when precision >= 0.80, recall >= 0.75 and citation accuracy >= 0.90.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx

from evals.scoring import score_graph


def fetch_latest_graph(client: httpx.Client, project: str) -> list[dict[str, Any]]:
    versions = client.get(f"/projects/{project}/graph").raise_for_status().json()
    if not versions:
        raise SystemExit("No graph version yet")
    graph = client.get(f"/projects/{project}/graph/{versions[0]['id']}").raise_for_status().json()
    nodes: list[dict[str, Any]] = graph["nodes"]
    return nodes


def main(argv: list[str] | None = None, client: httpx.Client | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--golden", type=Path, required=True)
    args = parser.parse_args(argv)
    expected = json.loads((args.golden / "expected_graph.json").read_text())
    client = client or httpx.Client(
        base_url=os.environ["SAQ_URL"].rstrip("/") + "/api/v1",
        headers={"Authorization": f"Bearer {os.environ['SAQ_TOKEN']}"},
        timeout=60,
    )
    score = score_graph(expected, fetch_latest_graph(client, args.project))
    print(json.dumps(asdict(score), indent=2))
    return 0 if score.passes() else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
