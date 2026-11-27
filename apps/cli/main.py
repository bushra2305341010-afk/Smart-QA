"""`saq` command line for CI and terminals (FR-17): talks to the API with a personal API token.

    saq login --url http://localhost:8000 --token saq_pat_...
    saq status --project prj_...            saq upload --project prj_... prd.pdf api.yaml
    saq event --project prj_... start       saq plan --project prj_... --json
    saq cases --project prj_...             saq bugs --project prj_...
    saq report --project prj_... --run run_... --xlsx out.xlsx --pack out.html
    saq audit verify --project prj_...
    saq run --project prj_... --journey Checkout --wait     (exit 1 on Fail / Test Error)
    saq verdicts --project prj_... [--run run_...]

The token comes from `SAQ_TOKEN` or the config file written by `saq login` (mode 0600).
Errors print the API error code and exit with status 1.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer

app = typer.Typer(help="Smart Autonomous QA command line.", no_args_is_help=True)
audit_app = typer.Typer(help="Audit ledger.", no_args_is_help=True)
app.add_typer(audit_app, name="audit")
mcp_app = typer.Typer(help="MCP server for coding agents (read-only).", no_args_is_help=True)
app.add_typer(mcp_app, name="mcp")

Project = Annotated[str, typer.Option("--project", "-p", help="Project ID (prj_...)")]
AsJson = Annotated[bool, typer.Option("--json", help="Print raw JSON")]


def config_path() -> Path:
    return Path(os.environ.get("SAQ_CONFIG", Path.home() / ".config" / "saq" / "config.json"))


def load_config() -> dict[str, str]:
    path = config_path()
    data: dict[str, str] = json.loads(path.read_text()) if path.exists() else {}
    if os.environ.get("SAQ_URL"):
        data["url"] = os.environ["SAQ_URL"]
    if os.environ.get("SAQ_TOKEN"):
        data["token"] = os.environ["SAQ_TOKEN"]
    return data


def default_client(url: str, token: str) -> httpx.Client:
    return httpx.Client(
        base_url=url.rstrip("/") + "/api/v1",
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )


# Tests replace this with a factory that returns a FastAPI TestClient.
CLIENT_FACTORY: Callable[[str, str], httpx.Client] = default_client


def client() -> httpx.Client:
    conf = load_config()
    if not conf.get("url") or not conf.get("token"):
        fail("NOT_LOGGED_IN", "Run `saq login --url ... --token ...` or set SAQ_URL and SAQ_TOKEN")
    return CLIENT_FACTORY(conf["url"], conf["token"])


def fail(code: str, message: str) -> None:
    typer.echo(f"error {code}: {message}", err=True)
    raise typer.Exit(1)


def call(method: str, path: str, **kw: Any) -> httpx.Response:
    res = client().request(method, path, **kw)
    if res.status_code >= 400:
        try:
            err = res.json()["error"]
            fail(err["code"], err["message"])
        except (ValueError, KeyError, TypeError):
            fail(str(res.status_code), res.text[:200])
    return res


def show(data: Any, as_json: bool, lines: Callable[[Any], list[str]]) -> None:
    if as_json:
        typer.echo(json.dumps(data, indent=2, default=str))
    else:
        for line in lines(data):
            typer.echo(line)


@app.command()
def login(
    url: Annotated[str, typer.Option(help="API base URL, e.g. http://localhost:8000")],
    token: Annotated[str, typer.Option(prompt=True, hide_input=True, help="saq_pat_... token")],
) -> None:
    """Check the token against the API and save it (file mode 0600)."""
    res = CLIENT_FACTORY(url, token).get("/me")
    if res.status_code != 200:
        fail("UNAUTHENTICATED", "The API rejected this token")
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"url": url, "token": token}))
    path.chmod(0o600)
    typer.echo(f"Logged in as {res.json()['email']}")


@app.command()
def status(project: Project, as_json: AsJson = False) -> None:
    """Project and pipeline state."""
    data = {
        "project": call("GET", f"/projects/{project}").json(),
        "pipeline": call("GET", f"/projects/{project}/pipeline").json()["current"],
    }

    def lines(d: dict[str, Any]) -> list[str]:
        cur = d["pipeline"]
        state = f"{cur['stage']} / {cur['status']}" if cur else "not started"
        return [
            f"{d['project']['name']} ({d['project']['id']}), role {d['project']['role']}",
            f"pipeline: {state}",
        ]

    show(data, as_json, lines)


@app.command()
def upload(
    project: Project,
    files: Annotated[list[Path], typer.Argument(exists=True, dir_okay=False, readable=True)],
    as_json: AsJson = False,
) -> None:
    """Upload documents (PDF, DOCX, Markdown, OpenAPI)."""
    out = []
    for path in files:
        with path.open("rb") as fh:
            res = call(
                "POST", f"/projects/{project}/sources/upload", files={"file": (path.name, fh)}
            )
        out.append(res.json())
    show(
        out,
        as_json,
        lambda d: [f"{s['id']}  {s['kind']:8} {s['status']:8} {s['filename']}" for s in d],
    )


@app.command()
def event(
    project: Project,
    name: Annotated[str, typer.Argument(help="start, retry, cancel or a gate decision")],
    as_json: AsJson = False,
) -> None:
    """Send a pipeline event (gates are still checked by the server)."""
    data = call("POST", f"/projects/{project}/pipeline/events", json={"event": name}).json()
    show(data, as_json, lambda d: [f"pipeline: {d['stage']} / {d['status']}"])


@app.command()
def plan(project: Project, as_json: AsJson = False) -> None:
    """The latest plan with counts and reasons."""
    plans = call("GET", f"/projects/{project}/plans").json()
    if not plans:
        fail("NOT_FOUND", "No plan yet")

    def lines(p: dict[str, Any]) -> list[str]:
        totals = f"{p['approved_total']} approved of {p['suggested_total']} suggested"
        out = [f"{p['id']} {p['status']}: {totals}"]
        for seg in p["segments"]:
            risk = f"{seg['priority']}, risk {seg['risk_score']:.2f}"
            out.append(f"  {seg['journey']}: {seg['suggested_count']} suggested ({risk})")
            out += [f"    {r['technique']}: {r['count']} - {r['reason']}" for r in seg["rows"]]
        return out

    show(plans[0], as_json, lines)


@app.command()
def cases(project: Project, as_json: AsJson = False) -> None:
    """Test cases of the approved plan."""
    data = call("GET", f"/projects/{project}/cases", params={"limit": 200}).json()["items"]

    def lines(d: list[dict[str, Any]]) -> list[str]:
        out = []
        for c in d:
            cited = (c["citation"] or {}).get("status", "")
            out.append(f"{c['code']}  {c['review_status']:9} {cited:16} {c['title']}")
        return out

    show(data, as_json, lines)


@app.command()
def bugs(project: Project, as_json: AsJson = False) -> None:
    """Bug drafts and filed bugs."""
    data = call("GET", f"/projects/{project}/bugs").json()

    def lines(d: list[dict[str, Any]]) -> list[str]:
        out = []
        for b in d:
            ref = b["tracker_ref"] or ""
            out.append(f"{b['id']}  {b['severity']:8} {b['status']:9} {b['title']}  {ref}".rstrip())
        return out

    show(data, as_json, lines)


@app.command()
def report(
    project: Project,
    run: Annotated[str, typer.Option(help="Run ID (run_...)")],
    xlsx: Annotated[Path | None, typer.Option(help="Write the workbook here")] = None,
    pack: Annotated[Path | None, typer.Option(help="Write the HTML evidence pack here")] = None,
) -> None:
    """Download the run workbook and/or evidence pack."""
    if xlsx is None and pack is None:
        fail("VALIDATION_ERROR", "Give --xlsx and/or --pack")
    for path, suffix in ((xlsx, "export.xlsx"), (pack, "evidence-pack")):
        if path is not None:
            path.write_bytes(call("GET", f"/projects/{project}/runs/{run}/{suffix}").content)
            typer.echo(f"wrote {path}")


VERDICT_ORDER = ("fail", "test_error", "blocked", "flaky", "unable_to_verify", "pass")
WAIT_DONE = {"bug_review", "report", "done"}
SLEEP: Callable[[float], None] = time.sleep


def _verdict_lines(run: dict[str, Any]) -> list[str]:
    counts: dict[str, int] = {}
    for c in run["cases"]:
        counts[c["verdict"] or "pending"] = counts.get(c["verdict"] or "pending", 0) + 1
    head = ", ".join(f"{counts[v]} {v}" for v in (*VERDICT_ORDER, "pending") if v in counts)
    out = [f"{run['id']}  {run['status']}  {head or 'no results'}"]
    for c in run["cases"]:
        out.append(f"  {c['code']:12} {(c['verdict'] or 'pending'):16} {c['rule'] or ''}".rstrip())
    return out


def _latest_run(project: str) -> dict[str, Any]:
    items = call("GET", f"/projects/{project}/runs", params={"limit": 1}).json()["items"]
    if not items:
        fail("NOT_FOUND", "No run yet")
    return dict(call("GET", f"/projects/{project}/runs/{items[0]['id']}").json())


@app.command()
def run(
    project: Project,
    journey: Annotated[list[str] | None, typer.Option(help="Only these journeys")] = None,
    env: Annotated[str | None, typer.Option(help="Environment ID (env_...)")] = None,
    wait: Annotated[
        bool, typer.Option(help="Wait for verdicts; exit 1 on Fail/Test Error")
    ] = False,
    timeout: Annotated[int, typer.Option(help="Seconds to wait")] = 1800,
    as_json: AsJson = False,
) -> None:
    """Start a regression run of the approved test cases."""
    body: dict[str, Any] = {"journeys": journey or [], "source": "cli"}
    if env:
        body["env_id"] = env
    before = call("GET", f"/projects/{project}/runs", params={"limit": 1}).json()["items"]
    started = call("POST", f"/projects/{project}/runs", json=body).json()
    if not wait:
        show(started, as_json, lambda d: [f"run requested: {d['stage']} {d['status']}"])
        return
    deadline = time.monotonic() + timeout
    while True:
        cur = call("GET", f"/projects/{project}/pipeline").json()["current"]
        if cur["status"] in ("failed", "cancelled"):
            fail("RUN_FAILED", f"pipeline {cur['stage']} {cur['status']}")
        latest = call("GET", f"/projects/{project}/runs", params={"limit": 1}).json()["items"]
        is_new = latest and (not before or latest[0]["id"] != before[0]["id"])
        if cur["stage"] in WAIT_DONE and is_new:
            break
        if time.monotonic() > deadline:
            fail("TIMEOUT", f"still at {cur['stage']} {cur['status']}")
        SLEEP(5)
    result = _latest_run(project)
    show(result, as_json, _verdict_lines)
    if any(c["verdict"] in ("fail", "test_error") for c in result["cases"]):
        raise typer.Exit(1)


@app.command()
def verdicts(
    project: Project,
    run_id: Annotated[str | None, typer.Option("--run", help="Run ID (default: latest)")] = None,
    as_json: AsJson = False,
) -> None:
    """Verdicts of a run with rule ids."""
    data = (
        call("GET", f"/projects/{project}/runs/{run_id}").json() if run_id else _latest_run(project)
    )
    show(data, as_json, _verdict_lines)


@audit_app.command("verify")
def audit_verify(project: Project, as_json: AsJson = False) -> None:
    """Verify the project's hash-chained audit ledger. Exit 1 if it is broken."""
    data = call("GET", f"/projects/{project}/audit", params={"verify": "true", "limit": 1}).json()
    result = {"verified": data["verified"], "broken_at_seq": data["broken_at_seq"]}
    show(
        result,
        as_json,
        lambda d: [
            "audit chain OK" if d["verified"] else f"audit chain BROKEN at seq {d['broken_at_seq']}"
        ],
    )
    if not result["verified"]:
        raise typer.Exit(1)


def mcp_server(project: str) -> Any:
    """Build the MCP server bound to this CLI's credentials (checked before serving)."""
    from apps.mcp.server import build_server

    client().close()  # fails early with NOT_LOGGED_IN if there are no credentials
    return build_server(client, project)


@mcp_app.command("serve")
def mcp_serve(project: Project) -> None:  # pragma: no cover - blocks on stdio
    """Serve the read-only tools over stdio: `claude mcp add smart-qa -- saq mcp serve -p prj_…`."""
    mcp_server(project).run("stdio")


def main() -> None:  # pragma: no cover - console entry point
    app(prog_name="saq")


if __name__ == "__main__":  # pragma: no cover
    main()
