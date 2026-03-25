from __future__ import annotations

import pytest

from exposure_scenario_mcp.models import AirflowDirectionality, ParticleSizeRegime
from exposure_scenario_mcp.tier1_inhalation_profiles import Tier1InhalationProfileRegistry


def test_tier1_inhalation_profile_manifest_and_matching() -> None:
    registry = Tier1InhalationProfileRegistry.load()
    manifest = registry.manifest()

    assert manifest.profile_version == "2026.03.25.v1"
    assert manifest.directionality_profile_count == 5
    assert manifest.particle_profile_count == 3
    assert manifest.profile_count == 3
    assert {item.source_id for item in manifest.sources} == {
        "benchmark_tier1_nf_ff_parameter_pack_v1",
        "benchmark_tier1_nf_ff_product_profiles_v1",
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
