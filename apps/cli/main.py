"""`saq` command line for CI and terminals (FR-17): talks to the API with a personal API token.

    saq login --url http://localhost:8000 --token saq_pat_...
    saq status --project prj_...            saq upload --project prj_... prd.pdf api.yaml
    saq event --project prj_... start       saq plan --project prj_... --json
    saq cases --project prj_...             saq bugs --project prj_...
    saq report --project prj_... --run run_... --xlsx out.xlsx --pack out.html
    saq audit verify --project prj_...

The token comes from `SAQ_TOKEN` or the config file written by `saq login` (mode 0600).
Errors print the API error code and exit with status 1.
"""

from __future__ import annotations

import json
import os
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
