"""Agent-specific customer data-scope enforcement."""

from __future__ import annotations

from app.rules.base import WAFRule
from app.rules.models import RuleResult, WAFRequest
from app.rules.stores import AgentScopeStore


class DataScopeRule(WAFRule):
    """Prevent an agent from addressing customers outside its declared scope."""

    name = "data_scope"

    def __init__(self, store: AgentScopeStore) -> None:
        self._store = store

    def evaluate(self, request: WAFRequest) -> RuleResult:
        customer_id = request.parameters.get("customer_id")
        if not isinstance(customer_id, str):
            return self.allow("Request does not address customer-scoped data")

        allowed_ids = self._store.get_customer_ids(request.agent_id)
        if allowed_ids is None:
            return self.allow("No customer scope declared for this agent")
        if customer_id not in allowed_ids:
            return self.block("Customer is outside agent scope")
        return self.allow("Customer is within agent scope")
