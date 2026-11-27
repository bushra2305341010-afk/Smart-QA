"""Runner-side secret resolution (T-203). Secrets never leave the runner's machine.

Jobs carry `{{secret:name}}` placeholders and identity references (`secret_ref`). They are
resolved here, from the runner's own vault, only at the moment a value is typed. Resolved values
are masked out of every console line, error message and evidence text the runner uploads.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import Protocol

PLACEHOLDER = re.compile(r"\{\{secret:([a-z0-9_]{1,40})\}\}")
MASK = "[secret]"


class SecretSource(Protocol):
    def get(self, name: str) -> str | None: ...


class EnvSecrets:
    """`SAQ_SECRET_<NAME>` environment variables of the runner process."""

    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._env = os.environ if environ is None else environ

    def get(self, name: str) -> str | None:
        return self._env.get(f"SAQ_SECRET_{name.upper()}")


class MissingSecretError(KeyError):
    pass


class Resolver:
    def __init__(self, *sources: SecretSource) -> None:
        self._sources = sources
        self.used: set[str] = set()

    def resolve(self, value: str) -> str:
        def one(m: re.Match[str]) -> str:
            name = m.group(1)
            for source in self._sources:
                found = source.get(name)
                if found is not None:
                    self.used.add(found)
                    return found
            raise MissingSecretError(name)

        return PLACEHOLDER.sub(one, value)

    def mask(self, text: str) -> str:
        for secret in sorted(self.used, key=len, reverse=True):
            if secret:
                text = text.replace(secret, MASK)
        return text
