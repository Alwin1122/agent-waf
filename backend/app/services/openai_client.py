"""Small adapter around the official OpenAI Chat Completions API."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

from openai import OpenAI, OpenAIError

from app.config import get_settings
from app.services.agent_errors import AgentConfigurationError, OpenAIProviderError


@dataclass(frozen=True)
class ModelToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class ModelReply:
    content: str | None
    tool_calls: tuple[ModelToolCall, ...] = ()


class ChatModelClient(Protocol):
    """Provider-neutral interface consumed by the sample agent."""

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ModelReply: ...


class OpenAIChatClient:
    """Translate the OpenAI SDK response into provider-neutral models."""

    def __init__(self, client: OpenAI, *, model: str) -> None:
        self._client = client
        self._model = model

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ModelReply:
        request: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
        }
        if tools:
            request["tools"] = tools
            request["tool_choice"] = "auto"

        try:
            completion = self._client.chat.completions.create(**request)
        except OpenAIError as exc:
            raise OpenAIProviderError(
                "OpenAI could not complete the agent request."
            ) from exc
        except Exception as exc:
            raise OpenAIProviderError(
                "OpenAI returned an unexpected response."
            ) from exc

        if not completion.choices:
            raise OpenAIProviderError("OpenAI returned no response choices.")

        message = completion.choices[0].message
        tool_calls = tuple(
            ModelToolCall(
                id=tool_call.id,
                name=tool_call.function.name,
                arguments=tool_call.function.arguments,
            )
            for tool_call in (message.tool_calls or [])
        )
        return ModelReply(content=message.content, tool_calls=tool_calls)


@lru_cache
def get_openai_chat_client() -> OpenAIChatClient:
    settings = get_settings()
    if settings.openai_api_key is None:
        raise AgentConfigurationError(
            "OPENAI_API_KEY is required to use the sample agent."
        )
    client = OpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        timeout=settings.openai_timeout_seconds,
    )
    return OpenAIChatClient(client, model=settings.openai_model)
