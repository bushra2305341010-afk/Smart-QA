from types import SimpleNamespace

from packages.model_gateway.anthropic_adapter import FALLBACK_BETA, AnthropicProvider
from packages.model_gateway.types import ProviderCall


class FakeMessages:
    def __init__(self, response: SimpleNamespace) -> None:
        self.response = response
        self.kwargs: dict = {}

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.kwargs = kwargs
        return self.response


class FakeCount:
    def __init__(self) -> None:
        self.kwargs: dict = {}

    def count_tokens(self, **kwargs: object) -> SimpleNamespace:
        self.kwargs = kwargs
        return SimpleNamespace(input_tokens=1234)


def _response(stop_reason: str = "end_turn", category: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        model="claude-opus-5-5",
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category=category) if category else None,
        content=[
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text='{"ok": true}'),
        ],
        usage=SimpleNamespace(
            input_tokens=10,
            output_tokens=5,
            cache_read_input_tokens=7,
            cache_creation_input_tokens=None,
        ),
    )


def _client(resp: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages(resp)), messages=FakeCount())


CALL = ProviderCall(
    system="sys",
    cached_context="graph",
    user="do it",
    effort="high",
    max_tokens=16000,
    json_schema={"type": "object"},
)


def test_request_shape_uses_structured_output_effort_cache_and_fallbacks() -> None:
    client = _client(_response())
    AnthropicProvider(client=client, model="claude-opus-5-5").complete(CALL)
    kw = client.beta.messages.kwargs
    assert kw["model"] == "claude-opus-5-5"
    assert kw["output_config"] == {
        "effort": "high",
        "format": {"type": "json_schema", "schema": {"type": "object"}},
    }
    assert kw["system"][0] == {"type": "text", "text": "sys"}
    assert kw["system"][1]["cache_control"] == {"type": "ephemeral"}
    assert kw["fallbacks"] == "default" and kw["betas"] == [FALLBACK_BETA]
    assert kw["messages"] == [{"role": "user", "content": "do it"}]


def test_response_text_skips_thinking_and_maps_usage() -> None:
    res = AnthropicProvider(client=_client(_response()), model="claude-opus-5-5").complete(CALL)
    assert res.text == '{"ok": true}'
    assert res.usage.cache_read_input_tokens == 7 and res.usage.cache_creation_input_tokens == 0


def test_refusal_category_is_exposed() -> None:
    res = AnthropicProvider(client=_client(_response("refusal", "cyber")), model="m").complete(CALL)
    assert res.stop_reason == "refusal" and res.refusal_category == "cyber"


def test_no_cached_context_and_retry_feedback_message() -> None:
    client = _client(_response())
    call = CALL.model_copy(update={"cached_context": None, "retry_feedback": "fix it"})
    AnthropicProvider(client=client, model="m", fallbacks=False).complete(call)
    kw = client.beta.messages.kwargs
    assert len(kw["system"]) == 1
    assert "fallbacks" not in kw and "betas" not in kw
    assert kw["messages"][-1] == {"role": "user", "content": "do it\n\nfix it"}


def test_count_tokens() -> None:
    client = _client(_response())
    assert AnthropicProvider(client=client, model="m").count_tokens(CALL) == 1234
    assert client.messages.kwargs["model"] == "m"


def test_default_client_is_the_official_sdk(monkeypatch) -> None:
    import anthropic

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used")
    provider = AnthropicProvider()
    assert isinstance(provider.client, anthropic.Anthropic)
    assert provider.model == "claude-opus-5-5"
