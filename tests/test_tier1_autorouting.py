from __future__ import annotations

from exposure_scenario_mcp.benchmarks import load_benchmark_manifest
from exposure_scenario_mcp.models import (
    AirflowDirectionality,
    InhalationTier1ScenarioRequest,
    ParticleSizeRegime,
    PopulationProfile,
    ProductUseProfile,
    Route,
    ScenarioClass,
)
from exposure_scenario_mcp.tier1_autorouting import (
    TIER1_TWO_ZONE_AUTO_ENABLED,
    can_auto_select_two_zone,
    tier1_two_zone_autorouting_manifest,
)
from exposure_scenario_mcp.tier1_inhalation_profiles import Tier1InhalationProfileRegistry


def _make_request(
    *,
    product_category: str = "personal_care",
    application_method: str = "pump_spray",
    product_subtype: str | None = None,
) -> InhalationTier1ScenarioRequest:
    return InhalationTier1ScenarioRequest(
        chemical_id="auto-tier1-test",
        route=Route.INHALATION,
        scenario_class=ScenarioClass.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category=product_category,
            product_subtype=product_subtype,
            physical_form="spray",
            application_method=application_method,
            concentration_fraction=0.05,
            use_amount_per_event=4.0,
            use_amount_unit="g",
            use_events_per_day=1.0,
            room_volume_m3=30.0,
            air_exchange_rate_per_hour=0.5,
            exposure_duration_hours=1.0,
            aerosolized_fraction=0.2,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=70.0,
            inhalation_rate_m3_per_hour=0.5,
        ),
        source_distance_m=0.35,
        spray_duration_seconds=8.0,
        near_field_volume_m3=2.0,
        airflow_directionality=AirflowDirectionality.CROSS_DRAFT,
        particle_size_regime=ParticleSizeRegime.COARSE_SPRAY,
    )


def test_tier1_two_zone_autorouting_manifest_references_known_benchmarks() -> None:
    benchmark_case_ids = {item["id"] for item in load_benchmark_manifest()["cases"]}
    manifest = tier1_two_zone_autorouting_manifest()

    assert manifest["defaultEnabled"] is False
    assert manifest["decisionStatus"] == "benchmark_pending_release_signoff"
    assert set(manifest["benchmarkCaseIds"]).issubset(benchmark_case_ids)


def test_tier1_two_zone_autorouting_remains_disabled_by_default() -> None:
    registry = Tier1InhalationProfileRegistry.load()
    request = _make_request()
    matched_profile = registry.matching_profiles(
        product_family=request.product_use_profile.product_category,
        application_method=request.product_use_profile.application_method,
        product_subtype=request.product_use_profile.product_subtype,
    )[0]

    assert TIER1_TWO_ZONE_AUTO_ENABLED is False
    assert (
        can_auto_select_two_zone(
            request,
            matched_profile,
            saturation_cap_applied=False,
        )
        is False
    )


def test_tier1_two_zone_autorouting_candidate_passes_gating_when_enabled(monkeypatch) -> None:
    import exposure_scenario_mcp.tier1_autorouting as autorouting

    request = _make_request()
    matched_profile = type(
        "MatchedProfile",
        (),
        {
            "profile_id": "personal_care_pump_spray_tier1",
            "supports_two_zone": True,
        },
    )()

    monkeypatch.setattr(autorouting, "TIER1_TWO_ZONE_AUTO_ENABLED", True)

    assert (
        autorouting.can_auto_select_two_zone(
            request,
            matched_profile,
            saturation_cap_applied=False,
        )
        is True
    )
    assert (
        autorouting.can_auto_select_two_zone(
            request,
            matched_profile,
            saturation_cap_applied=True,
        )
        is False
    )
