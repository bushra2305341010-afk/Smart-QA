"""Code facts from source files (N05, MVP): routes, forms, inputs and field limits.

Pattern-based and deterministic: every fact keeps `file:line`, so the Analyst can cite it like any
document sentence. Covered: FastAPI/Flask/Starlette decorators, Express routers, Django `path()`,
HTML forms and inputs (required, min/max length, min/max, pattern), Pydantic `Field(...)` limits.
A tree-sitter analyzer can replace this module later behind the same `extract_facts` contract.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_PY_ROUTE = re.compile(
    r"@\w+(?:\.\w+)*\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]+)['\"]", re.IGNORECASE
)
_FLASK_ROUTE = re.compile(r"@\w+(?:\.\w+)*\.route\(\s*['\"]([^'\"]+)['\"](?P<rest>[^)]*)\)")
_METHODS = re.compile(r"methods\s*=\s*\[([^\]]*)\]")
_JS_ROUTE = re.compile(r"\b(?:app|router)\.(get|post|put|patch|delete)\(\s*['\"`]([^'\"`]+)['\"`]")
_DJANGO = re.compile(r"\b(?:re_)?path\(\s*r?['\"]([^'\"]*)['\"]\s*,\s*([\w.]+)")
_FORM = re.compile(r"<form\b[^>]*>", re.IGNORECASE)
_INPUT = re.compile(r"<(input|select|textarea)\b[^>]*>", re.IGNORECASE)
_ATTR = re.compile(r"([\w-]+)\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)|\b(required)\b", re.IGNORECASE)
_PYDANTIC = re.compile(r"^\s*(\w+)\s*:\s*[^=]+=\s*Field\(([^)]*)\)")
_LIMIT_KW = re.compile(r"\b(min_length|max_length|ge|gt|le|lt|pattern)\s*=\s*([^,)]+)")
_KEEP_INPUT = ("required", "minlength", "maxlength", "min", "max", "pattern", "type")


@dataclass(frozen=True)
class CodeFact:
    kind: str  # Endpoint | Form | Field
    text: str
    path: str
    line: int

    def render(self) -> str:
        return f"{self.kind}: {self.text} ({self.path}:{self.line})"


def _attrs(tag: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, value, flag in _ATTR.findall(tag):
        if flag:
            out["required"] = "true"
        else:
            out[name.lower()] = value.strip("'\"")
    return out


def _facts_in_line(path: str, n: int, line: str) -> list[CodeFact]:
    facts: list[CodeFact] = []
    ext = path.rsplit(".", 1)[-1].lower()
    if ext == "py":
        if m := _PY_ROUTE.search(line):
            facts.append(CodeFact("Endpoint", f"{m.group(1).upper()} {m.group(2)}", path, n))
        if m := _FLASK_ROUTE.search(line):
            methods = _METHODS.search(m.group("rest"))
            names = re.findall(r"\w+", methods.group(1)) if methods else ["GET"]
            facts += [CodeFact("Endpoint", f"{x.upper()} {m.group(1)}", path, n) for x in names]
        if m := _DJANGO.search(line):
            facts.append(CodeFact("Endpoint", f"/{m.group(1)} -> {m.group(2)}", path, n))
        if m := _PYDANTIC.search(line):
            limits = ", ".join(f"{k}={v.strip()}" for k, v in _LIMIT_KW.findall(m.group(2)))
            if limits:
                facts.append(CodeFact("Field", f"{m.group(1)} ({limits})", path, n))
    elif ext in {"js", "jsx", "ts", "tsx", "mjs", "cjs"} and (m := _JS_ROUTE.search(line)):
        facts.append(CodeFact("Endpoint", f"{m.group(1).upper()} {m.group(2)}", path, n))
    if ext in {"html", "htm", "jsx", "tsx", "vue", "svelte"}:
        for tag in _FORM.findall(line):
            a = _attrs(tag)
            target = f"{a.get('method', 'GET').upper()} {a.get('action', '(same page)')}"
            facts.append(CodeFact("Form", target, path, n))
        for kind, tag in ((m.group(1).lower(), m.group(0)) for m in _INPUT.finditer(line)):
            a = _attrs(tag)
            name = a.get("name") or a.get("id")
            if name:
                rules = ", ".join(f"{k}={a[k]}" for k in _KEEP_INPUT if k in a)
                facts.append(
                    CodeFact(
                        "Field", f"{name} <{kind}>" + (f" ({rules})" if rules else ""), path, n
                    )
                )
    return facts


def extract_facts(files: dict[str, str]) -> list[CodeFact]:
    """Facts from every file, ordered by path and line."""
    facts: list[CodeFact] = []
    for path in sorted(files):
        for n, line in enumerate(files[path].splitlines(), start=1):
            facts.extend(_facts_in_line(path, n, line))
    return facts


def render_repo_text(repo: str, facts: list[CodeFact], docs: dict[str, str]) -> str:
    """The citable text of a repository source: code facts first, then its Markdown docs."""
    parts = [f"Repository {repo}", "", "## Code facts", ""]
    parts += [f.render() for f in facts] or ["(no routes, forms or fields found)"]
    for path in sorted(docs):
        parts += ["", f"## {path}", "", docs[path].strip()]
    return "\n".join(parts) + "\n"
