from __future__ import annotations

from exposure_scenario_mcp.probability_profiles import ProbabilityBoundsProfileRegistry


def test_packaged_probability_profile_manifest_loads() -> None:
    manifest = ProbabilityBoundsProfileRegistry.load().manifest()

    assert manifest.profile_version == "2026.03.25.v2"
    assert manifest.profile_count >= 4
    assert {
        "adult_leave_on_hand_cream_use_amount_per_event",
        "adult_leave_on_hand_cream_concentration_fraction",
        "adult_trigger_spray_room_volume_m3",
        "child_direct_oral_liquid_use_events_per_day",
    } <= {item.profile_id for item in manifest.profiles}
    assert {
        item.driver_family.value for item in manifest.profiles
    } >= {
        "use_burden",
        "formulation_strength",
        "microenvironment",
        "ingestion_regimen",
    }
