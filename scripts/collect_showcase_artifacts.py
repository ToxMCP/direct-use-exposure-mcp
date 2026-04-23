#!/usr/bin/env python3
# ruff: noqa: E501
"""Collect live MCP showcase artifacts for the Direct-Use Exposure MCP report."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import shutil
import subprocess
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SHOWCASE_DIR = ROOT / "output" / "showcase_report"

RESOURCE_URIS: dict[str, str] = {
    "030_contracts_manifest.json": "contracts://manifest",
    "040_defaults_manifest.json": "defaults://manifest",
    "050_verification_summary.json": "verification://summary",
    "051_release_metadata_report.json": "release://metadata-report",
    "052_release_readiness_report.json": "release://readiness-report",
    "053_security_provenance_review_report.json": "release://security-provenance-review-report",
    "054_validation_coverage_report.json": "validation://coverage-report",
}

TOOL_RUNS: list[dict[str, str]] = [
    {
        "request_file": "schemas/examples/screening_dermal_request.json",
        "request_artifact": "100_screening_dermal_request.json",
        "tool_name": "exposure_build_screening_exposure_scenario",
        "result_artifact": "101_screening_dermal_result.json",
    },
    {
        "request_file": "schemas/examples/dietary_supplement_oral_request.json",
        "request_artifact": "110_direct_oral_request.json",
        "tool_name": "exposure_build_screening_exposure_scenario",
        "result_artifact": "111_direct_oral_result.json",
    },
    {
        "request_file": "schemas/examples/inhalation_tier1_request_two_zone.json",
        "request_artifact": "120_inhalation_tier1_request.json",
        "tool_name": "exposure_build_inhalation_tier1_screening_scenario",
        "result_artifact": "121_inhalation_tier1_result.json",
    },
    {
        "request_file": "schemas/examples/compare_jurisdictional_scenarios_request.json",
        "request_artifact": "130_jurisdiction_compare_request.json",
        "tool_name": "exposure_compare_jurisdictional_scenarios",
        "result_artifact": "131_jurisdiction_compare_result.json",
    },
    {
        "request_file": "schemas/examples/integrated_exposure_workflow_request.json",
        "request_artifact": "140_integrated_workflow_request.json",
        "tool_name": "exposure_run_integrated_workflow",
        "result_artifact": "141_integrated_workflow_result.json",
    },
    {
        "request_file": "NONE",
        "request_artifact": "150_verification_checks_request.json",
        "tool_name": "exposure_run_verification_checks",
        "result_artifact": "151_verification_checks_result.json",
    },
]

ARTIFACT_DESCRIPTIONS: dict[str, str] = {
    "000_run_metadata.json": "Execution metadata: endpoint, git SHA, commands, timestamps, and runtime versions.",
    "010_initialize.json": "Raw MCP initialize response from the live Streamable HTTP server.",
    "020_surface_inventory.json": "Live tool, resource, and prompt inventory as seen by the MCP client.",
    "030_contracts_manifest.json": "Published contract manifest served by the MCP.",
    "040_defaults_manifest.json": "Versioned defaults manifest and SHA256 served by the MCP.",
    "050_verification_summary.json": "Published verification summary resource.",
    "051_release_metadata_report.json": "Release metadata resource for v0.2.0.",
    "052_release_readiness_report.json": "Release readiness resource.",
    "053_security_provenance_review_report.json": "Security and provenance review resource.",
    "054_validation_coverage_report.json": "Validation coverage resource.",
    "100_screening_dermal_request.json": "Dermal screening request used in the live showcase run.",
    "101_screening_dermal_result.json": "Dermal screening tool result from the live showcase run.",
    "110_direct_oral_request.json": "Direct-use oral request used in the live showcase run.",
    "111_direct_oral_result.json": "Direct-use oral tool result from the live showcase run.",
    "120_inhalation_tier1_request.json": "Tier 1 inhalation request used in the live showcase run.",
    "121_inhalation_tier1_result.json": "Tier 1 inhalation tool result from the live showcase run.",
    "130_jurisdiction_compare_request.json": "Jurisdictional comparison request used in the live showcase run.",
    "131_jurisdiction_compare_result.json": "Jurisdictional comparison result from the live showcase run.",
    "140_integrated_workflow_request.json": "Integrated workflow request used in the live showcase run.",
    "141_integrated_workflow_result.json": "Integrated workflow result from the live showcase run.",
    "150_verification_checks_request.json": "Empty tool-call payload used for exposure_run_verification_checks.",
    "151_verification_checks_result.json": "Verification tool result from the live showcase run.",
    "160_sccs_face_cream_base_request.json": "Generic EU face-cream request used as the pre-evidence baseline for the SCCS case study.",
    "161_sccs_face_cream_baseline_result.json": "Baseline dermal scenario for the SCCS face-cream case study before reviewed evidence was applied.",
    "162_sccs_face_cream_raw_record.json": "Typed SCCS cosmetics guidance record used in the live case-study run.",
    "163_sccs_face_cream_evidence_result.json": "Mapped generic product-use evidence record built from the SCCS source.",
    "164_sccs_face_cream_fit_result.json": "Evidence-fit assessment between the generic face-cream request and the SCCS evidence record.",
    "165_sccs_face_cream_applied_request.json": "Request after SCCS evidence overrides were applied.",
    "166_sccs_face_cream_scenario_result.json": "Final SCCS-aligned dermal face-cream scenario.",
    "167_sccs_face_cream_compare_result.json": "Scenario comparison between the generic baseline and the SCCS-aligned face-cream scenario.",
    "168_sccs_face_cream_pbpk_export_request.json": "PBPK export request for the SCCS-aligned face-cream scenario.",
    "169_sccs_face_cream_pbpk_export_result.json": "PBPK-ready handoff object exported from the SCCS-aligned face-cream scenario.",
    "170_benchmark_tier1_disinfectant_request.json": "Benchmark Tier 1 disinfectant trigger-spray request replayed live against the MCP.",
    "171_benchmark_tier1_disinfectant_result.json": "Live Tier 1 disinfectant trigger-spray result for the benchmark replication run.",
    "172_benchmark_tier1_disinfectant_comparison.json": "Comparison between the live Tier 1 disinfectant trigger-spray result and the published benchmark fixture target.",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--server-url",
        default="http://127.0.0.1:8765/mcp",
        help="Live Streamable HTTP MCP URL to query.",
    )
    parser.add_argument(
        "--showcase-dir",
        type=Path,
        default=DEFAULT_SHOWCASE_DIR,
        help="Directory where summary and artifact files will be written.",
    )
    parser.add_argument(
        "--server-command",
        default="",
        help="Optional exact server command used for the audited run.",
    )
    return parser.parse_args()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_output(*args: str) -> str:
    git_executable = shutil.which("git")
    if git_executable is None:
        return ""
    completed = subprocess.run(  # noqa: S603
        [git_executable, *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def _git_info() -> dict[str, Any]:
    status_lines = [line for line in _git_output("status", "--short").splitlines() if line.strip()]
    return {
        "commit": _git_output("rev-parse", "HEAD"),
        "branch": _git_output("branch", "--show-current"),
        "dirty": bool(status_lines),
        "statusShort": status_lines,
    }


def _extract_resource_text(resource_result: Any) -> str:
    contents = resource_result.contents
    if not contents:
        raise ValueError("Resource result did not include any contents.")
    first = contents[0]
    text = getattr(first, "text", None)
    if text is not None:
        return text
    content = getattr(first, "content", None)
    if content is not None:
        return content
    raise ValueError(f"Unsupported resource content type: {type(first)!r}")


def _quality_flags(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return payload.get("qualityFlags") or payload.get("quality_flags") or []


def _fit_for_purpose(payload: dict[str, Any]) -> dict[str, Any]:
    return payload.get("fitForPurpose") or payload.get("fit_for_purpose") or {}


def _tier_semantics(payload: dict[str, Any]) -> dict[str, Any]:
    return payload.get("tierSemantics") or payload.get("tier_semantics") or {}


def _uncertainty_register(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return payload.get("uncertaintyRegister") or payload.get("uncertainty_register") or []


def _assumption_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["name"]: item for item in payload.get("assumptions", []) if item.get("name")}


def _reference_summary(payload: dict[str, Any]) -> dict[str, Any]:
    user_inputs: list[str] = []
    derived_parameters: list[str] = []
    references: dict[str, dict[str, Any]] = {}
    for item in payload.get("assumptions", []):
        name = item.get("name")
        if not name:
            continue
        source_kind = item.get("source_kind")
        if source_kind == "user_input":
            user_inputs.append(name)
        elif source_kind == "derived":
            derived_parameters.append(name)
        source = item.get("source") or {}
        source_id = source.get("source_id")
        if not source_id or source_id == "exposure_scenario_mcp":
            continue
        entry = references.setdefault(
            source_id,
            {
                "sourceId": source_id,
                "title": source.get("title"),
                "locator": source.get("locator"),
                "version": source.get("version"),
                "parameterNames": [],
                "defaultedParameterNames": [],
            },
        )
        if name not in entry["parameterNames"]:
            entry["parameterNames"].append(name)
        if item.get("default_applied") and name not in entry["defaultedParameterNames"]:
            entry["defaultedParameterNames"].append(name)
    sorted_references = sorted(references.values(), key=lambda item: item["sourceId"])
    return {
        "usedSccs": any("sccs" in item["sourceId"].lower() for item in sorted_references),
        "userInputParameters": sorted(user_inputs),
        "derivedParameters": sorted(derived_parameters),
        "externalReferences": sorted_references,
    }


def _equation_summary(payload: dict[str, Any]) -> dict[str, Any]:
    route = payload.get("route")
    route_metrics = payload.get("route_metrics", {})
    assumptions = _assumption_map(payload)
    body_weight = assumptions.get("body_weight_kg", {}).get(
        "value", payload.get("population_profile", {}).get("body_weight_kg")
    )
    concentration_fraction = assumptions.get("concentration_fraction", {}).get("value")
    use_amount = assumptions.get("use_amount_per_event", {}).get("value")
    use_events = assumptions.get("use_events_per_day", {}).get("value")
    chemical_mass = route_metrics.get("chemical_mass_mg_per_event")
    external_mass = route_metrics.get("external_mass_mg_per_day")
    normalized = payload.get("external_dose", {}).get("value")

    equations: dict[str, Any] = {
        "chemicalMassPerEvent": {
            "formula": "use_amount_per_event[g] * 1000 * concentration_fraction",
            "substitution": f"{use_amount} * 1000 * {concentration_fraction}",
            "result": chemical_mass,
            "unit": "mg/event",
        },
        "normalizedExternalDose": {
            "formula": "external_mass_mg_per_day / body_weight_kg",
            "substitution": f"{external_mass} / {body_weight}",
            "result": normalized,
            "unit": "mg/kg-day",
        },
    }

    if route == "dermal":
        retention = assumptions.get("retention_factor", {}).get("value")
        transfer = assumptions.get("transfer_efficiency", {}).get("value")
        surface_area = assumptions.get("exposed_surface_area_cm2", {}).get("value")
        equations["externalMassPerDay"] = {
            "formula": (
                "chemical_mass_mg_per_event * use_events_per_day * retention_factor * "
                "transfer_efficiency"
            ),
            "substitution": f"{chemical_mass} * {use_events} * {retention} * {transfer}",
            "result": external_mass,
            "unit": "mg/day",
        }
        if surface_area:
            equations["surfaceLoading"] = {
                "formula": "external_mass_mg_per_day / exposed_surface_area_cm2",
                "substitution": f"{external_mass} / {surface_area}",
                "result": route_metrics.get("surface_loading_mg_per_cm2_day"),
                "unit": "mg/cm2-day",
            }
    elif route == "oral":
        ingestion = assumptions.get("ingestion_fraction", {}).get("value")
        equations["externalMassPerDay"] = {
            "formula": "chemical_mass_mg_per_event * use_events_per_day * ingestion_fraction",
            "substitution": f"{chemical_mass} * {use_events} * {ingestion}",
            "result": external_mass,
            "unit": "mg/day",
        }
    return equations


def _scenario_summary(result: dict[str, Any]) -> dict[str, Any]:
    payload = result["structuredContent"]
    assumptions = payload.get("assumptions", [])
    defaulted = [item["name"] for item in assumptions if item.get("default_applied")]
    route_metrics = payload.get("route_metrics", {})
    return {
        "schemaVersion": payload.get("schema_version"),
        "scenarioId": payload.get("scenario_id"),
        "route": payload.get("route"),
        "scenarioClass": payload.get("scenario_class"),
        "chemicalId": payload.get("chemical_id"),
        "productName": payload.get("product_use_profile", {}).get("product_name"),
        "populationGroup": payload.get("population_profile", {}).get("population_group"),
        "region": payload.get("population_profile", {}).get("region"),
        "externalDose": payload.get("external_dose"),
        "assumptionCount": len(assumptions),
        "defaultedParameterNames": defaulted,
        "qualityFlagCount": len(_quality_flags(payload)),
        "limitationCount": len(payload.get("limitations", [])),
        "uncertaintyRegisterCount": len(_uncertainty_register(payload)),
        "fitForPurpose": _fit_for_purpose(payload),
        "provenance": payload.get("provenance", {}),
        "tierSemantics": _tier_semantics(payload),
        "referenceSummary": _reference_summary(payload),
        "equations": _equation_summary(payload),
        "routeMetricsExcerpt": {
            key: route_metrics[key]
            for key in [
                "chemical_mass_mg_per_event",
                "external_mass_mg_per_day",
                "surface_loading_mg_per_cm2_day",
                "dosage_unit_count_per_event",
                "chemical_mass_mg_per_unit",
                "near_field_peak_concentration_mg_per_m3",
                "far_field_peak_concentration_mg_per_m3",
                "saturation_cap_applied",
            ]
            if key in route_metrics
        },
    }


def _comparison_summary(result: dict[str, Any]) -> dict[str, Any]:
    payload = result["structuredContent"]
    dose_range = payload.get("doseRange", {})
    minimum = dose_range.get("minimumValue")
    maximum = dose_range.get("maximumValue")
    ratio = None
    if minimum not in (None, 0) and maximum is not None:
        ratio = maximum / minimum
    return {
        "schemaVersion": payload.get("schema_version"),
        "comparisonId": payload.get("comparisonId"),
        "jurisdictions": payload.get("comparedJurisdictions", []),
        "externalDoseByJurisdiction": payload.get("externalDoseByJurisdiction", {}),
        "doseRange": dose_range,
        "rangeRatio": ratio,
        "varianceDrivers": payload.get("varianceDrivers", []),
        "harmonizationOpportunity": payload.get("harmonizationOpportunity"),
        "qualityFlagCount": len(_quality_flags(payload)),
        "limitationCount": len(payload.get("limitations", [])),
        "fitForPurpose": _fit_for_purpose(payload),
        "uncertaintyRegisterCount": len(_uncertainty_register(payload)),
        "provenance": payload.get("provenance", {}),
    }


def _scenario_comparison_summary(
    result: dict[str, Any],
    baseline_payload: dict[str, Any] | None = None,
    comparison_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = result["structuredContent"]
    surface_loading_ratio = None
    if baseline_payload and comparison_payload:
        baseline_surface = baseline_payload.get("route_metrics", {}).get(
            "surface_loading_mg_per_cm2_day"
        )
        comparison_surface = comparison_payload.get("route_metrics", {}).get(
            "surface_loading_mg_per_cm2_day"
        )
        if baseline_surface not in (None, 0) and comparison_surface is not None:
            surface_loading_ratio = comparison_surface / baseline_surface
    return {
        "schemaVersion": payload.get("schema_version"),
        "baselineScenarioId": payload.get("baseline_scenario_id"),
        "comparisonScenarioId": payload.get("comparison_scenario_id"),
        "baselineDose": payload.get("baseline_dose"),
        "comparisonDose": payload.get("comparison_dose"),
        "absoluteDelta": payload.get("absolute_delta"),
        "percentDelta": payload.get("percent_delta"),
        "changedAssumptionCount": len(payload.get("changed_assumptions", [])),
        "changedAssumptions": payload.get("changed_assumptions", []),
        "interpretationNotes": payload.get("interpretation_notes", []),
        "surfaceLoadingRatio": surface_loading_ratio,
        "provenance": payload.get("provenance", {}),
    }


def _integrated_summary(result: dict[str, Any]) -> dict[str, Any]:
    payload = result["structuredContent"]
    pbpk_report = payload.get("pbpkCompatibilityReport", {})
    pbpk_input = payload.get("pbpkScenarioInput", {})
    return {
        "schemaVersion": payload.get("schema_version"),
        "chemicalId": payload.get("chemicalId"),
        "scenarioId": payload.get("scenario", {}).get("scenario_id"),
        "route": payload.get("scenario", {}).get("route"),
        "evidenceStrategy": payload.get("evidenceStrategy"),
        "selectedEvidenceSourceName": payload.get("selectedEvidenceSourceName"),
        "selectedEvidenceSourceKind": payload.get("selectedEvidenceSourceKind"),
        "manualReviewRequired": payload.get("manualReviewRequired"),
        "normalizedEvidenceRecordCount": len(payload.get("normalizedEvidenceRecords", [])),
        "qualityFlagCount": len(_quality_flags(payload)),
        "limitationCount": len(payload.get("limitations", [])),
        "pbpkCompatible": pbpk_report.get("compatible"),
        "readyForExternalPbpkImport": pbpk_report.get("ready_for_external_pbpk_import"),
        "pbpkDoseMagnitude": pbpk_input.get("dose_magnitude"),
        "pbpkDoseUnit": pbpk_input.get("dose_unit"),
        "pbpkRoute": pbpk_input.get("route"),
        "workflowNotes": payload.get("workflowNotes", []),
        "provenance": payload.get("provenance", {}),
    }


def _pbpk_export_summary(result: dict[str, Any]) -> dict[str, Any]:
    payload = result["structuredContent"]
    return {
        "schemaVersion": payload.get("schema_version"),
        "sourceScenarioId": payload.get("source_scenario_id"),
        "route": payload.get("route"),
        "doseMagnitude": payload.get("dose_magnitude"),
        "doseUnit": payload.get("dose_unit"),
        "doseMetric": payload.get("dose_metric"),
        "eventsPerDay": payload.get("events_per_day"),
        "timingPattern": payload.get("timing_pattern"),
        "populationContext": payload.get("population_context"),
        "supportingAssumptionCount": len(payload.get("supporting_assumption_names", [])),
        "supportingAssumptionNames": payload.get("supporting_assumption_names", []),
        "provenance": payload.get("provenance", {}),
    }


def _case_study_base_request() -> dict[str, Any]:
    payload = deepcopy(_read_json(ROOT / "schemas/examples/screening_dermal_request.json"))
    payload["product_use_profile"]["product_name"] = "Example Face Cream"
    payload["product_use_profile"]["product_subtype"] = "face_cream"
    return payload


def _case_study_evidence_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "sourceName": payload.get("source_name"),
        "sourceKind": payload.get("source_kind"),
        "sourceRecordId": payload.get("source_record_id"),
        "sourceLocator": payload.get("source_locator"),
        "productName": payload.get("product_name"),
        "productSubtype": payload.get("product_subtype"),
        "evidenceSources": payload.get("evidence_sources", []),
        "productUseProfileOverrides": payload.get("productUseProfileOverrides")
        or payload.get("product_use_profile_overrides", {}),
        "populationProfileOverrides": payload.get("populationProfileOverrides")
        or payload.get("population_profile_overrides", {}),
        "notes": payload.get("notes", []),
    }


def _fit_report_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": payload.get("schema_version"),
        "evidenceSourceName": payload.get("evidence_source_name"),
        "evidenceSourceKind": payload.get("evidence_source_kind"),
        "compatible": payload.get("compatible"),
        "autoApplySafe": payload.get("auto_apply_safe"),
        "recommendation": payload.get("recommendation"),
        "matchedFieldCount": len(payload.get("matched_fields", [])),
        "matchedFields": payload.get("matched_fields", []),
        "warningCount": len(payload.get("warnings", [])),
        "warnings": payload.get("warnings", []),
        "blockingIssueCount": len(payload.get("blocking_issues", [])),
        "blockingIssues": payload.get("blocking_issues", []),
        "suggestedUpdates": payload.get("suggested_updates", {}),
    }


def _applied_request_summary(payload: dict[str, Any]) -> dict[str, Any]:
    profile = payload.get("product_use_profile", {})
    population = payload.get("population_profile", {})
    assumption_overrides = payload.get("assumption_overrides", {})
    return {
        "productName": profile.get("product_name"),
        "productSubtype": profile.get("product_subtype"),
        "useAmountPerEvent": profile.get("use_amount_per_event"),
        "useAmountUnit": profile.get("use_amount_unit"),
        "useEventsPerDay": profile.get("use_events_per_day"),
        "bodyWeightKg": population.get("body_weight_kg"),
        "exposedSurfaceAreaCm2": population.get("exposed_surface_area_cm2"),
        "region": population.get("region"),
        "evidenceSourceName": assumption_overrides.get("external_product_use_source_name"),
        "evidenceSourceKind": assumption_overrides.get("external_product_use_source_kind"),
        "primaryEvidence": assumption_overrides.get("external_product_use_primary_evidence"),
    }


def _selected_domain_summary(
    validation_coverage: dict[str, Any], domain: str
) -> dict[str, Any] | None:
    for item in validation_coverage.get("domainSummaries", []):
        if item.get("domain") == domain:
            return {
                "domain": item.get("domain"),
                "coverageLevel": item.get("coverageLevel"),
                "highestSupportedUncertaintyTier": item.get("highestSupportedUncertaintyTier"),
                "benchmarkCaseCount": item.get("benchmarkCaseCount"),
                "benchmarkCaseIds": item.get("benchmarkCaseIds", []),
                "externalDatasetCount": item.get("externalDatasetCount"),
                "externalDatasetIds": item.get("externalDatasetIds", []),
                "executableReferenceBandCount": item.get("executableReferenceBandCount"),
                "executableReferenceBandIds": item.get("executableReferenceBandIds", []),
                "timeSeriesPackCount": item.get("timeSeriesPackCount"),
                "timeSeriesPackIds": item.get("timeSeriesPackIds", []),
                "openGapCount": item.get("openGapCount"),
                "openGapIds": item.get("openGapIds", []),
                "summary": item.get("summary"),
            }
    return None


def _benchmark_fixture_case(case_id: str) -> dict[str, Any]:
    benchmark_manifest = _read_json(ROOT / "tests/fixtures/benchmark_cases.json")
    for item in benchmark_manifest.get("cases", []):
        if item.get("id") == case_id:
            return item
    raise KeyError(f"Benchmark case not found: {case_id}")


def _goldset_case(case_id: str) -> dict[str, Any]:
    goldset_manifest = _read_json(ROOT / "tests/fixtures/goldset_cases.json")
    for item in goldset_manifest.get("cases", []):
        if item.get("id") == case_id:
            return item
    raise KeyError(f"Goldset case not found: {case_id}")


def _goldset_case_summary(case_id: str) -> dict[str, Any]:
    payload = _goldset_case(case_id)
    return {
        "id": payload.get("id"),
        "title": payload.get("title"),
        "coverageStatus": payload.get("coverage_status"),
        "benchmarkCaseIds": payload.get("benchmark_case_ids", []),
        "recognizableExamples": payload.get("recognizable_examples", []),
        "challengeTags": payload.get("challenge_tags", []),
        "whyItMatters": payload.get("why_it_matters"),
        "showcaseStory": payload.get("showcase_story"),
        "evidenceGaps": payload.get("evidence_gaps", []),
        "externalSources": payload.get("external_sources", []),
    }


def _published_reconciliation_example_summary() -> dict[str, Any]:
    payload = _read_json(ROOT / "schemas/examples/product_use_evidence_reconciliation_report.json")
    return {
        "chemicalId": payload.get("chemical_id"),
        "requestRegion": payload.get("request_region"),
        "consideredSources": payload.get("consideredSources", []),
        "compatibleSources": payload.get("compatibleSources", []),
        "recommendedSourceName": payload.get("recommendedSourceName"),
        "recommendedSourceKind": payload.get("recommendedSourceKind"),
        "recommendation": payload.get("recommendation"),
        "manualReviewRequired": payload.get("manualReviewRequired"),
        "conflicts": payload.get("conflicts", []),
        "rationale": payload.get("rationale", []),
    }


def _benchmark_replication_summary(
    benchmark_case: dict[str, Any],
    result_payload: dict[str, Any],
) -> dict[str, Any]:
    expected = benchmark_case.get("expected", {})
    actual_dose = result_payload.get("external_dose", {})
    expected_dose_value = expected.get("external_dose_value")
    actual_dose_value = actual_dose.get("value")
    absolute_delta = None
    relative_delta_pct = None
    if expected_dose_value is not None and actual_dose_value is not None:
        absolute_delta = actual_dose_value - expected_dose_value
        if expected_dose_value:
            relative_delta_pct = (absolute_delta / expected_dose_value) * 100.0

    route_metric_deltas: list[dict[str, Any]] = []
    actual_route_metrics = result_payload.get("route_metrics", {})
    for metric_name, expected_value in expected.get("route_metrics", {}).items():
        actual_value = actual_route_metrics.get(metric_name)
        absolute_metric_delta = None
        relative_metric_delta_pct = None
        if expected_value is not None and actual_value is not None:
            absolute_metric_delta = actual_value - expected_value
            if expected_value:
                relative_metric_delta_pct = (absolute_metric_delta / expected_value) * 100.0
        route_metric_deltas.append(
            {
                "metricName": metric_name,
                "expectedValue": expected_value,
                "actualValue": actual_value,
                "absoluteDelta": absolute_metric_delta,
                "relativeDeltaPct": relative_metric_delta_pct,
            }
        )

    return {
        "benchmarkCaseId": benchmark_case.get("id"),
        "description": benchmark_case.get("description"),
        "requestRoute": benchmark_case.get("request", {}).get("route"),
        "productName": benchmark_case.get("request", {})
        .get("product_use_profile", {})
        .get("product_name"),
        "expectedExternalDose": {
            "value": expected_dose_value,
            "unit": expected.get("external_dose_unit"),
        },
        "actualExternalDose": actual_dose,
        "absoluteDoseDelta": absolute_delta,
        "relativeDoseDeltaPct": relative_delta_pct,
        "routeMetricDeltas": route_metric_deltas,
        "allComparedValuesMatch": all(
            item.get("absoluteDelta") in (None, 0) for item in route_metric_deltas
        )
        and absolute_delta in (None, 0),
    }


async def _collect_sccs_face_cream_case_study(
    session: ClientSession,
    artifacts_dir: Path,
) -> dict[str, Any]:
    base_request = _case_study_base_request()
    raw_record = _read_json(ROOT / "schemas/examples/sccs_evidence_record.json")
    _write_json(artifacts_dir / "160_sccs_face_cream_base_request.json", base_request)
    _write_json(artifacts_dir / "162_sccs_face_cream_raw_record.json", raw_record)

    baseline_result = await session.call_tool(
        "exposure_build_screening_exposure_scenario",
        {"params": base_request},
    )
    evidence_result = await session.call_tool(
        "exposure_build_product_use_evidence_from_sccs",
        {"params": {"evidence": raw_record}},
    )
    fit_result = await session.call_tool(
        "exposure_assess_product_use_evidence_fit",
        {
            "params": {
                "request": base_request,
                "evidence": evidence_result.structuredContent,
            }
        },
    )
    applied_request_result = await session.call_tool(
        "exposure_apply_product_use_evidence",
        {
            "params": {
                "request": base_request,
                "evidence": evidence_result.structuredContent,
                "require_auto_apply_safe": False,
            }
        },
    )
    scenario_result = await session.call_tool(
        "exposure_build_screening_exposure_scenario",
        {"params": applied_request_result.structuredContent},
    )
    compare_result = await session.call_tool(
        "exposure_compare_exposure_scenarios",
        {
            "params": {
                "baseline": baseline_result.structuredContent,
                "comparison": scenario_result.structuredContent,
            }
        },
    )
    pbpk_request = {
        "scenario": scenario_result.structuredContent,
        "regimen_name": "screening_daily_use",
        "includeTransientConcentrationProfile": False,
    }
    pbpk_result = await session.call_tool(
        "exposure_export_pbpk_scenario_input",
        {"params": pbpk_request},
    )

    for filename, result in [
        ("161_sccs_face_cream_baseline_result.json", baseline_result),
        ("163_sccs_face_cream_evidence_result.json", evidence_result),
        ("164_sccs_face_cream_fit_result.json", fit_result),
        ("165_sccs_face_cream_applied_request.json", applied_request_result),
        ("166_sccs_face_cream_scenario_result.json", scenario_result),
        ("167_sccs_face_cream_compare_result.json", compare_result),
        ("169_sccs_face_cream_pbpk_export_result.json", pbpk_result),
    ]:
        _write_json(artifacts_dir / filename, result.model_dump(mode="json"))
    _write_json(artifacts_dir / "168_sccs_face_cream_pbpk_export_request.json", pbpk_request)

    baseline_payload = baseline_result.structuredContent
    scenario_payload = scenario_result.structuredContent
    return {
        "title": "EU SCCS Face Cream Evidence Application",
        "baselineRequest": {
            "productName": base_request["product_use_profile"]["product_name"],
            "productSubtype": base_request["product_use_profile"]["product_subtype"],
            "useAmountPerEvent": base_request["product_use_profile"]["use_amount_per_event"],
            "useEventsPerDay": base_request["product_use_profile"]["use_events_per_day"],
            "region": base_request["population_profile"]["region"],
        },
        "reviewedEvidence": {
            "guidanceId": raw_record.get("guidanceId"),
            "guidanceTitle": raw_record.get("guidanceTitle"),
            "guidanceVersion": raw_record.get("guidanceVersion"),
            "guidanceLocator": raw_record.get("guidanceLocator"),
            "tableReferences": raw_record.get("tableReferences", []),
            "evidenceSources": raw_record.get("evidence_sources", []),
        },
        "mappedEvidence": _case_study_evidence_summary(evidence_result.structuredContent),
        "fitReport": _fit_report_summary(fit_result.structuredContent),
        "appliedRequest": _applied_request_summary(applied_request_result.structuredContent),
        "baselineScenario": _scenario_summary(baseline_result.model_dump(mode="json")),
        "finalScenario": _scenario_summary(scenario_result.model_dump(mode="json")),
        "comparisonToBaseline": _scenario_comparison_summary(
            compare_result.model_dump(mode="json"),
            baseline_payload=baseline_payload,
            comparison_payload=scenario_payload,
        ),
        "pbpkExport": _pbpk_export_summary(pbpk_result.model_dump(mode="json")),
    }


async def _collect_tier1_benchmark_replication(
    session: ClientSession,
    artifacts_dir: Path,
) -> dict[str, Any]:
    benchmark_case = _benchmark_fixture_case(
        "inhalation_tier1_disinfectant_trigger_spray_external_2015"
    )
    request_payload = benchmark_case["request"]
    _write_json(artifacts_dir / "170_benchmark_tier1_disinfectant_request.json", request_payload)

    result = await session.call_tool(
        "exposure_build_inhalation_tier1_screening_scenario",
        {"params": request_payload},
    )
    _write_json(
        artifacts_dir / "171_benchmark_tier1_disinfectant_result.json",
        result.model_dump(mode="json"),
    )

    comparison_summary = _benchmark_replication_summary(benchmark_case, result.structuredContent)
    _write_json(
        artifacts_dir / "172_benchmark_tier1_disinfectant_comparison.json", comparison_summary
    )
    return comparison_summary


async def _collect_live_artifacts(showcase_dir: Path, server_url: str, server_command: str) -> None:
    artifacts_dir = showcase_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    git_info = _git_info()
    collected_at = datetime.now(UTC).isoformat()

    async with (
        streamablehttp_client(server_url) as (
            read_stream,
            write_stream,
            _session_id,
        ),
        ClientSession(read_stream, write_stream) as session,
    ):
        initialize_result = await session.initialize()
        list_tools_result = await session.list_tools()
        list_resources_result = await session.list_resources()
        list_prompts_result = await session.list_prompts()

        _write_json(
            artifacts_dir / "010_initialize.json",
            initialize_result.model_dump(mode="json"),
        )
        surface_inventory = {
            "toolCount": len(list_tools_result.tools),
            "resourceCount": len(list_resources_result.resources),
            "promptCount": len(list_prompts_result.prompts),
            "toolNames": [tool.name for tool in list_tools_result.tools],
            "resourceUris": [str(resource.uri) for resource in list_resources_result.resources],
            "promptNames": [prompt.name for prompt in list_prompts_result.prompts],
        }
        _write_json(artifacts_dir / "020_surface_inventory.json", surface_inventory)

        for filename, uri in RESOURCE_URIS.items():
            resource_result = await session.read_resource(uri)
            payload = json.loads(_extract_resource_text(resource_result))
            _write_json(artifacts_dir / filename, payload)

        for run in TOOL_RUNS:
            request_artifact = artifacts_dir / run["request_artifact"]
            if run["request_file"] == "NONE":
                request_payload: dict[str, Any] = {}
            else:
                request_payload = _read_json(ROOT / run["request_file"])
            if run["tool_name"] == "exposure_compare_jurisdictional_scenarios":
                request_payload["jurisdictions"] = ["global", "eu", "china"]
            _write_json(request_artifact, request_payload)
            tool_result = await session.call_tool(
                run["tool_name"],
                {"params": request_payload} if request_payload else {},
            )
            _write_json(
                artifacts_dir / run["result_artifact"],
                tool_result.model_dump(mode="json"),
            )

        sccs_face_cream_case_study = await _collect_sccs_face_cream_case_study(
            session,
            artifacts_dir,
        )
        await _collect_tier1_benchmark_replication(session, artifacts_dir)

    run_metadata = {
        "generatedAtUtc": collected_at,
        "repoPath": str(ROOT),
        "showcaseDir": str(showcase_dir),
        "artifactsDir": str(artifacts_dir),
        "serverUrl": server_url,
        "serverCommand": server_command,
        "git": git_info,
    }
    _write_json(artifacts_dir / "000_run_metadata.json", run_metadata)

    release_metadata = _read_json(artifacts_dir / "051_release_metadata_report.json")
    defaults_manifest = _read_json(artifacts_dir / "040_defaults_manifest.json")
    verification_resource = _read_json(artifacts_dir / "050_verification_summary.json")
    validation_coverage = _read_json(artifacts_dir / "054_validation_coverage_report.json")
    contracts_manifest = _read_json(artifacts_dir / "030_contracts_manifest.json")
    initialize_payload = _read_json(artifacts_dir / "010_initialize.json")
    dermal_result = _read_json(artifacts_dir / "101_screening_dermal_result.json")
    oral_result = _read_json(artifacts_dir / "111_direct_oral_result.json")
    inhalation_result = _read_json(artifacts_dir / "121_inhalation_tier1_result.json")
    comparison_result = _read_json(artifacts_dir / "131_jurisdiction_compare_result.json")
    integrated_result = _read_json(artifacts_dir / "141_integrated_workflow_result.json")
    verification_tool_result = _read_json(artifacts_dir / "151_verification_checks_result.json")
    tier1_benchmark_replication = _read_json(
        artifacts_dir / "172_benchmark_tier1_disinfectant_comparison.json"
    )

    validation_domain_highlights = [
        item
        for item in [
            _selected_domain_summary(validation_coverage, "dermal_direct_application"),
            _selected_domain_summary(validation_coverage, "oral_direct_intake"),
            _selected_domain_summary(validation_coverage, "inhalation_near_field_far_field"),
            _selected_domain_summary(validation_coverage, "pbpk_external_handoff"),
        ]
        if item is not None
    ]
    face_cream_goldset = _goldset_case_summary("consumer_face_cream_sccs_guidance_alignment")
    disinfectant_goldset = _goldset_case_summary(
        "consumer_disinfectant_trigger_spray_tier1_monitoring"
    )
    published_reconciliation_example = _published_reconciliation_example_summary()

    initialize_server_info = initialize_payload.get("serverInfo", {})
    version_alignment = {
        "initializeServerVersion": initialize_server_info.get("version"),
        "releaseVersion": release_metadata.get("releaseVersion"),
        "packageVersion": release_metadata.get("packageVersion"),
        "matchesReleasePackageVersion": initialize_server_info.get("version")
        == release_metadata.get("packageVersion"),
    }

    summary = {
        "generatedAtUtc": collected_at,
        "repoPath": str(ROOT),
        "serverUrl": server_url,
        "serverCommand": server_command,
        "git": git_info,
        "runtime": {
            "serverName": initialize_server_info.get("name"),
            "initializeServerVersion": initialize_server_info.get("version"),
            "protocolVersion": initialize_payload.get("protocolVersion"),
            "releaseVersion": release_metadata.get("releaseVersion"),
            "packageVersion": release_metadata.get("packageVersion"),
            "defaultsVersion": defaults_manifest.get("defaults_version"),
            "defaultsHashSha256": defaults_manifest.get("defaults_hash_sha256"),
            "toolCount": len(contracts_manifest.get("tools", [])),
            "resourceCount": len(contracts_manifest.get("resources", [])),
            "promptCount": len(contracts_manifest.get("prompts", [])),
            "schemaCount": len(contracts_manifest.get("schemas", [])),
            "exampleCount": len(contracts_manifest.get("examples", [])),
        },
        "versionAlignment": version_alignment,
        "trust": {
            "verificationStatus": verification_resource.get("status"),
            "verificationSummary": verification_resource.get("summary"),
            "releaseReadinessStatus": verification_resource.get("releaseReadinessStatus"),
            "securityReviewStatus": verification_resource.get("securityReviewStatus"),
            "validationDomainCount": verification_resource.get("validationDomainCount"),
            "benchmarkCaseCount": verification_resource.get("benchmarkCaseCount"),
            "goldsetCaseCount": verification_resource.get("goldsetCaseCount"),
            "externalDatasetCount": validation_coverage.get("externalDatasetCount"),
            "referenceBandCount": validation_coverage.get("referenceBandCount"),
            "timeSeriesPackCount": validation_coverage.get("timeSeriesPackCount"),
            "supportedRegions": defaults_manifest.get("supported_regions", []),
            "validationDomainHighlights": validation_domain_highlights,
            "benchmarkShowcases": [face_cream_goldset, disinfectant_goldset],
            "benchmarkReplication": tier1_benchmark_replication,
            "publishedEvidenceReconciliationExample": published_reconciliation_example,
            "toolMetaExample": verification_tool_result.get("meta"),
        },
        "examples": {
            "dermalScreening": _scenario_summary(dermal_result),
            "oralDirectUse": _scenario_summary(oral_result),
            "inhalationTier1": _scenario_summary(inhalation_result),
            "jurisdictionComparison": _comparison_summary(comparison_result),
            "integratedWorkflow": _integrated_summary(integrated_result),
        },
        "caseStudy": sccs_face_cream_case_study,
        "artifactIndexFile": "artifact_index.json",
    }
    _write_json(showcase_dir / "showcase_summary.json", summary)

    artifact_index = []
    for path in sorted(artifacts_dir.glob("*.json")):
        artifact_index.append(
            {
                "file": str(path.relative_to(showcase_dir)),
                "description": ARTIFACT_DESCRIPTIONS.get(path.name, ""),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    _write_json(showcase_dir / "artifact_index.json", artifact_index)


def main() -> None:
    args = _parse_args()
    asyncio.run(
        _collect_live_artifacts(
            showcase_dir=args.showcase_dir.resolve(),
            server_url=args.server_url,
            server_command=args.server_command,
        )
    )


if __name__ == "__main__":
    main()
