"""Read-only Git import (T-202): real local repositories, no network."""

from __future__ import annotations

import base64
import subprocess
from pathlib import Path

import pytest

from apps.workers import git_source
from apps.workers.git_source import GitImportError, clone, collect

GIT = [
    "git",
    "-c",
    "user.name=t",
    "-c",
    "user.email=t@example.com",
    "-c",
    "init.defaultBranch=main",
]


def make_repo(root: Path) -> Path:
    repo = root / "origin"
    (repo / "api").mkdir(parents=True)
    (repo / "node_modules").mkdir()
    (repo / "api" / "orders.py").write_text('@router.post("/orders")\ndef place(): ...\n')
    (repo / "signup.html").write_text(
        '<form action="/signup" method="post"><input name="email" required></form>\n'
    )
    (repo / "README.md").write_text("# Shop\n\nCoupons expire after 30 days.\n")
    (repo / "node_modules" / "x.js").write_text("app.get('/vendored', h)\n")
    (repo / "big.py").write_text("#" * (git_source.MAX_FILE_BYTES + 1))
    (repo / "image.png").write_bytes(b"\x89PNG")
    (repo / "leak.md").symlink_to("/etc/hosts")
    subprocess.run([*GIT, "init", "-q", str(repo)], check=True)
    subprocess.run([*GIT, "-C", str(repo), "add", "-A"], check=True)
    subprocess.run([*GIT, "-C", str(repo), "commit", "-qm", "init"], check=True)
    subprocess.run([*GIT, "-C", str(repo), "branch", "release"], check=True)
    return repo


def test_clone_and_collect(tmp_path: Path) -> None:
    origin = make_repo(tmp_path)
    commit = clone(f"file://{origin}", tmp_path / "copy", ref="release", protocols=("file",))
    assert len(commit) == 40
    files = collect(tmp_path / "copy", commit)
    assert set(files.code) == {"api/orders.py", "signup.html"}  # vendored, big, binary skipped
    # core.symlinks=false: the link is checked out as a plain file holding only its target path.
    assert files.docs["leak.md"] == "/etc/hosts" and "Coupons" in files.docs["README.md"]
    # A real symlink in a working tree is never followed.
    assert set(collect(origin, commit).docs) == {"README.md"}


def test_clone_failures_never_leak_the_token(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(GitImportError, match="Clone failed") as exc:
        clone(f"file://{tmp_path}/missing", tmp_path / "x", token="SECRET123", protocols=("file",))
    assert "SECRET123" not in str(exc.value)
    with pytest.raises(GitImportError, match="Clone failed"):  # protocol not allowed by git itself
        clone(f"file://{make_repo(tmp_path)}", tmp_path / "y", protocols=("https",))
    monkeypatch.setattr(git_source.shutil, "which", lambda _: None)
    with pytest.raises(GitImportError, match="not installed"):
        clone("https://example.com/r.git", tmp_path / "z")


def test_timeout_and_file_cap(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    origin = make_repo(tmp_path)

    def slow(*a, **k):  # type: ignore[no-untyped-def]
        raise subprocess.TimeoutExpired("git", 1)

    monkeypatch.setattr(git_source.subprocess, "run", slow)
    with pytest.raises(GitImportError, match="timed out"):
        clone(f"file://{origin}", tmp_path / "t", protocols=("file",))
    monkeypatch.undo()
    monkeypatch.setattr(git_source, "MAX_FILES", 1)
    with pytest.raises(GitImportError, match="more than 1"):
        collect(origin, "abc")


def test_token_goes_through_env_not_argv() -> None:
    env = git_source._env("tok", ("https",), "/tmp/h")
    header = env["GIT_CONFIG_VALUE_2"]
    assert env["GIT_CONFIG_KEY_2"] == "http.extraHeader"
    assert base64.b64decode(header.split()[-1]) == b"x-access-token:tok"
    assert env["GIT_ALLOW_PROTOCOL"] == "https" and env["GIT_TERMINAL_PROMPT"] == "0"
    assert "GIT_CONFIG_KEY_2" not in git_source._env(None, ("https",), "/tmp/h")
