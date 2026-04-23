from __future__ import annotations

import json

from tests.fixtures.cross_suite.woe_roundtrip import (
    WOE_ROUNDTRIP_FIXTURE_PATH,
    build_direct_use_woe_roundtrip_bundle,
)


def test_direct_use_woe_roundtrip_bundle_matches_checked_in_fixture() -> None:
    expected = json.loads(WOE_ROUNDTRIP_FIXTURE_PATH.read_text(encoding="utf-8"))
    actual = build_direct_use_woe_roundtrip_bundle()

    assert actual == expected


def test_direct_use_woe_roundtrip_bundle_preserves_direct_use_context_and_refs() -> None:
    bundle = build_direct_use_woe_roundtrip_bundle()
    evidence_items = bundle["evidenceItems"]

    assert {item["oralExposureContext"] for item in evidence_items} == {
        "direct_use_medicinal",
        "direct_use_supplement",
    }
    assert {item["intendedUseFamily"] for item in evidence_items} == {
        "medicinal",
        "supplement",
    }
    assert all(item["exposureScenario"] == "oral_direct_intake" for item in evidence_items)
    assert all(
        {ref["objectTypeRef"] for ref in item["upstreamArtifactRefs"]}
        == {"ExposureScenario", "PbpkScenarioInput", "PbpkExternalImportPackage"}
        for item in evidence_items
    )
    assert all(
        ref["producerModule"] == "direct_use_exposure"
        for item in evidence_items
        for ref in item["upstreamArtifactRefs"]
    )
