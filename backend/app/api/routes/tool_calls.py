"""Tool call ingress endpoint.

The route only translates HTTP to and from the gateway; resolving and running
a tool is the gateway's job.
"""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.logging_config import get_logger
from app.rules.models import WAFBlockResponse
from app.schemas.common import ErrorResponse
from app.schemas.tool_calls import ToolCallRequest, ToolCallResponse
from app.services.protected_tools import (
    ProtectedToolService,
    get_protected_tool_service,
)

logger = get_logger(__name__)
router = APIRouter(tags=["tool-calls"])


@router.post(
    "/tool-calls",
    response_model=ToolCallResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute a tool through the gateway",
    responses={
        status.HTTP_403_FORBIDDEN: {"model": WAFBlockResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def submit_tool_call(
    request: ToolCallRequest,
    protected_tools: ProtectedToolService = Depends(get_protected_tool_service),
) -> ToolCallResponse | JSONResponse:
    """Inspect the call with the WAF, then run an allowed tool.

    Only identifiers are logged; parameter values may carry sensitive data and
    are deliberately excluded.
    """
    logger.info(
        "Tool call received: agent_id=%s session_id=%s tool=%s",
        request.agent_id,
        request.session_id,
        request.tool,
    )

    outcome = protected_tools.execute(request)
    if not outcome.allowed:
        blocked = outcome.decision.blocked_by
        assert blocked is not None
        payload = WAFBlockResponse(rule=blocked.rule, reason=blocked.reason)
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=payload.model_dump(mode="json"),
        )

    assert outcome.result is not None
    return ToolCallResponse(
        status="success",
        tool=request.tool,
        result=outcome.result,
    )
