from __future__ import annotations

import pytest

from exposure_scenario_mcp.models import AirflowDirectionality, ParticleSizeRegime
from exposure_scenario_mcp.tier1_inhalation_profiles import Tier1InhalationProfileRegistry


def test_tier1_inhalation_profile_manifest_and_matching() -> None:
    registry = Tier1InhalationProfileRegistry.load()
    manifest = registry.manifest()

    assert manifest.profile_version == "2026.04.07.v5"
    assert manifest.directionality_profile_count == 5
    assert manifest.particle_profile_count == 3
    assert manifest.profile_count == 9
    assert {item.source_id for item in manifest.sources} == {
        "benchmark_tier1_nf_ff_parameter_pack_v1",
        "benchmark_tier1_nf_ff_household_cleaner_profiles_v1",
        "benchmark_tier1_nf_ff_personal_care_profiles_v1",
        "benchmark_tier1_nf_ff_disinfectant_profiles_v1",
        "benchmark_tier1_nf_ff_pest_control_profiles_v1",
    }

    airflow = registry.airflow_profile(AirflowDirectionality.CROSS_DRAFT)
    assert airflow.exchange_turnover_per_hour == pytest.approx(32.0, rel=1e-6)
    assert airflow.source_id == "benchmark_tier1_nf_ff_parameter_pack_v1"

    particle = registry.particle_profile(ParticleSizeRegime.COARSE_SPRAY)
    assert particle.persistence_factor == pytest.approx(0.85, rel=1e-6)
    assert particle.source_id == "benchmark_tier1_nf_ff_parameter_pack_v1"

    matches = registry.matching_profiles(
        product_family="household_cleaner",
        application_method="trigger_spray",
    )
    assert [item.profile_id for item in matches] == ["household_cleaner_trigger_spray_tier1"]

    personal_care_matches = registry.matching_profiles(
        product_family="personal_care",
        application_method="pump_spray",
    )
    assert [item.profile_id for item in personal_care_matches] == [
        "personal_care_pump_spray_tier1"
    ]

    subtype_matches = registry.matching_profiles(
        product_family="pesticide",
        product_subtype="indoor_surface_insecticide",
        application_method="trigger_spray",
    )
    assert [item.profile_id for item in subtype_matches] == [
        "pest_control_indoor_surface_trigger_spray_tier1"
    ]
    targeted_spot_matches = registry.matching_profiles(
        product_family="pesticide",
        product_subtype="targeted_spot_insecticide",
        application_method="trigger_spray",
    )
    assert [item.profile_id for item in targeted_spot_matches] == [
        "pest_control_targeted_spot_trigger_spray_tier1"
    ]
    crack_matches = registry.matching_profiles(
        product_family="pesticide",
        product_subtype="crack_and_crevice_insecticide",
        application_method="trigger_spray",
    )
    assert [item.profile_id for item in crack_matches] == [
        "pest_control_crack_crevice_trigger_spray_tier1"
    ]
    air_space_matches = registry.matching_profiles(
        product_family="pesticide",
        product_subtype="air_space_insecticide",
        application_method="aerosol_spray",
    )
    assert [item.profile_id for item in air_space_matches] == [
        "pest_control_air_space_aerosol_tier1"
    ]
