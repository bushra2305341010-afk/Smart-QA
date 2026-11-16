from pydantic import BaseModel

from packages.model_gateway.schema import strict_json_schema


class Inner(BaseModel):
    value: int


class Outer(BaseModel):
    name: str
    tags: list[str]
    inner: Inner
    note: str | None = None


def _objects(node: object) -> list[dict]:
    found: list[dict] = []
    if isinstance(node, dict):
        if node.get("type") == "object":
            found.append(node)
        for v in node.values():
            found.extend(_objects(v))
    elif isinstance(node, list):
        for v in node:
            found.extend(_objects(v))
    return found


def test_every_object_forbids_extra_properties_and_requires_all() -> None:
    schema = strict_json_schema(Outer)
    objs = _objects(schema)
    assert len(objs) >= 2
    for obj in objs:
        assert obj["additionalProperties"] is False
        assert set(obj["required"]) == set(obj["properties"])


def test_titles_and_defaults_are_stripped() -> None:
    text = str(strict_json_schema(Outer))
    assert "'title'" not in text
    assert "'default'" not in text
