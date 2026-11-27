"""UI explorer (F04, M09c): breadth-first crawl of the running app, read-only.

It only *navigates* (GET) to links inside the environment's allowed hosts, every navigation
checked by the safe-action policy, and never clicks buttons, submits forms or types: actions
are recorded by name so reviewers see them, not performed. At most `budget` page visits
(docs/08: 150). CAPTCHA / login walls stop that branch. Page text is data, never instructions.
"""

from __future__ import annotations

from collections import deque
from typing import Any
from urllib.parse import urldefrag, urljoin, urlsplit

from playwright.sync_api import Error as PlaywrightError

from apps.runner.detectors import PageSnapshot, detect
from packages.contracts.explore import Exploration, ObservedField, ObservedScreen
from packages.policy.actions import Action, PolicyContext, check

BUDGET = 150
SCAN_JS = """() => {
  const text = el => (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ');
  const labelOf = el => {
    if (el.labels && el.labels.length) {
      const copy = el.labels[0].cloneNode(true);
      copy.querySelectorAll('input, select, textarea').forEach(c => c.remove());
      return (copy.textContent || '').trim().replace(/\\s+/g, ' ');
    }
    return el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.name || '';
  };
  const fields = [...document.querySelectorAll('input, select, textarea')]
    .filter(el => !['hidden', 'submit', 'button', 'reset', 'image'].includes(el.type))
    .map(el => ({
      label: labelOf(el).slice(0, 200), input_type: el.tagName === 'SELECT' ? 'select'
        : (el.tagName === 'TEXTAREA' ? 'textarea' : (el.type || 'text')),
      required: !!el.required, min: el.getAttribute('min'), max: el.getAttribute('max'),
      max_length: el.maxLength > 0 ? el.maxLength : null,
      options: el.tagName === 'SELECT' ? [...el.options].map(o => text(o)).slice(0, 50) : [],
    })).filter(f => f.label);
  const actions = [...document.querySelectorAll('button, input[type=submit], [role=button]')]
    .map(el => (el.getAttribute('aria-label') || text(el) || el.value || '').slice(0, 100))
    .filter(Boolean);
  return {
    title: document.title,
    headings: [...document.querySelectorAll('h1, h2')].map(text).slice(0, 20),
    fields, actions, links: [...document.querySelectorAll('a[href]')].map(a => a.href),
    text: (document.body ? document.body.innerText : '').slice(0, 5000),
    otp: !!document.querySelector('input[autocomplete="one-time-code"]'),
    password: !!document.querySelector('input[type="password"]'),
  };
}"""


def _path(url: str) -> str:
    parts = urlsplit(url)
    return (parts.path or "/") + (f"?{parts.query}" if parts.query else "")


def explore(
    page: Any,
    policy: PolicyContext,
    start: str = "/",
    *,
    budget: int = BUDGET,
    timeout_ms: int = 10_000,
) -> Exploration:
    base = policy.base_url.rstrip("/")
    queue: deque[str] = deque([urljoin(base + "/", start.lstrip("/"))])
    seen: set[str] = set()
    out = Exploration(base_url=base)
    screens: list[ObservedScreen] = []
    blocked: list[str] = []
    steps = 0
    while queue:
        url = urldefrag(queue.popleft())[0]
        if url in seen:
            continue
        seen.add(url)
        decision = check(Action(kind="navigate", url=url), policy)
        if not decision.allowed:
            blocked.append(f"{url}: {decision.reason}")
            continue
        if steps >= budget:
            out.budget_exhausted = True
            break
        steps += 1
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        except PlaywrightError as exc:
            blocked.append(f"{url}: {str(exc).splitlines()[0][:200]}")
            continue
        if resp is not None and resp.status >= 400:
            blocked.append(f"{url}: HTTP {resp.status}")
            continue
        scan = page.evaluate(SCAN_JS)
        wall = detect(
            PageSnapshot(
                url=page.url,
                title=scan["title"],
                text=scan["text"],
                frame_urls=[f.url for f in page.frames],
                has_otp_input=scan["otp"],
                has_password_input=False,
            )
        )
        if wall is not None:
            blocked.append(f"{url}: {wall.reason}")
            continue
        links = []
        for href in scan["links"]:
            target = urldefrag(href)[0]
            if target.startswith(("http://", "https://")):
                links.append(target)
                if target not in seen:
                    queue.append(target)
        screens.append(
            ObservedScreen(
                path=_path(page.url),
                title=scan["title"][:200],
                headings=scan["headings"],
                fields=[ObservedField.model_validate(f) for f in scan["fields"]][:100],
                actions=list(dict.fromkeys(scan["actions"]))[:100],
                links=sorted({_path(u) for u in links if u.startswith(base)})[:200],
            )
        )
    out.screens, out.blocked, out.steps = screens, blocked, steps
    return out


def submit(client: Any, env_id: str, result: Exploration) -> dict[str, Any]:
    body = {"env_id": env_id, "exploration": result.model_dump(mode="json")}
    resp = client.http.post("/runner/explorations", json=body)
    resp.raise_for_status()
    return dict(resp.json())


def main() -> None:  # pragma: no cover - process wiring; explore/submit are tested
    """`uv run python -m apps.runner.explorer --env env_... [--start /] [--budget 150]`"""
    import argparse
    import os

    from playwright.sync_api import sync_playwright

    from apps.runner.main import RunnerClient
    from apps.runner.policy_hook import policy_context

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", help="env_... (default: first non-production environment)")
    parser.add_argument("--start", default="/")
    parser.add_argument("--budget", type=int, default=BUDGET)
    args = parser.parse_args()
    client = RunnerClient.from_env()
    envs = client.http.get("/runner/environments").json()
    env = (
        next((e for e in envs if e["id"] == args.env), None)
        if args.env
        else next((e for e in envs if e["kind"] != "production"), None)
    )
    if env is None:
        raise SystemExit("No matching environment")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel=os.environ.get("SAQ_BROWSER_CHANNEL") or None)
        page = browser.new_context().new_page()
        result = explore(page, policy_context(env), args.start, budget=args.budget)
        browser.close()
    print(submit(client, env["id"], result))
    for line in result.blocked:
        print("blocked", line)


if __name__ == "__main__":  # pragma: no cover
    main()
