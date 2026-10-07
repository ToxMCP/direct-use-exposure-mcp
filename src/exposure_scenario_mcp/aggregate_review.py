"""Compatibility findings for deterministic aggregate bookkeeping.

These checks do not establish source-event independence, material correspondence,
complete exposure coverage or a joint population distribution.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass

from exposure_scenario_mcp.models import ExposureScenario, Severity


@dataclass(frozen=True)
class AggregateReviewFinding:
    code: str
    message: str
    severity: Severity


def _resolved_body_weight(scenario: ExposureScenario) -> float | None:
    # Match the population plausibility check: calculation assumptions are
    # authoritative; the profile is only a fallback for retained/imported records.
    value = scenario.population_profile.body_weight_kg
    for assumption in scenario.assumptions:
        if (
            assumption.name == "body_weight_kg"
            and isinstance(assumption.value, int | float)
            and not isinstance(assumption.value, bool)
        ):
            value = float(assumption.value)
    return value


def _same_weight(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9)


def review_aggregate_components(
    components: list[ExposureScenario],
) -> list[AggregateReviewFinding]:
    """Keep arithmetic inspectable while identifying non-interpretable combinations."""
    findings: list[AggregateReviewFinding] = []
    weights = [_resolved_body_weight(item) for item in components]
    for item, weight in zip(components, weights, strict=True):
        profile_weight = item.population_profile.body_weight_kg
        if weight is None or not math.isfinite(weight) or weight <= 0:
            findings.append(
                AggregateReviewFinding(
                    "aggregate_population_context_incomplete",
                    f"Component `{item.scenario_id}` has no finite positive resolved body "
                    "weight for its normalized dose. Recover the calculation denominator "
                    "before interpreting an aggregate.",
                    Severity.ERROR,
                )
            )
        elif profile_weight is not None and not _same_weight(weight, profile_weight):
            findings.append(
                AggregateReviewFinding(
                    "aggregate_component_population_inconsistent",
                    f"Component `{item.scenario_id}` records calculation body weight "
                    f"{weight:g} kg but population-profile body weight {profile_weight:g} kg. "
                    "Recover the original calculation context and rebuild the component.",
                    Severity.ERROR,
                )
            )

    if len(components) < 2:
        return findings

    contexts = [
        (
            item.population_profile.population_group.strip().casefold(),
            item.population_profile.region.strip().casefold(),
            tuple(
                sorted({tag.strip().casefold() for tag in item.population_profile.demographic_tags})
            ),
        )
        for item in components
    ]
    differences = []
    for index, name in enumerate(("population_group", "region", "demographic_tags")):
        if len({context[index] for context in contexts}) > 1:
            differences.append(name)
    finite_weights = [value for value in weights if value is not None and math.isfinite(value)]
    if finite_weights and any(
        not _same_weight(finite_weights[0], value) for value in finite_weights[1:]
    ):
        differences.append("resolved_body_weight_kg")
    if differences:
        findings.append(
            AggregateReviewFinding(
                "aggregate_population_mismatch",
                "Components disagree on "
                + ", ".join(differences)
                + ": "
                + "; ".join(
                    f"`{item.scenario_id}` ({item.population_profile.population_group}, "
                    f"{item.population_profile.region}, calculation body weight "
                    f"{weight!r} kg, tags={item.population_profile.demographic_tags!r})"
                    for item, weight in zip(components, weights, strict=True)
                )
                + ". The sum is retained for inspection only and cannot represent one "
                "compatible population aggregate. Rebuild on a common population and dose "
                "basis or keep population-specific results separate.",
                Severity.ERROR,
            )
        )

    # Matching declared profiles are a review signal, not proof of duplicate events.
    # Never delete/deduplicate doses based solely on this fingerprint.
    by_profile: dict[str, list[str]] = {}
    for item in components:
        key = json.dumps(
            {
                "route": item.route.value,
                "product_use": item.product_use_profile.model_dump(mode="json", by_alias=True),
                "population": item.population_profile.model_dump(mode="json", by_alias=True),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        by_profile.setdefault(key, []).append(item.scenario_id)
    repeated = [ids for ids in by_profile.values() if len(ids) > 1]
    if repeated:
        findings.append(
            AggregateReviewFinding(
                "aggregate_component_overlap_unresolved",
                "Matching declared use and population profiles occur under different scenario "
                "IDs: "
                + "; ".join(", ".join(ids) for ids in repeated)
                + ". Review source/event correspondence: these may be repeated records, "
                "alternative scenarios or genuinely independent uses. Arithmetic is unchanged; "
                "independence is not established and no automatic deduplication is performed.",
                Severity.WARNING,
            )
        )
    findings.append(
        AggregateReviewFinding(
            "aggregate_scope_unverified",
            "This sum accounts for the supplied components only. Source/event independence, "
            "material correspondence, compatible periods and complete exposure coverage are "
            "not verified by this contract. Review an explicit inventory of additive, "
            "alternative, overlapping and omitted sources. Unknown omissions remain unknown; "
            "separate marginal P95s do not establish an aggregate P95.",
            Severity.INFO,
        )
    )
    return findings
