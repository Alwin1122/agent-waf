"""Mock order creation."""

from __future__ import annotations

import hashlib
from typing import Any

from pydantic import Field

from app.schemas.common import StrictModel
from app.tools.base import Tool
from app.tools.data import CUSTOMERS, PRODUCTS
from app.tools.errors import ToolExecutionError

MAX_QUANTITY = 100


class CreateOrderParameters(StrictModel):
    """Parameters accepted by ``create_order``."""

    customer_id: str = Field(min_length=1, max_length=64)
    product_id: str = Field(min_length=1, max_length=64)
    quantity: int = Field(ge=1, le=MAX_QUANTITY)


class CreateOrderTool(Tool):
    """Create an order for a known customer and product.

    No order is persisted; the identifier is derived from the inputs so the
    same request always yields the same order.
    """

    name = "create_order"
    description = "Create an order for a customer and a catalogue product."
    parameters_model = CreateOrderParameters

    def execute(self, parameters: CreateOrderParameters) -> dict[str, Any]:
        if parameters.customer_id not in CUSTOMERS:
            raise ToolExecutionError(
                f"No customer found with id '{parameters.customer_id}'.",
                code="customer_not_found",
                status_code=404,
            )

        product = PRODUCTS.get(parameters.product_id)
        if product is None:
            raise ToolExecutionError(
                f"No product found with id '{parameters.product_id}'.",
                code="product_not_found",
                status_code=404,
            )

        if not product["in_stock"]:
            raise ToolExecutionError(
                f"Product '{parameters.product_id}' is out of stock.",
                code="product_out_of_stock",
                status_code=409,
            )

        return {
            "order": {
                "order_id": _order_id(parameters),
                "customer_id": parameters.customer_id,
                "product_id": parameters.product_id,
                "quantity": parameters.quantity,
                "unit_price": product["price"],
                "total_price": round(product["price"] * parameters.quantity, 2),
                "status": "created",
            }
        }


def _order_id(parameters: CreateOrderParameters) -> str:
    digest = hashlib.sha256(
        f"{parameters.customer_id}:{parameters.product_id}:{parameters.quantity}".encode()
    ).hexdigest()
    return f"ord-{digest[:12]}"
