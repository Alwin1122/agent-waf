"""Product catalogue search."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from app.schemas.common import StrictModel
from app.tools.base import Tool
from app.tools.data import PRODUCTS


class SearchProductsParameters(StrictModel):
    """Parameters accepted by ``search_products``."""

    query: str = Field(min_length=1, max_length=128)
    max_price: float | None = Field(default=None, gt=0)


class SearchProductsTool(Tool):
    """Return catalogue entries matching a free-text query."""

    name = "search_products"
    description = "Search the product catalogue by name or category."
    parameters_model = SearchProductsParameters

    def execute(self, parameters: SearchProductsParameters) -> dict[str, Any]:
        needle = parameters.query.casefold()
        matches: list[dict[str, Any]] = []
        for product in PRODUCTS.values():
            haystack = f"{product['name']} {product['category']}".casefold()
            if needle not in haystack:
                continue
            if parameters.max_price is not None and product["price"] > parameters.max_price:
                continue
            matches.append(dict(product))
        matches.sort(key=lambda product: product["product_id"])
        return {
            "query": parameters.query,
            "max_price": parameters.max_price,
            "count": len(matches),
            "products": matches,
        }
