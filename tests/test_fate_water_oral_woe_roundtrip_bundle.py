from __future__ import annotations

import json

from tests.fixtures.cross_suite.fate_water_oral_woe_roundtrip import (
    SOURCE_SURFACE_ARTIFACT_ID,
    WOE_ROUNDTRIP_FIXTURE_PATH,
    build_fate_water_oral_woe_roundtrip_bundle,
)


def test_fate_water_oral_woe_roundtrip_bundle_matches_checked_in_fixture() -> None:
    generated = build_fate_water_oral_woe_roundtrip_bundle()
    checked_in = json.loads(WOE_ROUNDTRIP_FIXTURE_PATH.read_text(encoding="utf-8"))
    assert generated == checked_in


def test_fate_water_oral_woe_roundtrip_bundle_preserves_concentration_to_intake_lineage() -> None:
    bundle = build_fate_water_oral_woe_roundtrip_bundle()

    assert bundle["bundleId"] == "fate-water-oral-exposure-handoff-001"
    assert bundle["targetConsumer"] == "woe_ngra"
    assert len(bundle["evidenceItems"]) == 1

    evidence = bundle["evidenceItems"][0]
    assert evidence["exposureScenario"] == "environmental_media_oral_screening"
    assert evidence["route"] == "oral"
    assert evidence["oralExposureContext"] == "environmental_media"
    assert evidence["doseUnit"] == "mg/kg-day"
    assert evidence["intendedUseFamily"] == "environmental"
    assert "surface_water_concentration_mg_per_l" in evidence["routeMetricKeys"]
    assert "drinking_water_intake_l_per_day" in evidence["routeMetricKeys"]
    assert "source_concentration_surface_ids" in evidence["routeMetricKeys"]

    identifiers = {
        item["identifierType"]: item["identifierValue"] for item in evidence["studyIdentifiers"]
    }
    assert identifiers["pathway_semantics"] == "concentration_to_intake"
    assert identifiers["route_mechanism"] == "drinking_water_concentration_to_intake"
    assert identifiers["source_concentration_surface_id"] == SOURCE_SURFACE_ARTIFACT_ID
    assert identifiers["time_window_mode"] == "steady_state"

    object_type_refs = [ref["objectTypeRef"] for ref in evidence["upstreamArtifactRefs"]]
    assert object_type_refs[:2] == ["ExposureScenarioDefinition", "RouteDoseEstimate"]
    assert "ConcentrationSurface" in object_type_refs
    assert "EnvironmentalReleaseScenario" in object_type_refs
    assert "RegulatoryHandoffReviewPacket" in object_type_refs
