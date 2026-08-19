"""Protected tools reachable through the gateway.

Tools are plain classes with no knowledge of HTTP; the API layer talks to them
only through :class:`~app.tools.registry.ToolRegistry`.
"""

from app.tools.base import Tool
from app.tools.create_order import CreateOrderTool
from app.tools.errors import (
    DuplicateToolError,
    ToolError,
    ToolExecutionError,
    ToolInputError,
    ToolNotFoundError,
)
from app.tools.get_customer import GetCustomerTool
from app.tools.registry import ToolRegistry
from app.tools.search_products import SearchProductsTool


def build_default_registry() -> ToolRegistry:
    """Return a registry populated with the built-in tools."""
    registry = ToolRegistry()
    registry.register(SearchProductsTool())
    registry.register(GetCustomerTool())
    registry.register(CreateOrderTool())
    return registry


__all__ = [
    "CreateOrderTool",
    "DuplicateToolError",
    "GetCustomerTool",
    "SearchProductsTool",
    "Tool",
    "ToolError",
    "ToolExecutionError",
    "ToolInputError",
    "ToolNotFoundError",
    "ToolRegistry",
    "build_default_registry",
]
