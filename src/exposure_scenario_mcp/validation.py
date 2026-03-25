"""Validation posture and benchmark-domain metadata."""

from __future__ import annotations

from exposure_scenario_mcp.benchmarks import load_benchmark_manifest
from exposure_scenario_mcp.models import (
    ExposureScenario,
    Route,
    UncertaintyTier,
    ValidationStatus,
    ValidationSummary,
)

BENCHMARK_CASE_DOMAINS = {
    "dermal_hand_cream_screening": "dermal_direct_application",
    "dermal_density_precedence_volume_case": "dermal_direct_application",
    "oral_direct_oral_screening": "oral_direct_intake",
    "inhalation_trigger_spray_screening": "inhalation_well_mixed_spray",
    "cross_route_aggregate_summary": "aggregate_cross_route_screening",
    "zero_baseline_comparison": "scenario_delta_comparison",
    "dermal_pbpk_export": "pbpk_external_handoff",
    "dermal_pbpk_external_import_package": "pbpk_external_handoff",
}

EXTERNAL_DATASET_CANDIDATES = [
    {
        "datasetId": "air_chamber_spray_time_series_candidate",
        "domain": "inhalation_well_mixed_spray",
        "status": "candidate_only",
        "observable": "air concentration time series",
        "note": (
            "Candidate family for future external validation of spray or volatilization "
            "microenvironment models."
        ),
    },
    {
        "datasetId": "dermal_surface_loading_candidate",
        "domain": "dermal_direct_application",
        "status": "candidate_only",
        "observable": "surface loading or transfer recovery",
        "note": (
            "Candidate family for future external validation of dermal transfer and removal "
            "assumptions."
        ),
    },
    {
        "datasetId": "aggregate_external_proxy_candidate",
        "domain": "aggregate_cross_route_screening",
        "status": "candidate_only",
        "observable": "environmental or biomonitoring proxy comparison",
        "note": (
            "Candidate family for future cross-route aggregate validation once a population "
            "engine exists."
        ),
    },
]


def infer_route_mechanism(scenario: ExposureScenario) -> str:
    profile = scenario.product_use_profile
    if scenario.route == Route.DERMAL:
        if profile.application_method == "wipe":
            return "dermal_secondary_transfer"
        return "dermal_direct_application"
    if scenario.route == Route.ORAL:
        if profile.application_method == "incidental_oral":
            return "oral_incidental_transfer"
        return "oral_direct_intake"
    if profile.application_method in {"trigger_spray", "pump_spray", "aerosol_spray"}:
        return "inhalation_well_mixed_spray"
    return "inhalation_room_average"


def validation_manifest() -> dict:
    fixture = load_benchmark_manifest()
    benchmark_domains: dict[str, list[str]] = {}
    for case in fixture.get("cases", []):
        domain = BENCHMARK_CASE_DOMAINS.get(case["id"], "unclassified")
        benchmark_domains.setdefault(domain, []).append(case["id"])
    return {
        "policyVersion": "2026.03.25.v1",
        "benchmarkDomains": [
            {
                "domain": domain,
                "caseIds": sorted(case_ids),
                "validationStatus": "benchmark_regression",
                "highestSupportedUncertaintyTier": "tier_b",
            }
            for domain, case_ids in sorted(benchmark_domains.items())
        ],
        "externalDatasets": EXTERNAL_DATASET_CANDIDATES,
        "notes": [
            "Current v0.1 validation posture is benchmark regression plus verification.",
            "No external validation datasets are wired into executable scoring yet.",
            (
                "Probabilistic tiers remain gated until dependency handling and "
                "external validation mature."
            ),
        ],
    }


def build_validation_summary(scenario: ExposureScenario) -> ValidationSummary:
    route_mechanism = infer_route_mechanism(scenario)
    manifest = validation_manifest()
    benchmark_case_ids: list[str] = []
    for item in manifest["benchmarkDomains"]:
        if item["domain"] == route_mechanism:
            benchmark_case_ids = list(item["caseIds"])
            break
    external_dataset_ids = [
        item["datasetId"]
        for item in EXTERNAL_DATASET_CANDIDATES
        if item["domain"] == route_mechanism
    ]
    validation_status = (
        ValidationStatus.BENCHMARK_REGRESSION
        if benchmark_case_ids
        else ValidationStatus.VERIFICATION_ONLY
    )
    return ValidationSummary(
        validation_status=validation_status,
        route_mechanism=route_mechanism,
        benchmark_case_ids=benchmark_case_ids,
        external_dataset_ids=external_dataset_ids,
        highest_supported_uncertainty_tier=UncertaintyTier.TIER_B,
        probabilistic_enablement="blocked",
        notes=[
            "Deterministic verification and benchmark regression are available for this domain.",
            (
                "External validation remains a documented future capability rather than "
                "an active gate."
            ),
            (
                "Probabilistic outputs stay disabled until dependencies and validation "
                "evidence mature."
            ),
        ],
    )
