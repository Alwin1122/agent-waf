"""Required tool-order enforcement backed by session history."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from app.rules.base import WAFRule
from app.rules.models import RuleResult, WAFRequest
from app.rules.stores import SequenceStateStore


class SequenceEnforcementRule(WAFRule):
    """Require earlier workflow tools to have completed in the same session."""

    name = "sequence_enforcement"

    def __init__(
        self,
        workflows: Iterable[Sequence[str]],
        store: SequenceStateStore,
    ) -> None:
        self._workflows = tuple(tuple(workflow) for workflow in workflows)
        if any(not workflow for workflow in self._workflows):
            raise ValueError("Sequence workflows cannot be empty.")
        self._store = store

    def evaluate(self, request: WAFRequest) -> RuleResult:
        applicable = [
            workflow for workflow in self._workflows if request.tool in workflow
        ]
        if not applicable:
            return self.allow("No sequence configured for this tool")

        history = self._store.get_completed_tools(
            request.agent_id, request.session_id
        )
        for workflow in applicable:
            required = workflow[: workflow.index(request.tool)]
            if _is_subsequence(required, history):
                return self.allow("Required tool sequence has been satisfied")

        return self.block("Required tool sequence has not been completed")

    def record_success(self, request: WAFRequest) -> None:
        self._store.record_completed_tool(
            request.agent_id, request.session_id, request.tool
        )


def _is_subsequence(required: Sequence[str], history: Sequence[str]) -> bool:
    if not required:
        return True
    position = 0
    for completed_tool in history:
        if completed_tool == required[position]:
            position += 1
            if position == len(required):
                return True
    return False
