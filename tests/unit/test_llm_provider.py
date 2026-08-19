from typing import Any

from paper_research_copilot.integrations import OpenAICompatibleChatProvider


class _FakeTransport:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.payload: dict[str, Any] | None = None

    def post(self, resource: str, payload: dict[str, Any]) -> dict[str, Any]:
        assert resource == "chat/completions"
        self.payload = payload
        return self.response


def test_chat_provider_exposes_model_and_openai_usage_fields() -> None:
    transport = _FakeTransport(
        {
            "model": "gpt-5.5-2026-08-01",
            "choices": [{"message": {"content": "structured answer"}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 34,
                "total_tokens": 154,
            },
        }
    )
    provider = OpenAICompatibleChatProvider(
        "https://relay.example/v1",
        "secret",
        "gpt-5.5",
        max_tokens=4000,
        transport=transport,  # type: ignore[arg-type]
    )

    completion = provider.complete_with_metadata("system", "user")

    assert completion.content == "structured answer"
    assert completion.finish_reason == "stop"
    assert completion.response_model == "gpt-5.5-2026-08-01"
    assert completion.usage.input_tokens == 120
    assert completion.usage.output_tokens == 34
    assert completion.usage.total_tokens == 154
    assert transport.payload is not None
    assert transport.payload["max_tokens"] == 4000


def test_chat_provider_accepts_responses_api_usage_field_names() -> None:
    provider = OpenAICompatibleChatProvider(
        "https://relay.example",
        "secret",
        "gpt-5.5",
        transport=_FakeTransport(
            {
                "choices": [{"message": {"content": "answer"}}],
                "usage": {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
            }
        ),  # type: ignore[arg-type]
    )

    completion = provider.complete_with_metadata("system", "user")

    assert completion.usage.input_tokens == 11
    assert completion.usage.output_tokens == 7
