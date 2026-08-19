"""Fixed in-memory records backing the mock tools.

The dataset is a module-level constant and is never mutated, so repeated tool
calls always return the same results.
"""

from __future__ import annotations

from typing import Any

PRODUCTS: dict[str, dict[str, Any]] = {
    "p-1001": {
        "product_id": "p-1001",
        "name": "Aurora 14 Laptop",
        "category": "laptops",
        "price": 1299.00,
        "in_stock": True,
    },
    "p-1002": {
        "product_id": "p-1002",
        "name": "Aurora 16 Laptop Pro",
        "category": "laptops",
        "price": 2199.00,
        "in_stock": True,
    },
    "p-1003": {
        "product_id": "p-1003",
        "name": "Nimbus Wireless Mouse",
        "category": "accessories",
        "price": 49.50,
        "in_stock": True,
    },
    "p-1004": {
        "product_id": "p-1004",
        "name": "Nimbus Mechanical Keyboard",
        "category": "accessories",
        "price": 129.00,
        "in_stock": False,
    },
    "p-1005": {
        "product_id": "p-1005",
        "name": "Halo 27 Monitor",
        "category": "displays",
        "price": 399.00,
        "in_stock": True,
    },
}

CUSTOMERS: dict[str, dict[str, Any]] = {
    "c-001": {
        "customer_id": "c-001",
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "tier": "gold",
        "country": "GB",
    },
    "c-002": {
        "customer_id": "c-002",
        "name": "Grace Hopper",
        "email": "grace@example.com",
        "tier": "silver",
        "country": "US",
    },
    "c-003": {
        "customer_id": "c-003",
        "name": "Alan Turing",
        "email": "alan@example.com",
        "tier": "bronze",
        "country": "GB",
    },
}
