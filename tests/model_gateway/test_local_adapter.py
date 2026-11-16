import json

import httpx
import pytest

from packages.model_gateway.local_adapter import LocalModelError, LocalProvider
from packages.model_gateway.types import ProviderCall

CALL = ProviderCall(
    system="sys",
    cached_context="graph",
    user="do it",
    effort="high",
    max_tokens=2000,
    json_schema={"type": "object"},
)


def _provider(handler, **kw) -> LocalProvider:
    client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="http://localhost:11434/v1"
    )
    return LocalProvider(
        base_url="http://localhost:11434/v1", model="qwen3:8b", client=client, **kw
    )


def _ok(content: str = '{"ok": true}', finish: str = "stop") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": "qwen3:8b",
            "choices": [
                {"message": {"role": "assistant", "content": content}, "finish_reason": finish}
            ],
            "usage": {"prompt_tokens": 120, "completion_tokens": 30},
        },
    )


def test_request_shape_is_openai_compatible_with_json_schema() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return _ok()

    _provider(handler).complete(CALL)
    body = seen["body"]
    assert seen["url"] == "http://localhost:11434/v1/chat/completions"
    assert body["model"] == "qwen3:8b"
    assert body["messages"][0] == {"role": "system", "content": "sys\n\ngraph"}
    assert body["messages"][1] == {"role": "user", "content": "do it"}
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "output", "schema": {"type": "object"}, "strict": True},
    }
    assert body["max_tokens"] == 2000 and body["temperature"] == 0


def test_response_maps_text_usage_and_stop_reason() -> None:
    res = _provider(lambda r: _ok()).complete(CALL)
    assert res.text == '{"ok": true}'
    assert res.stop_reason == "end_turn"
    assert (res.usage.input_tokens, res.usage.output_tokens) == (120, 30)
    assert res.model == "qwen3:8b"


@pytest.mark.parametrize(
    ("finish", "stop"),
    [("length", "max_tokens"), ("content_filter", "refusal"), ("tool_calls", "tool_calls")],
)
def test_finish_reasons_are_mapped(finish: str, stop: str) -> None:
    assert _provider(lambda r: _ok(finish=finish)).complete(CALL).stop_reason == stop


def test_missing_usage_and_content_are_tolerated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": None}, "finish_reason": "stop"}]}
        )

    res = _provider(handler).complete(CALL)
    assert res.text == "" and res.usage.input_tokens == 0 and res.model == "qwen3:8b"


def test_retry_feedback_is_appended_and_no_cached_context() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return _ok()

    call = CALL.model_copy(update={"cached_context": None, "retry_feedback": "fix it"})
    _provider(handler).complete(call)
    assert seen["body"]["messages"][0]["content"] == "sys"
    assert seen["body"]["messages"][1]["content"] == "do it\n\nfix it"


def test_http_errors_raise_local_model_error() -> None:
    p = _provider(lambda r: httpx.Response(500, text="boom"))
    with pytest.raises(LocalModelError, match="500"):
        p.complete(CALL)


def test_connection_errors_raise_local_model_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(LocalModelError, match="unreachable"):
        _provider(handler).complete(CALL)


def test_malformed_body_raises_local_model_error() -> None:
    with pytest.raises(LocalModelError, match="unexpected response"):
        _provider(lambda r: httpx.Response(200, json={"nope": 1})).complete(CALL)


def test_count_tokens_is_a_conservative_estimate() -> None:
    p = _provider(lambda r: _ok())
    expected = (len("sys") + len("graph") + len("do it")) // 3 + 1
    assert p.count_tokens(CALL) == expected


def test_default_client_is_created() -> None:
    p = LocalProvider(base_url="http://localhost:11434/v1/", model="m")
    assert isinstance(p.client, httpx.Client)
    assert str(p.client.base_url) == "http://localhost:11434/v1/"
