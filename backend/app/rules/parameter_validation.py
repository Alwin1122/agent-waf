"""Generic inspection of tool parameters before tool-specific validation."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from app.rules.base import WAFRule
from app.rules.models import RuleResult, WAFRequest

DEFAULT_BLOCKED_PHRASES = (
    "ignore previous instructions",
    "reveal system prompt",
    "show system prompt",
)


class ParameterValidationRule(WAFRule):
    """Block prompt-injection phrases and oversized parameter payloads."""

    name = "parameter_validation"

    def __init__(
        self,
        blocked_phrases: Iterable[str] = DEFAULT_BLOCKED_PHRASES,
        *,
        max_string_length: int = 1_024,
        max_parameter_bytes: int = 16_384,
    ) -> None:
        if max_string_length < 1 or max_parameter_bytes < 1:
            raise ValueError("Parameter size limits must be positive.")
        self._blocked_phrases = tuple(
            phrase.casefold() for phrase in blocked_phrases if phrase
        )
        self._max_string_length = max_string_length
        self._max_parameter_bytes = max_parameter_bytes

    def evaluate(self, request: WAFRequest) -> RuleResult:
        encoded = json.dumps(
            request.parameters,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        if len(encoded) > self._max_parameter_bytes:
            return self.block("Parameter payload exceeds the configured size limit")

        for value in _string_values(request.parameters):
            if len(value) > self._max_string_length:
                return self.block("A string parameter exceeds the configured size limit")
            normalized = value.casefold()
            if any(phrase in normalized for phrase in self._blocked_phrases):
                return self.block("Parameter content matched a blocked pattern")

        return self.allow("Parameters passed WAF validation")


def _string_values(value: Any) -> Iterable[str]:
    """Yield string values recursively without exposing them to logs or reasons."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from _string_values(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            yield from _string_values(nested)
