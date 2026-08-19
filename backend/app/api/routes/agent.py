"""HTTP endpoint for the sample OpenAI-powered shopping agent."""

from fastapi import APIRouter, Depends, status

from app.schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    AgentErrorResponse,
    AgentWAFBlockResponse,
)
from app.services.openai_agent import OpenAIAgentService, get_openai_agent_service

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post(
    "/chat",
    response_model=AgentChatResponse,
    summary="Chat with the protected OpenAI shopping agent",
    responses={
        status.HTTP_403_FORBIDDEN: {"model": AgentWAFBlockResponse},
        status.HTTP_502_BAD_GATEWAY: {"model": AgentErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": AgentErrorResponse},
    },
)
def chat(
    request: AgentChatRequest,
    agent: OpenAIAgentService = Depends(get_openai_agent_service),
) -> AgentChatResponse:
    """Let OpenAI choose a tool, but execute it only through Agent WAF."""
    result = agent.chat(
        agent_id=request.agent_id,
        session_id=request.session_id,
        message=request.message,
    )
    return AgentChatResponse(
        response=result.response,
        tool=result.tool,
        tool_result=result.tool_result,
    )
