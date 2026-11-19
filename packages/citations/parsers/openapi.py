"""OpenAPI (JSON or YAML) rendered as stable, citable text: one block per operation.

    POST /orders
    Summary: Place an order
    Parameter coupon (query, optional, string): Discount code
    Request body (required): application/json
    Response 201: Order created
    Response 422: Coupon expired

The rendering is deterministic (paths and methods sorted), so offsets stay valid on re-ingest.
"""

from __future__ import annotations

import json
from typing import Any

import yaml

METHODS = ("get", "put", "post", "delete", "patch", "head", "options")


def load_openapi(text: str) -> dict[str, Any] | None:
    """The parsed document if `text` is an OpenAPI/Swagger spec, else None."""
    try:
        doc = json.loads(text)
    except ValueError:
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError:
            return None
    if isinstance(doc, dict) and ("openapi" in doc or "swagger" in doc) and "paths" in doc:
        return doc
    return None


def _param(p: dict[str, Any]) -> str:
    schema = p.get("schema") or {}
    kind = schema.get("type", p.get("type", "any"))
    need = "required" if p.get("required") else "optional"
    desc = f": {p['description']}" if p.get("description") else ""
    return f"Parameter {p.get('name', '?')} ({p.get('in', '?')}, {need}, {kind}){desc}"


_CONSTRAINTS = ("format", "minLength", "maxLength", "minimum", "maximum", "pattern", "enum")


def _body_fields(content: dict[str, Any]) -> list[str]:
    """Inline JSON body properties with their constraints (`$ref` schemas are not followed)."""
    schema = ((content.get("application/json") or {}).get("schema")) or {}
    props = schema.get("properties") if isinstance(schema, dict) else None
    if not isinstance(props, dict):
        return []
    required = set(schema.get("required") or [])
    lines = []
    for name in sorted(props):
        prop = props[name] if isinstance(props[name], dict) else {}
        parts = [str(prop.get("type", "any")), "required" if name in required else "optional"]
        parts += [f"{k} {prop[k]}" for k in _CONSTRAINTS if k in prop]
        lines.append(f"Body field {name} ({', '.join(parts)})")
    return lines


def _operation(path: str, method: str, op: dict[str, Any]) -> str:
    lines = [f"{method.upper()} {path}"]
    for label, key in (("Summary", "summary"), ("Description", "description")):
        if op.get(key):
            lines.append(f"{label}: {op[key]}")
    lines += [_param(p) for p in op.get("parameters", []) if isinstance(p, dict)]
    body = op.get("requestBody")
    if isinstance(body, dict):
        need = "required" if body.get("required") else "optional"
        content = body.get("content") or {}
        types = ", ".join(sorted(content.keys())) or "any"
        lines.append(f"Request body ({need}): {types}")
        lines += _body_fields(content)
    for code, resp in sorted((op.get("responses") or {}).items(), key=lambda kv: str(kv[0])):
        desc = resp.get("description", "") if isinstance(resp, dict) else ""
        lines.append(f"Response {code}: {desc}".rstrip())
    return "\n".join(lines)


def parse_openapi(data: bytes) -> list[str]:
    doc = load_openapi(data.decode("utf-8-sig"))
    if doc is None:
        raise ValueError("Not an OpenAPI document")
    info = doc.get("info") or {}
    blocks = [f"{info.get('title', 'API')} {info.get('version', '')}".strip()]
    if info.get("description"):
        blocks.append(str(info["description"]))
    for path in sorted(doc["paths"]):
        item = doc["paths"][path] or {}
        for method in METHODS:
            if isinstance(item.get(method), dict):
                blocks.append(_operation(path, method, item[method]))
    return ["\n\n".join(blocks)]
