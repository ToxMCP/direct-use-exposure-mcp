from __future__ import annotations

from exposure_scenario_mcp.probability_profiles import ProbabilityBoundsProfileRegistry


def test_packaged_probability_profile_manifest_loads() -> None:
    manifest = ProbabilityBoundsProfileRegistry.load().manifest()

    assert manifest.profile_version == "2026.03.25.v1"
    assert manifest.profile_count >= 2
    assert any(
        item.profile_id == "adult_leave_on_hand_cream_use_amount_per_event"
        for item in manifest.profiles
    )
    assert any(
        item.profile_id == "adult_trigger_spray_room_volume_m3" for item in manifest.profiles
    )
