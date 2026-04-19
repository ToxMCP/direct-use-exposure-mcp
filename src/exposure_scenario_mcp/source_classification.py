"""Shared helpers for classifying source identifiers."""

from __future__ import annotations


def is_heuristic_source_id(source_id: str | None) -> bool:
    """Return True when a source identifier denotes a heuristic screening family."""

    if source_id is None:
        return False
    return "heuristic" in source_id.lower()
