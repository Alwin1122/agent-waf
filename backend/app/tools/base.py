"""Common interface implemented by every protected tool."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Mapping

from pydantic import ValidationError

from app.schemas.common import StrictModel
from app.tools.errors import ToolInputError


class Tool(ABC):
    """A single callable capability exposed through the gateway.

    Subclasses declare a name, a description and a Pydantic model describing
    their parameters. Validation is handled here so every tool rejects bad
    input identically.
    """

    name: ClassVar[str]
    description: ClassVar[str]
    parameters_model: ClassVar[type[StrictModel]]

    def run(self, parameters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Validate parameters and execute the tool."""
        return self.execute(self.validate(parameters or {}))

    def validate(self, parameters: Mapping[str, Any]) -> StrictModel:
        """Coerce raw parameters into the tool's parameter model."""
        try:
            return self.parameters_model.model_validate(dict(parameters))
        except ValidationError as exc:
            raise ToolInputError(
                f"Invalid parameters for tool '{self.name}'.",
                details=[
                    {
                        "location": ".".join(
                            str(part) for part in ("parameters", *error["loc"])
                        ),
                        "message": str(error["msg"]),
                        "type": str(error["type"]),
                    }
                    for error in exc.errors()
                ],
            ) from exc

    @abstractmethod
    def execute(self, parameters: Any) -> dict[str, Any]:
        """Perform the tool's work against already validated parameters."""

    def describe(self) -> dict[str, Any]:
        """Return the tool's public metadata for discovery endpoints."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters_model.model_json_schema(),
        }
