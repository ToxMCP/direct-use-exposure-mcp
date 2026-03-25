from __future__ import annotations

from exposure_scenario_mcp.contracts import (
    build_release_metadata_report,
    build_release_readiness_report,
    build_security_provenance_review_report,
)
from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.guidance import (
    archetype_library_guide,
    conformance_report_markdown,
    probability_bounds_guide,
    release_notes_markdown,
    release_readiness_markdown,
    uncertainty_framework,
    validation_framework,
)


def test_release_guidance_mentions_current_benchmark_matrix() -> None:
    registry = DefaultsRegistry.load()
    metadata = build_release_metadata_report(registry)
    readiness = build_release_readiness_report(registry)
    security_review = build_security_provenance_review_report(registry)

    release_notes = release_notes_markdown(metadata)
    readiness_markdown = release_readiness_markdown(readiness)
    conformance = conformance_report_markdown(metadata, readiness, security_review)

    assert "Benchmark Matrix" in release_notes
    assert "Benchmark Matrix" in readiness_markdown
    assert "`dermal_pbpk_external_import_package`" in release_notes
    assert "`dermal_pbpk_external_import_package`" in readiness_markdown
    assert f"Benchmark cases published: `{metadata.benchmark_case_count}`" in conformance
    assert "`dermal_pbpk_external_import_package`" in conformance


def test_uncertainty_and_validation_guidance_expose_tier_a_b_posture() -> None:
    uncertainty = uncertainty_framework()
    validation = validation_framework()
    archetypes = archetype_library_guide()
    probability_bounds = probability_bounds_guide()

    assert "Tier A" in uncertainty
    assert "Tier B" in uncertainty
    assert "Tier C" in uncertainty
    assert "Packaged Archetype Sets" in archetypes
    assert "`adult_leave_on_hand_cream`" in archetypes
    assert "Packaged Probability Profiles" in probability_bounds
    assert "`adult_leave_on_hand_cream_use_amount_per_event`" in probability_bounds
    assert "Packaged Scenario-Probability Profiles" in probability_bounds
    assert "`adult_leave_on_hand_cream_use_intensity_package`" in probability_bounds
    assert "benchmarkDomains" not in validation
    assert "External Dataset Candidates" in validation
    assert "`air_chamber_spray_time_series_candidate`" in validation
