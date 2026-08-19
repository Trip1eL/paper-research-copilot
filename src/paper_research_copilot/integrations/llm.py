"""Chat model interface and OpenAI-compatible implementation."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from paper_research_copilot.integrations.openai_compatible import OpenAICompatibleTransport


class ChatProvider(Protocol):
    def complete(self, system_prompt: str, user_prompt: str) -> str: ...


class ChatTokenUsage(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class ChatCompletion(BaseModel):
    model_config = ConfigDict(frozen=True)

    content: str
    finish_reason: str | None = None
    response_model: str | None = None
    usage: ChatTokenUsage


class ObservableChatProvider(Protocol):
    def complete_with_metadata(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> ChatCompletion: ...


class OpenAICompatibleChatProvider:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        max_tokens: int = 1200,
        *,
        transport: OpenAICompatibleTransport | None = None,
    ) -> None:
        self._transport = transport or OpenAICompatibleTransport(base_url, api_key, timeout=120.0)
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        completion = self.complete_with_metadata(system_prompt, user_prompt)
        if not completion.content.strip():
            raise ValueError("Chat provider returned an empty answer")
        if completion.finish_reason == "length":
            raise ValueError("Chat provider returned a truncated answer")
        return completion.content

    def complete_with_metadata(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> ChatCompletion:
        response = self._transport.post(
            "chat/completions",
            {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0,
                "max_tokens": self._max_tokens,
            },
        )
        try:
            choice = response["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("Chat response does not contain assistant content") from exc
        if not isinstance(content, str):
            raise ValueError("Chat response assistant content must be a string")
        finish_reason = choice.get("finish_reason")
        raw_usage = response.get("usage")
        usage = raw_usage if isinstance(raw_usage, dict) else {}
        response_model = response.get("model")
        return ChatCompletion(
            content=content.strip(),
            finish_reason=finish_reason if isinstance(finish_reason, str) else None,
            response_model=response_model if isinstance(response_model, str) else None,
            usage=ChatTokenUsage(
                input_tokens=_optional_int(usage.get("prompt_tokens", usage.get("input_tokens"))),
                output_tokens=_optional_int(
                    usage.get("completion_tokens", usage.get("output_tokens"))
                ),
                total_tokens=_optional_int(usage.get("total_tokens")),
            ),
        )


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None
