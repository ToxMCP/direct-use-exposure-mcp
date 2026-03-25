from __future__ import annotations

from exposure_scenario_mcp.scenario_probability_packages import (
    ScenarioProbabilityPackageRegistry,
)


def test_scenario_probability_package_registry_exposes_packaged_profiles() -> None:
    manifest = ScenarioProbabilityPackageRegistry.load().manifest()

    assert manifest.profile_version == "2026.03.25.v1"
    assert manifest.profile_count >= 2
    assert {
        "adult_leave_on_hand_cream_use_intensity_package",
        "adult_trigger_spray_room_context_package",
    } <= {item.profile_id for item in manifest.profiles}
