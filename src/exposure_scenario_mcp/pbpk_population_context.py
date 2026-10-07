"""Preserve the calculation denominator in both PBPK export paths."""

from __future__ import annotations

import math

from exposure_scenario_mcp.models import ExposureScenario, LimitationNote, Severity


def resolve_pbpk_body_weight(
    scenario: ExposureScenario,
) -> tuple[float | None, list[LimitationNote]]:
    """Recorded assumptions govern; a profile is a fallback only when none exist.

    Conflicting recorded values cannot identify the original calculation context.
    A valid denominator that disagrees with a profile stays inspectable, but its
    correspondence requires correction before a downstream import is ready.
    """
    issues: list[LimitationNote] = []

    def issue(code: str, message: str) -> None:
        issues.append(LimitationNote(code=code, message=message, severity=Severity.ERROR))

    assumptions = [item for item in scenario.assumptions if item.name == "body_weight_kg"]
    values = [item.value for item in assumptions] or [scenario.population_profile.body_weight_kg]
    if all(value is None for value in values):
        issue(
            "pbpk_body_weight_missing",
            "Recover the original calculation body weight before PBPK export.",
        )
        return None, issues
    numeric = [
        float(value)
        for value in values
        if isinstance(value, int | float) and not isinstance(value, bool)
    ]
    if (
        len(numeric) != len(values)
        or any(not math.isfinite(value) or value <= 0 for value in numeric)
        or any(item.unit not in {None, "kg"} for item in assumptions)
    ):
        issue(
            "pbpk_body_weight_invalid",
            "Recorded body weight must be finite, positive and expressed in kg. "
            "Rebuild the source calculation; no fallback or conversion is inferred.",
        )
        return None, issues
    weight = numeric[-1]
    if any(not math.isclose(weight, value, rel_tol=1e-9, abs_tol=1e-9) for value in numeric):
        issue(
            "pbpk_body_weight_conflicting_assumptions",
            "Recorded body-weight assumptions disagree. Recover the calculation "
            "denominator before PBPK export.",
        )
        return None, issues
    declared = scenario.population_profile.body_weight_kg
    if declared is not None and not math.isclose(weight, declared, rel_tol=1e-9, abs_tol=1e-9):
        issue(
            "pbpk_population_context_inconsistent",
            f"The dose uses a recorded body weight of {weight:g} kg but its population "
            f"profile declares {declared:g} kg. The original denominator and dose are "
            "preserved; rebuild a corresponding source scenario before import.",
        )
    return weight, issues
