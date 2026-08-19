"""Unit tests for the tool layer: tools, registry and gateway."""

from __future__ import annotations

import pytest

from app.services.tool_gateway import ToolGateway
from app.tools import (
    CreateOrderTool,
    DuplicateToolError,
    GetCustomerTool,
    SearchProductsTool,
    ToolExecutionError,
    ToolInputError,
    ToolNotFoundError,
    ToolRegistry,
    build_default_registry,
)


@pytest.fixture
def registry() -> ToolRegistry:
    return build_default_registry()


@pytest.fixture
def gateway(registry: ToolRegistry) -> ToolGateway:
    return ToolGateway(registry)


class TestRegistry:
    def test_default_registry_holds_the_built_in_tools(
        self, registry: ToolRegistry
    ) -> None:
        assert registry.names() == ["create_order", "get_customer", "search_products"]
        assert len(registry) == 3

    def test_registered_tool_can_be_resolved(self, registry: ToolRegistry) -> None:
        assert isinstance(registry.get("search_products"), SearchProductsTool)
        assert "get_customer" in registry

    def test_registering_a_duplicate_name_is_rejected(self) -> None:
        registry = ToolRegistry()
        registry.register(GetCustomerTool())

        with pytest.raises(DuplicateToolError):
            registry.register(GetCustomerTool())

    def test_resolving_an_unknown_tool_raises(self, registry: ToolRegistry) -> None:
        with pytest.raises(ToolNotFoundError):
            registry.get("no_such_tool")


class TestSearchProducts:
    def test_query_matches_name_and_category(self) -> None:
        result = SearchProductsTool().run({"query": "laptop"})

        assert result["count"] == 2
        assert [product["product_id"] for product in result["products"]] == [
            "p-1001",
            "p-1002",
        ]

    def test_max_price_filters_results(self) -> None:
        result = SearchProductsTool().run({"query": "laptop", "max_price": 1500})

        assert [product["product_id"] for product in result["products"]] == ["p-1001"]

    def test_query_is_case_insensitive(self) -> None:
        assert SearchProductsTool().run({"query": "NIMBUS"})["count"] == 2

    def test_no_match_returns_an_empty_list(self) -> None:
        result = SearchProductsTool().run({"query": "spaceship"})

        assert result == {
            "query": "spaceship",
            "max_price": None,
            "count": 0,
            "products": [],
        }

    def test_missing_query_is_rejected(self) -> None:
        with pytest.raises(ToolInputError):
            SearchProductsTool().run({})


class TestGetCustomer:
    def test_known_customer_is_returned(self) -> None:
        result = GetCustomerTool().run({"customer_id": "c-002"})

        assert result["customer"]["name"] == "Grace Hopper"
        assert result["customer"]["email"] == "grace@example.com"

    def test_unknown_customer_raises_a_controlled_error(self) -> None:
        with pytest.raises(ToolExecutionError) as excinfo:
            GetCustomerTool().run({"customer_id": "c-404"})

        assert excinfo.value.code == "customer_not_found"
        assert excinfo.value.status_code == 404

    def test_unexpected_parameter_is_rejected(self) -> None:
        with pytest.raises(ToolInputError):
            GetCustomerTool().run({"customer_id": "c-001", "sneaky": True})


class TestCreateOrder:
    def test_order_is_created_with_a_computed_total(self) -> None:
        result = CreateOrderTool().run(
            {"customer_id": "c-001", "product_id": "p-1003", "quantity": 4}
        )

        order = result["order"]
        assert order["total_price"] == 198.00
        assert order["status"] == "created"
        assert order["order_id"].startswith("ord-")

    def test_identical_input_produces_an_identical_order_id(self) -> None:
        parameters = {"customer_id": "c-001", "product_id": "p-1003", "quantity": 1}

        first = CreateOrderTool().run(parameters)["order"]["order_id"]
        second = CreateOrderTool().run(parameters)["order"]["order_id"]

        assert first == second

    @pytest.mark.parametrize("quantity", [0, -3, 101])
    def test_quantity_outside_the_allowed_range_is_rejected(
        self, quantity: int
    ) -> None:
        with pytest.raises(ToolInputError):
            CreateOrderTool().run(
                {"customer_id": "c-001", "product_id": "p-1003", "quantity": quantity}
            )

    def test_unknown_customer_is_rejected(self) -> None:
        with pytest.raises(ToolExecutionError) as excinfo:
            CreateOrderTool().run(
                {"customer_id": "c-404", "product_id": "p-1003", "quantity": 1}
            )

        assert excinfo.value.code == "customer_not_found"

    def test_unknown_product_is_rejected(self) -> None:
        with pytest.raises(ToolExecutionError) as excinfo:
            CreateOrderTool().run(
                {"customer_id": "c-001", "product_id": "p-9999", "quantity": 1}
            )

        assert excinfo.value.code == "product_not_found"

    def test_out_of_stock_product_is_rejected(self) -> None:
        with pytest.raises(ToolExecutionError) as excinfo:
            CreateOrderTool().run(
                {"customer_id": "c-001", "product_id": "p-1004", "quantity": 1}
            )

        assert excinfo.value.code == "product_out_of_stock"
        assert excinfo.value.status_code == 409


class TestGateway:
    def test_execute_runs_the_named_tool(self, gateway: ToolGateway) -> None:
        result = gateway.execute("get_customer", {"customer_id": "c-003"})

        assert result["customer"]["customer_id"] == "c-003"

    def test_execute_rejects_an_unknown_tool(self, gateway: ToolGateway) -> None:
        with pytest.raises(ToolNotFoundError) as excinfo:
            gateway.execute("drop_database", {})

        assert excinfo.value.status_code == 404
        assert excinfo.value.code == "tool_not_found"

    def test_execute_propagates_tool_input_errors(self, gateway: ToolGateway) -> None:
        with pytest.raises(ToolInputError):
            gateway.execute("search_products", {"query": ""})

    def test_list_tools_describes_each_tool(self, gateway: ToolGateway) -> None:
        descriptors = gateway.list_tools()

        assert [descriptor["name"] for descriptor in descriptors] == [
            "create_order",
            "get_customer",
            "search_products",
        ]
        assert all(descriptor["parameters"]["type"] == "object" for descriptor in descriptors)

    def test_gateway_only_exposes_tools_from_its_registry(self) -> None:
        registry = ToolRegistry()
        registry.register(SearchProductsTool())

        gateway = ToolGateway(registry)

        assert [descriptor["name"] for descriptor in gateway.list_tools()] == [
            "search_products"
        ]
        with pytest.raises(ToolNotFoundError):
            gateway.execute("get_customer", {"customer_id": "c-001"})
