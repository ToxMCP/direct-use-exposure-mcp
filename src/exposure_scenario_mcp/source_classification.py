"""Shared helpers for classifying source identifiers."""

from __future__ import annotations

ROUTE_SEMANTIC_SOURCE_IDS = frozenset(
    {
        "heuristic_consexpo_pest_control_aerosol_airborne_fraction_bridge_2026",
        "pressurized_aerosol_volume_interpretation_heuristics_2026",
    }
)


def is_heuristic_source_id(source_id: str | None) -> bool:
    """Return True when a source identifier denotes a heuristic screening family."""

    if source_id is None:
        return False
    return "heuristic" in source_id.lower()


def is_route_semantic_source_id(source_id: str | None) -> bool:
    """Return True for deterministic screening-boundary source families."""

    if source_id is None:
        return False
    normalized = source_id.lower()
    return normalized.startswith("screening_") or normalized in ROUTE_SEMANTIC_SOURCE_IDS


def is_warning_heuristic_source_id(source_id: str | None) -> bool:
    """Return True for low-confidence default families that should surface warnings."""

    return is_heuristic_source_id(source_id) and not is_route_semantic_source_id(source_id)


def is_benchmark_source_id(source_id: str | None) -> bool:
    """Return True for benchmark-only source families."""

    if source_id is None:
        return False
    return source_id.startswith("benchmark_")
