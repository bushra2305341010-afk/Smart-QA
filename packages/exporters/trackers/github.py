"""GitHub Issues adapter: duplicate search before filing (US-08) and issue creation.

The token is read from the environment by the caller and never stored or logged.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

API = "https://api.github.com"


class TrackerError(Exception):
    pass


@dataclass(frozen=True)
class Issue:
    number: int
    title: str
    url: str


class GitHubTracker:
    def __init__(self, repo: str, token: str, client: httpx.Client | None = None) -> None:
        if repo.count("/") != 1:
            raise ValueError("repo must be 'owner/name'")
        self.repo = repo
        self._client = client or httpx.Client(base_url=API, timeout=15)
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _check(self, res: httpx.Response) -> httpx.Response:
        if res.status_code >= 400:
            raise TrackerError(f"GitHub {res.status_code}: {res.text[:200]}")
        return res

    def find_duplicates(self, title: str, limit: int = 5) -> list[Issue]:
        """Open issues whose title shares the words of `title` (GitHub search)."""
        words = " ".join(w for w in title.replace('"', " ").split() if len(w) > 2)[:200]
        query = f"repo:{self.repo} is:issue is:open in:title {words}"
        res = self._check(
            self._client.get(
                "/search/issues", params={"q": query, "per_page": limit}, headers=self._headers
            )
        )
        return [Issue(i["number"], i["title"], i["html_url"]) for i in res.json().get("items", [])]

    def file(self, title: str, body: str, labels: list[str]) -> Issue:
        res = self._check(
            self._client.post(
                f"/repos/{self.repo}/issues",
                json={"title": title, "body": body, "labels": labels},
                headers=self._headers,
            )
        )
        data = res.json()
        return Issue(data["number"], data["title"], data["html_url"])
