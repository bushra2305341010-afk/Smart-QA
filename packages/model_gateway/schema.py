"""Turn a Pydantic model into a strict JSON schema for structured outputs.

Rules applied: `$ref`s inlined, every object gets `additionalProperties: false` and lists all
properties as required, and `title` / `default` keywords are dropped.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

_DROP = {"title", "default"}


def _transform(node: Any, defs: dict[str, Any]) -> Any:
    if isinstance(node, list):
        return [_transform(item, defs) for item in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        name = str(node["$ref"]).rsplit("/", 1)[-1]
        return _transform(defs[name], defs)

    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in _DROP:
            continue
        if key == "properties" and isinstance(value, dict):
            out[key] = {prop: _transform(sub, defs) for prop, sub in value.items()}
        else:
            out[key] = _transform(value, defs)
    if out.get("type") == "object":
        props = out.setdefault("properties", {})
        out["required"] = list(props)
        out["additionalProperties"] = False
    return out


def strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Return the strict JSON schema for `model`."""
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})
    result: dict[str, Any] = _transform(schema, defs)
    return result
