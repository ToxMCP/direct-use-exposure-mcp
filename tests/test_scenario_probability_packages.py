from __future__ import annotations

from exposure_scenario_mcp.scenario_probability_packages import (
    ScenarioProbabilityPackageRegistry,
)


def test_scenario_probability_package_registry_exposes_packaged_profiles() -> None:
    manifest = ScenarioProbabilityPackageRegistry.load().manifest()

    assert manifest.profile_version == "2026.03.25.v3"
    assert manifest.profile_count >= 5
    assert {
        "adult_leave_on_hand_cream_use_intensity_package",
        "adult_leave_on_hand_cream_composition_use_package",
        "adult_trigger_spray_room_context_package",
        "child_direct_oral_liquid_regimen_package",
        "adult_personal_care_pump_spray_tier1_near_field_context_package",
    } <= {item.profile_id for item in manifest.profiles}
    assert {
        item.package_family.value for item in manifest.profiles
    } >= {
        "use_intensity",
        "composition_use_burden",
        "microenvironment_context",
        "near_field_context",
        "ingestion_regimen",
    }
