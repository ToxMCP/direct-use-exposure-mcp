"""Typed error models for the exposure scenario engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ExposureScenarioError(Exception):
    """A structured, actionable error for tool-facing failures."""

    code: str
    message: str
    suggestion: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "suggestion": self.suggestion,
            "details": self.details,
        }

    def as_text(self) -> str:
        parts = [f"{self.code}: {self.message}"]
        if self.suggestion:
            parts.append(f"Suggestion: {self.suggestion}")
        if self.details:
            parts.append(f"Details: {self.details}")
        return " ".join(parts)


def ensure(
    condition: bool, code: str, message: str, suggestion: str | None = None, **details: Any
) -> None:
    """Raise a typed error when a required condition is not met."""

    if not condition:
        raise ExposureScenarioError(
            code=code, message=message, suggestion=suggestion, details=details
        )
