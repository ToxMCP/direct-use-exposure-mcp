from __future__ import annotations

from exposure_scenario_mcp.archetypes import ArchetypeLibraryRegistry


def test_packaged_archetype_library_manifest_loads() -> None:
    manifest = ArchetypeLibraryRegistry.load().manifest()

    assert manifest.library_version == "2026.03.25.v2"
    assert manifest.set_count >= 4
    assert any(item.set_id == "adult_leave_on_hand_cream" for item in manifest.sets)
    assert any(item.set_id == "adult_trigger_spray_room" for item in manifest.sets)
    assert any(item.set_id == "adult_personal_care_pump_spray_tier1" for item in manifest.sets)
