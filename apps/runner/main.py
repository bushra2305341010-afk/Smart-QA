"""Runner process: `uv run python -m apps.runner` inside the team network (sector 05).

Outbound only: it calls the control plane, nothing calls it. Each job gets a fresh browser
context (no cookies or storage shared between tests or attempts). Evidence is uploaded before
the result, so the result can reference it by hash. A killed runner simply stops renewing its
lease; the job is re-leased to another runner and the result write stays idempotent.

Environment:
  SAQ_API_URL            e.g. https://qa.example.com/api/v1
  SAQ_RUNNER_TOKEN       saq_run_... from POST /projects/{id}/runners
  SAQ_BROWSER_CHANNEL    optional, e.g. "chrome" to use the installed Chrome
  SAQ_SECRET_<NAME>      values for {{secret:name}} placeholders (never sent anywhere)
  SAQ_VAULT_FILE / SAQ_VAULT_KEY   encrypted vault for the same placeholders (T-203)
  SAQ_CLIENT_CERT / SAQ_CLIENT_KEY   optional client certificate for mTLS
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from apps.runner.evidence import Collector
from apps.runner.executor import CaseRunner
from apps.runner.policy_hook import policy_context
from apps.runner.secrets import EnvSecrets, Resolver, SecretSource
from apps.runner.vault import Vault
from packages.contracts.run import AttemptResult, CompiledCase

log = logging.getLogger("saq.runner")
VERSION = "runner/1"


class RunnerClient:
    def __init__(self, http: httpx.Client) -> None:
        self.http = http

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> RunnerClient:  # pragma: no cover
        env = dict(os.environ if environ is None else environ)
        cert = (
            (env["SAQ_CLIENT_CERT"], env["SAQ_CLIENT_KEY"]) if env.get("SAQ_CLIENT_CERT") else None
        )
        http = httpx.Client(
            base_url=env["SAQ_API_URL"].rstrip("/"),
            headers={"Authorization": f"Bearer {env['SAQ_RUNNER_TOKEN']}"},
            cert=cert,
            timeout=60,
        )
        return cls(http)

    def _ok(self, resp: httpx.Response) -> httpx.Response:
        resp.raise_for_status()
        return resp

    def heartbeat(self) -> dict[str, Any]:
        return dict(self._ok(self.http.post("/runner/heartbeat", json={"version": VERSION})).json())

    def pull(self) -> dict[str, Any] | None:
        resp = self._ok(self.http.post("/runner/jobs/pull"))
        return None if resp.status_code == 204 else dict(resp.json())

    def upload(self, kind: str, sha256: str, data: bytes, retries: int = 3) -> None:
        for attempt in range(1, retries + 1):
            try:
                self._ok(self.http.put(f"/runner/evidence/{sha256}", params={"kind": kind},
                                       content=data))  # fmt: skip
                return
            except httpx.HTTPError:
                if attempt == retries:
                    raise

    def report(self, job_id: str, result: AttemptResult, evidence: list[dict[str, Any]],
               browser: str) -> dict[str, Any]:  # fmt: skip
        body = {"result": result.model_dump(mode="json"), "evidence": evidence, "browser": browser}
        return dict(self._ok(self.http.post(f"/runner/jobs/{job_id}/result", json=body)).json())


@dataclass
class Browser:
    """What `run_job` needs from Playwright: a factory for fresh isolated pages."""

    new_context: Callable[[], Any]
    name: str


def run_job(job: dict[str, Any], browser: Browser, secrets: list[SecretSource]) -> tuple[
    AttemptResult, Collector
]:  # fmt: skip
    case = CompiledCase.model_validate(job["case"])
    env = job["env"]
    collector = Collector()
    resolver = Resolver(*secrets)
    context = browser.new_context()
    try:
        context.tracing.start(screenshots=True, snapshots=True)
        page = context.new_page()
        runner = CaseRunner(page, case, env, policy_context(env), resolver, collector)
        runner.install()
        result = runner.run(job["attempt"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.zip"
            context.tracing.stop(path=str(path))
            collector.add("trace", path.read_bytes())
    finally:
        context.close()
    return result.model_copy(update={"evidence_count": len(collector.items)}), collector


def process_one(client: RunnerClient, browser: Browser, secrets: list[SecretSource]) -> bool:
    job = client.pull()
    if job is None:
        return False
    result, collector = run_job(job, browser, secrets)
    for item in collector.items:
        client.upload(item.kind, item.sha256, item.data)
    client.report(job["job_id"], result, collector.refs(), browser.name)
    log.info("%s attempt %s: %s", job["code"], job["attempt"], result.status)
    return True


def heartbeat_loop(client: RunnerClient, stop: threading.Event, every_s: float = 10) -> None:
    while not stop.wait(every_s):
        try:
            client.heartbeat()
        except httpx.HTTPError as exc:  # pragma: no cover - network blip; lease may expire
            log.warning("heartbeat failed: %s", exc)


def main() -> None:  # pragma: no cover - process wiring; parts are tested separately
    from playwright.sync_api import sync_playwright

    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    client = RunnerClient.from_env()
    vault = Vault.from_env()
    sources: list[SecretSource] = [EnvSecrets(), *([vault] if vault else [])]
    client.heartbeat()
    stop = threading.Event()
    threading.Thread(target=heartbeat_loop, args=(client, stop), daemon=True).start()
    with sync_playwright() as pw:
        channel = os.environ.get("SAQ_BROWSER_CHANNEL") or None
        chromium = pw.chromium.launch(channel=channel, headless=True)
        browser = Browser(lambda: chromium.new_context(ignore_https_errors=False),
                          f"chromium {chromium.version}")  # fmt: skip
        try:
            while not stop.is_set():
                if not process_one(client, browser, sources):
                    stop.wait(2)
        finally:
            stop.set()
            chromium.close()
