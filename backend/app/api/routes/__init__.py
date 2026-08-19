"""Route registration for the versioned API."""

from fastapi import APIRouter

from app.api.routes import agent, audit, health, tool_calls, tools

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(tools.router)
api_router.include_router(tool_calls.router)
api_router.include_router(agent.router)
api_router.include_router(audit.router)

__all__ = ["api_router"]
