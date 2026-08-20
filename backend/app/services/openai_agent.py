"""Sample OpenAI agent orchestrating only through the protected tool path."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from fastapi import Depends

from app.schemas.tool_calls import ToolCallRequest
from app.services.agent_errors import (
    AgentToolExecutionError,
    AgentWAFBlockedError,
    InvalidModelToolCallError,
    OpenAIProviderError,
)
from app.services.openai_client import (
    ChatModelClient,
    ModelReply,
    ModelToolCall,
    get_openai_chat_client,
)
from app.services.protected_tools import (
    ProtectedToolCaller,
    get_protected_tool_service,
)
from app.tools.errors import ToolError

SYSTEM_PROMPT = (
    "You are a shopping assistant. Use only the supplied tools when product, "
    "customer, or order data is needed. Never claim a tool succeeded unless a "
    "tool result is present. After receiving a tool result, answer the user "
    "clearly and concisely."
)


@dataclass(frozen=True)
class AgentChatResult:
    response: str
    tool: str | None = None
    tool_result: dict[str, Any] | None = None


class OpenAIAgentService:
    """Coordinate OpenAI while delegating every tool call to WAF protection."""

    def __init__(
        self,
        model: ChatModelClient,
        protected_tools: ProtectedToolCaller,
    ) -> None:
        self._model = model
        self._protected_tools = protected_tools

    def chat(
        self,
        *,
        user_id: str,
        agent_id: str,
        session_id: str,
        message: str,
    ) -> AgentChatResult:
        descriptors = self._protected_tools.list_tools()
        available_names = {descriptor["name"] for descriptor in descriptors}
        openai_tools = [_to_openai_tool(descriptor) for descriptor in descriptors]
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ]

        initial = self._model.complete(messages, openai_tools)
        if not initial.tool_calls:
            return AgentChatResult(response=_required_content(initial))
        if len(initial.tool_calls) != 1:
            raise InvalidModelToolCallError(
                "The model returned multiple tool calls; exactly one is supported."
            )

        model_call = initial.tool_calls[0]
        if model_call.name not in available_names:
            raise InvalidModelToolCallError(
                "The model selected a tool that is not registered."
            )
        parameters = _parse_arguments(model_call)

        try:
            outcome = self._protected_tools.execute(
                ToolCallRequest(
                    user_id=user_id,
                    agent_id=agent_id,
                    session_id=session_id,
                    tool=model_call.name,
                    parameters=parameters,
                )
            )
        except ToolError as exc:
            raise AgentToolExecutionError(
                f"Protected tool execution failed: {exc.message}"
            ) from exc

        if not outcome.allowed:
            raise AgentWAFBlockedError(outcome.decision)
        if outcome.result is None:
            raise AgentToolExecutionError(
                "The protected tool returned no result."
            )

        messages.extend(
            [
                _assistant_tool_call_message(initial, model_call),
                {
                    "role": "tool",
                    "tool_call_id": model_call.id,
                    "content": json.dumps(
                        outcome.result,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                },
            ]
        )
        final = self._model.complete(messages)
        if final.tool_calls:
            raise InvalidModelToolCallError(
                "The model attempted another tool call instead of a final response."
            )
        return AgentChatResult(
            response=_required_content(final),
            tool=model_call.name,
            tool_result=outcome.result,
        )


def _to_openai_tool(descriptor: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": descriptor["name"],
            "description": descriptor["description"],
            "parameters": descriptor["parameters"],
        },
    }


def _parse_arguments(tool_call: ModelToolCall) -> dict[str, Any]:
    try:
        parameters = json.loads(tool_call.arguments)
    except (TypeError, json.JSONDecodeError) as exc:
        raise InvalidModelToolCallError(
            "The model returned malformed JSON tool arguments."
        ) from exc
    if not isinstance(parameters, dict):
        raise InvalidModelToolCallError(
            "The model's tool arguments must be a JSON object."
        )
    return parameters


def _assistant_tool_call_message(
    reply: ModelReply, tool_call: ModelToolCall
) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": reply.content,
        "tool_calls": [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.name,
                    "arguments": tool_call.arguments,
                },
            }
        ],
    }


def _required_content(reply: ModelReply) -> str:
    content = (reply.content or "").strip()
    if not content:
        raise OpenAIProviderError("OpenAI returned an empty response.")
    return content


def get_openai_agent_service(
    model: ChatModelClient = Depends(get_openai_chat_client),
    protected_tools: ProtectedToolCaller = Depends(get_protected_tool_service),
) -> OpenAIAgentService:
    return OpenAIAgentService(model, protected_tools)
