from __future__ import annotations

from exposure_scenario_mcp.archetypes import ArchetypeLibraryRegistry


def test_packaged_archetype_library_manifest_loads() -> None:
    manifest = ArchetypeLibraryRegistry.load().manifest()

    assert manifest.library_version == "2026.04.10.v3"
    assert manifest.set_count >= 5
    assert any(item.set_id == "adult_leave_on_hand_cream" for item in manifest.sets)
    assert any(item.set_id == "adult_leave_on_face_cream_sccs" for item in manifest.sets)
    assert any(item.set_id == "adult_trigger_spray_room" for item in manifest.sets)
    assert any(item.set_id == "adult_personal_care_pump_spray_tier1" for item in manifest.sets)
