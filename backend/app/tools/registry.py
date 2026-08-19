"""In-memory registry of the tools the gateway is allowed to invoke."""

from __future__ import annotations

from typing import Iterator

from app.tools.base import Tool
from app.tools.errors import DuplicateToolError, ToolNotFoundError


class ToolRegistry:
    """Name-to-tool lookup.

    The registry is the only place that knows which tools exist; the gateway
    resolves every call through it so unknown names fail in one place.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Add a tool, rejecting a name that is already taken."""
        if tool.name in self._tools:
            raise DuplicateToolError(f"A tool named '{tool.name}' is already registered.")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        """Return a registered tool or raise :class:`ToolNotFoundError`."""
        try:
            return self._tools[name]
        except KeyError:
            raise ToolNotFoundError(f"Unknown tool: '{name}'.") from None

    def names(self) -> list[str]:
        """Return registered tool names in a stable order."""
        return sorted(self._tools)

    def all(self) -> list[Tool]:
        """Return every registered tool in a stable order."""
        return [self._tools[name] for name in self.names()]

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def __iter__(self) -> Iterator[Tool]:
        return iter(self.all())
