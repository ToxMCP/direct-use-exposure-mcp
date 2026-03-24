from __future__ import annotations

from exposure_scenario_mcp.contracts import (
    build_release_metadata_report,
    build_release_readiness_report,
    build_security_provenance_review_report,
)
from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.guidance import (
    conformance_report_markdown,
    release_notes_markdown,
    release_readiness_markdown,
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
