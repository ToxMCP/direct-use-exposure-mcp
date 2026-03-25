"""Tier C single-driver probability-bounds helpers."""

from __future__ import annotations

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.errors import ensure
from exposure_scenario_mcp.models import (
    BiasDirection,
    BuildProbabilityBoundsFromProfileInput,
    ProbabilityBoundDosePoint,
    ProbabilityBoundsDriverProfile,
    ProbabilityBoundsProfileSummary,
    UncertaintyQuantificationStatus,
    UncertaintyRegisterEntry,
    UncertaintyTier,
    UncertaintyType,
)
from exposure_scenario_mcp.probability_profiles import ProbabilityBoundsProfileRegistry
from exposure_scenario_mcp.provenance import AssumptionTracker
from exposure_scenario_mcp.uncertainty import BOUNDS_PARAMETER_CONFIG, _with_override

APPLICABILITY_MAP = {
    "product_category": ("product_use_profile", "product_category"),
    "physical_form": ("product_use_profile", "physical_form"),
    "application_method": ("product_use_profile", "application_method"),
    "retention_type": ("product_use_profile", "retention_type"),
    "population_group": ("population_profile", "population_group"),
    "region": ("population_profile", "region"),
}


def _request_value(request, key: str):
    section_name, field_name = APPLICABILITY_MAP[key]
    section = getattr(request, section_name)
    return getattr(section, field_name)


def _normalize(value):
    if isinstance(value, str):
        return value.lower()
    return value


def _validate_profile_against_request(
    params: BuildProbabilityBoundsFromProfileInput,
    profile: ProbabilityBoundsDriverProfile,
) -> None:
    ensure(
        params.base_request.route == profile.route,
        "probability_profile_route_mismatch",
        (
            f"Profile `{profile.profile_id}` is for route `{profile.route.value}`, but the "
            f"base request uses `{params.base_request.route.value}`."
        ),
        suggestion="Choose a driver profile that matches the base request route.",
    )
    ensure(
        params.base_request.scenario_class == profile.scenario_class,
        "probability_profile_scenario_class_mismatch",
        (
            f"Profile `{profile.profile_id}` is for scenario class "
            f"`{profile.scenario_class.value}`, but the base request uses "
            f"`{params.base_request.scenario_class.value}`."
        ),
        suggestion="Choose a driver profile that matches the base request scenario class.",
    )
    ensure(
        profile.parameter_name in BOUNDS_PARAMETER_CONFIG,
        "probability_profile_parameter_unsupported",
        f"Profile `{profile.profile_id}` uses unsupported parameter `{profile.parameter_name}`.",
        suggestion="Update the packaged profile so it uses a supported monotonic driver.",
    )
    supported_routes = BOUNDS_PARAMETER_CONFIG[profile.parameter_name]["routes"]
    ensure(
        params.base_request.route in supported_routes,
        "probability_profile_parameter_route_mismatch",
        (
            f"Profile parameter `{profile.parameter_name}` is not supported for route "
            f"`{params.base_request.route.value}`."
        ),
        suggestion="Choose a profile whose driver is route-relevant for the base request.",
    )
    for key, expected in profile.applicability.items():
        ensure(
            key in APPLICABILITY_MAP,
            "probability_profile_applicability_key_unsupported",
            f"Applicability key `{key}` is not supported by the probability-bounds layer.",
            suggestion=(
                "Use one of: " + ", ".join(f"`{name}`" for name in sorted(APPLICABILITY_MAP)) + "."
            ),
        )
        actual = _request_value(params.base_request, key)
        ensure(
            _normalize(actual) == _normalize(expected),
            "probability_profile_applicability_mismatch",
            (
                f"Profile `{profile.profile_id}` expects `{key}` = `{expected}`, but the "
                f"base request uses `{actual}`."
            ),
            suggestion="Use a base request that matches the packaged profile applicability.",
        )


def build_probability_bounds_from_profile(
    params: BuildProbabilityBoundsFromProfileInput,
    engine,
    registry: DefaultsRegistry,
    profiles: ProbabilityBoundsProfileRegistry,
    *,
    generated_at: str | None = None,
) -> ProbabilityBoundsProfileSummary:
    profile = profiles.get_profile(params.driver_profile_id)
    _validate_profile_against_request(params, profile)
    base_scenario = engine.build(params.base_request)
    points = []
    for item in profile.support_points:
        scenario = engine.build(
            _with_override(params.base_request, profile.parameter_name, item.parameter_value)
        )
        points.append((item, scenario))
    minimum_dose = min(points, key=lambda entry: entry[1].external_dose.value)[1].external_dose
    maximum_dose = max(points, key=lambda entry: entry[1].external_dose.value)[1].external_dose
    support_points = [
        ProbabilityBoundDosePoint(
            pointId=item.point_id,
            parameterValue=item.parameter_value,
            dose=scenario.external_dose,
            cumulativeProbabilityLower=item.cumulative_probability_lower,
            cumulativeProbabilityUpper=item.cumulative_probability_upper,
            note=item.note,
        )
        for item, scenario in points
    ]
    uncertainty_register = [
        UncertaintyRegisterEntry(
            entry_id="single-driver-probability-bounds",
            title="Single-driver probability bounds are available for the selected parameter",
            uncertainty_types=[
                UncertaintyType.PARAMETER_UNCERTAINTY,
                UncertaintyType.SCENARIO_UNCERTAINTY,
            ],
            related_assumptions=[profile.parameter_name],
            quantification_status=UncertaintyQuantificationStatus.PROBABILITY_BOUNDS,
            bias_direction=BiasDirection.BIDIRECTIONAL,
            impact_level="high",
            summary=(
                f"Profile `{profile.profile_id}` provides cumulative probability bounds for "
                f"single-driver support points on `{profile.parameter_name}` while all other "
                "drivers remain fixed at the base scenario."
            ),
            recommendation=(
                "Do not treat this output as a joint exposure distribution or a validated "
                "population simulation."
            ),
        )
    ]
    if profile.limitations:
        uncertainty_register.append(
            UncertaintyRegisterEntry(
                entry_id="single-driver-probability-bounds-limitations",
                title="Profile-specific limitations remain in force",
                uncertainty_types=[UncertaintyType.MODEL_UNCERTAINTY],
                related_assumptions=[profile.parameter_name],
                quantification_status=UncertaintyQuantificationStatus.PROBABILITY_BOUNDS,
                bias_direction=BiasDirection.UNKNOWN,
                impact_level="medium",
                summary="; ".join(profile.limitations),
                recommendation=(
                    "Keep the probability-bounds output tied to its packaged driver profile and "
                    "avoid extrapolating it to unmanaged contexts."
                ),
            )
        )
    dependency_metadata = base_scenario.dependency_metadata
    validation_summary = base_scenario.validation_summary.model_copy(
        update={
            "highest_supported_uncertainty_tier": UncertaintyTier.TIER_C,
            "probabilistic_enablement": "gated",
            "notes": [
                *base_scenario.validation_summary.notes,
                "Single-driver probability bounds are packaged for selected drivers only.",
            ],
        },
        deep=True,
    )
    tracker = AssumptionTracker(registry=registry)
    tracker.add_derived(
        "probability_profile_support_point_count",
        len(profile.support_points),
        None,
        "Tier C single-driver probability-bounds support-point count.",
    )
    tracker.add_derived(
        "probability_profile_id",
        profile.profile_id,
        None,
        "Packaged probability-bounds driver profile identifier.",
    )
    return ProbabilityBoundsProfileSummary(
        summaryId=f"pbnd-{base_scenario.scenario_id.split('-')[-1]}",
        chemical_id=base_scenario.chemical_id,
        route=base_scenario.route,
        scenarioClass=base_scenario.scenario_class,
        label=params.label,
        driverProfileId=profile.profile_id,
        driverParameterName=profile.parameter_name,
        profileVersion=profiles.version,
        archetypeLibrarySetId=profile.archetype_library_set_id,
        baseScenario=base_scenario,
        supportPoints=support_points,
        minimumDose=minimum_dose,
        maximumDose=maximum_dose,
        uncertaintyRegister=uncertainty_register,
        dependencyMetadata=dependency_metadata,
        validationSummary=validation_summary,
        provenance=tracker.provenance(
            plugin_id="probability_bounds_service",
            algorithm_id="uncertainty.probability_bounds.v1",
            generated_at=generated_at,
        ),
        interpretation_notes=[
            (
                "This output carries single-driver probability bounds, not a joint "
                "population distribution."
            ),
            (
                "Only the packaged driver varies across support points; all other "
                "scenario inputs remain fixed."
            ),
        ]
        + [f"Profile limitation: {item}" for item in profile.limitations],
    )
