"""Execution boundary between the API and the tool layer."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Mapping

from app.logging_config import get_logger
from app.tools import ToolRegistry, build_default_registry

logger = get_logger(__name__)


class ToolGateway:
    """Resolve a tool by name and run it.

    Everything the API needs from the tool layer goes through this class, so
    routes never touch the registry or a tool directly.
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    def list_tools(self) -> list[dict[str, Any]]:
        """Return metadata for every registered tool."""
        return [tool.describe() for tool in self._registry.all()]

    def execute(
        self, tool_name: str, parameters: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        """Run a registered tool and return its result.

        Unknown names and invalid parameters surface as ``ToolError``
        subclasses raised by the registry and the tool itself.
        """
        tool = self._registry.get(tool_name)
        logger.info("Executing tool '%s'", tool_name)
        return tool.run(parameters or {})


@lru_cache
def get_tool_gateway() -> ToolGateway:
    """Return the process-wide gateway backed by the built-in tools."""
    return ToolGateway(build_default_registry())
