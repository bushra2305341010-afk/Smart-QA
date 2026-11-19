"""Pick the project's issue tracker from settings. The token comes from the environment
(`GITHUB_TOKEN`), never from the database, logs or exports."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from apps.api.settings import Settings
from packages.exporters.trackers.github import GitHubTracker, Issue


class Tracker(Protocol):
    def find_duplicates(self, title: str, limit: int = 5) -> list[Issue]: ...

    def file(self, title: str, body: str, labels: list[str]) -> Issue: ...


TrackerFactory = Callable[[dict[str, Any]], Tracker | None]


def tracker_factory(settings: Settings) -> TrackerFactory:
    def make(project_settings: dict[str, Any]) -> Tracker | None:
        conf = project_settings.get("tracker") or {}
        if conf.get("kind") != "github" or not conf.get("repo") or settings.github_token is None:
            return None
        return GitHubTracker(str(conf["repo"]), settings.github_token.get_secret_value())

    return make
