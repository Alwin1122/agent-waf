"""Customer record lookup."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from app.schemas.common import StrictModel
from app.tools.base import Tool
from app.tools.data import CUSTOMERS
from app.tools.errors import ToolExecutionError


class GetCustomerParameters(StrictModel):
    """Parameters accepted by ``get_customer``."""

    customer_id: str = Field(min_length=1, max_length=64)


class GetCustomerTool(Tool):
    """Return a single customer record by identifier."""

    name = "get_customer"
    description = "Fetch a customer record by its identifier."
    parameters_model = GetCustomerParameters

    def execute(self, parameters: GetCustomerParameters) -> dict[str, Any]:
        customer = CUSTOMERS.get(parameters.customer_id)
        if customer is None:
            raise ToolExecutionError(
                f"No customer found with id '{parameters.customer_id}'.",
                code="customer_not_found",
                status_code=404,
            )
        return {"customer": dict(customer)}
