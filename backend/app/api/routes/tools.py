"""Tool discovery endpoint."""

from fastapi import APIRouter, Depends

from app.schemas.tools import ToolListResponse
from app.services.tool_gateway import ToolGateway, get_tool_gateway

router = APIRouter(tags=["tools"])


@router.get(
    "/tools",
    response_model=ToolListResponse,
    summary="List the tools the gateway can invoke",
)
async def list_tools(
    gateway: ToolGateway = Depends(get_tool_gateway),
) -> ToolListResponse:
    """Return every registered tool with its parameter schema."""
    descriptors = gateway.list_tools()
    return ToolListResponse(count=len(descriptors), tools=descriptors)
