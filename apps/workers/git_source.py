"""Read-only Git import (T-202, US-01): shallow clone, then read text files safely.

Safety rules:
- only allowed protocols (https in production; tests add `file`), never ssh/git/ext;
- shallow, single-branch, no tags, no terminal prompt, no system/global git config, symlinks
  checked out as plain files, hard timeout;
- the token goes in through git's environment config (`GIT_CONFIG_*`), so it never appears in
  the process list or in error messages;
- only regular files inside the clone are read (no symlink escapes), with size and count caps.
"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from packages.analyzers.code.repo_url import GitImportError, check_repo_url, split_ref

__all__ = ["GitImportError", "check_repo_url", "clone", "collect", "split_ref"]

CLONE_TIMEOUT_S = 120
MAX_FILE_BYTES = 512 * 1024
MAX_FILES = 3000
CODE_EXT = {"py", "js", "jsx", "ts", "tsx", "mjs", "cjs", "html", "htm", "vue", "svelte"}
DOC_EXT = {"md", "markdown"}
SKIP_DIRS = {".git", "node_modules", "dist", "build", ".venv", "venv", "__pycache__", "vendor"}


@dataclass(frozen=True)
class RepoFiles:
    commit: str
    code: dict[str, str]
    docs: dict[str, str]


def _env(token: str | None, protocols: tuple[str, ...], home: str) -> dict[str, str]:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": home,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_ALLOW_PROTOCOL": ":".join(protocols),
    }
    config = [("core.symlinks", "false"), ("protocol.allow", "user")]
    if token:
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        config.append(("http.extraHeader", f"Authorization: Basic {basic}"))
    env["GIT_CONFIG_COUNT"] = str(len(config))
    for i, (key, value) in enumerate(config):
        env[f"GIT_CONFIG_KEY_{i}"], env[f"GIT_CONFIG_VALUE_{i}"] = key, value
    return env


def clone(
    url: str,
    dest: Path,
    *,
    ref: str | None = None,
    token: str | None = None,
    protocols: tuple[str, ...] = ("https",),
    timeout_s: int = CLONE_TIMEOUT_S,
) -> str:
    """Shallow clone into `dest`; returns the commit hash."""
    git = shutil.which("git")
    if git is None:
        raise GitImportError("git is not installed on this worker")
    args = [git, "clone", "--depth", "1", "--single-branch", "--no-tags", "--quiet"]
    if ref:
        args += ["--branch", ref]
    with tempfile.TemporaryDirectory() as home:
        env = _env(token, protocols, home)
        try:
            subprocess.run(  # noqa: S603 - fixed argv, URL passed after "--"
                [*args, "--", url, str(dest)], env=env, check=True, capture_output=True,
                timeout=timeout_s,
            )  # fmt: skip
            out = subprocess.run(  # noqa: S603
                [git, "-C", str(dest), "rev-parse", "HEAD"], env=env, check=True,
                capture_output=True, text=True, timeout=30,
            )  # fmt: skip
        except subprocess.TimeoutExpired:
            raise GitImportError("Clone timed out") from None
        except subprocess.CalledProcessError as exc:
            raw = exc.stderr or b""
            reason = raw.decode(errors="replace") if isinstance(raw, bytes) else str(raw)
            if token:
                reason = reason.replace(token, "***")
            raise GitImportError(f"Clone failed: {reason.strip()[:300]}") from None
    return out.stdout.strip()


def collect(root: Path, commit: str) -> RepoFiles:
    """Readable code and Markdown files, as relative paths. Symlinks and big files are skipped."""
    base = root.resolve()
    code: dict[str, str] = {}
    docs: dict[str, str] = {}
    count = 0
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            path = Path(dirpath) / name
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            if ext not in CODE_EXT | DOC_EXT or path.is_symlink() or not path.is_file():
                continue
            if not path.resolve().is_relative_to(base) or path.stat().st_size > MAX_FILE_BYTES:
                continue
            count += 1
            if count > MAX_FILES:
                raise GitImportError(f"Repository has more than {MAX_FILES} code/doc files")
            text = path.read_text(encoding="utf-8", errors="replace")
            rel = path.relative_to(base).as_posix()
            (docs if ext in DOC_EXT else code)[rel] = text
    return RepoFiles(commit, code, docs)
