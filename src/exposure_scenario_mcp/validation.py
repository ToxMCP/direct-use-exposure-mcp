"""Validation posture and benchmark-domain metadata."""

from __future__ import annotations

from exposure_scenario_mcp.benchmarks import load_benchmark_manifest
from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.models import (
    ExposureScenario,
    ExternalValidationDataset,
    ExternalValidationDatasetStatus,
    Route,
    TierLevel,
    UncertaintyTier,
    ValidationBenchmarkDomain,
    ValidationDossierReport,
    ValidationEvidenceReadiness,
    ValidationGap,
    ValidationGapSeverity,
    ValidationStatus,
    ValidationSummary,
)

BENCHMARK_CASE_DOMAINS = {
    "dermal_hand_cream_screening": "dermal_direct_application",
    "dermal_density_precedence_volume_case": "dermal_direct_application",
    "oral_direct_oral_screening": "oral_direct_intake",
    "inhalation_trigger_spray_screening": "inhalation_well_mixed_spray",
    "inhalation_tier1_trigger_spray_nf_ff": "inhalation_near_field_far_field",
    "inhalation_tier1_scenario_package_probability": "inhalation_near_field_far_field",
    "cross_route_aggregate_summary": "aggregate_cross_route_screening",
    "zero_baseline_comparison": "scenario_delta_comparison",
    "dermal_pbpk_export": "pbpk_external_handoff",
    "dermal_pbpk_external_import_package": "pbpk_external_handoff",
}

BENCHMARK_DOMAIN_NOTES = {
    "dermal_direct_application": [
        (
            "Current executable coverage is deterministic benchmark regression rather "
            "than external calibration."
        )
    ],
    "oral_direct_intake": [
        (
            "Current executable coverage verifies direct-intake screening arithmetic "
            "but does not yet benchmark distributional use factors."
        )
    ],
    "inhalation_well_mixed_spray": [
        (
            "Current benchmark coverage protects the Tier 0 room-average spray path "
            "against numeric drift."
        )
    ],
    "inhalation_near_field_far_field": [
        (
            "Current benchmark coverage includes both a single Tier 1 NF/FF scenario "
            "and a Tier C package built from governed Tier 1 support points."
        )
    ],
    "aggregate_cross_route_screening": [
        (
            "Aggregate validation remains bookkeeping-oriented until a broader "
            "population engine and external proxies are wired in."
        )
    ],
    "pbpk_external_handoff": [
        (
            "These benchmarks verify handoff semantics and request-shape fidelity, "
            "not PBPK model correctness."
        )
    ],
}

EXTERNAL_DATASET_CANDIDATES = [
    ExternalValidationDataset(
        datasetId="air_chamber_spray_time_series_candidate",
        domain="inhalation_well_mixed_spray",
        status=ExternalValidationDatasetStatus.CANDIDATE_ONLY,
        observable="air concentration time series",
        targetMetrics=["average_air_concentration_mg_per_m3", "inhaled_mass_mg_per_day"],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["household_cleaner", "personal_care"],
        note=(
            "Candidate family for future external validation of Tier 0 spray or volatilization "
            "microenvironment models."
        ),
    ),
    ExternalValidationDataset(
        datasetId="near_field_far_field_spray_candidate",
        domain="inhalation_near_field_far_field",
        status=ExternalValidationDatasetStatus.CANDIDATE_ONLY,
        observable="near-field and far-field concentration time series",
        targetMetrics=[
            "near_field_active_spray_concentration_mg_per_m3",
            "far_field_average_air_concentration_mg_per_m3",
            "breathing_zone_time_weighted_average_mg_per_m3",
        ],
        applicableTierClaims=[TierLevel.TIER_1],
        productFamilies=["household_cleaner", "personal_care"],
        note=(
            "Candidate family for future validation of Tier 1 near-field/far-field spray "
            "screening models."
        ),
    ),
    ExternalValidationDataset(
        datasetId="dermal_surface_loading_candidate",
        domain="dermal_direct_application",
        status=ExternalValidationDatasetStatus.CANDIDATE_ONLY,
        observable="surface loading or transfer recovery",
        targetMetrics=["external_mass_mg_per_day", "surface_loading_mg_per_cm2_day"],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["personal_care", "household_cleaner"],
        note=(
            "Candidate family for future external validation of dermal transfer and removal "
            "assumptions."
        ),
    ),
    ExternalValidationDataset(
        datasetId="direct_oral_liquid_regimen_candidate",
        domain="oral_direct_intake",
        status=ExternalValidationDatasetStatus.CANDIDATE_ONLY,
        observable="dispensed amount or dose recovery",
        targetMetrics=["chemical_mass_mg_per_event", "external_mass_mg_per_day"],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["medicinal_liquid"],
        note=(
            "Candidate family for future direct-oral screening validation using dispensed "
            "amount and regimen recovery observations."
        ),
    ),
    ExternalValidationDataset(
        datasetId="aggregate_external_proxy_candidate",
        domain="aggregate_cross_route_screening",
        status=ExternalValidationDatasetStatus.CANDIDATE_ONLY,
        observable="environmental or biomonitoring proxy comparison",
        targetMetrics=["normalized_total_external_dose"],
        applicableTierClaims=[TierLevel.TIER_0, TierLevel.TIER_1],
        productFamilies=["mixed_use"],
        note=(
            "Candidate family for future cross-route aggregate validation once a population "
            "engine exists."
        ),
    ),
]


def _heuristic_source_ids(registry: DefaultsRegistry) -> list[str]:
    return sorted(
        source["source_id"]
        for source in registry.payload.get("sources", [])
        if str(source.get("source_id", "")).startswith("heuristic_")
    )


def _open_validation_gaps(registry: DefaultsRegistry) -> list[ValidationGap]:
    heuristic_source_ids = _heuristic_source_ids(registry)
    gaps = [
        ValidationGap(
            gapId="tier1_nf_ff_external_validation_candidate_only",
            title="Tier 1 NF/FF external validation remains candidate-only",
            severity=ValidationGapSeverity.HIGH,
            appliesToDomains=["inhalation_near_field_far_field"],
            relatedSourceIds=["benchmark_tier1_nf_ff_parameter_pack_v1"],
            note=(
                "Tier 1 NF/FF spray screening now has executable benchmark coverage, but "
                "external dataset linkage remains at the candidate stage."
            ),
            recommendation=(
                "Prioritize chamber or breathing-zone datasets with time-series coverage for "
                "near-field and far-field concentrations in personal-care and cleaner "
                "spray contexts."
            ),
        ),
        ValidationGap(
            gapId="tier0_spray_external_validation_candidate_only",
            title="Tier 0 spray external validation remains candidate-only",
            severity=ValidationGapSeverity.MEDIUM,
            appliesToDomains=["inhalation_well_mixed_spray"],
            relatedSourceIds=["heuristic_screening_defaults_v1"],
            note=(
                "Tier 0 spray screening is benchmark-regressed, but room-average spray "
                "validation still depends on candidate external datasets."
            ),
            recommendation=(
                "Add external chamber or room-concentration datasets before promoting spray "
                "screening defaults beyond benchmark-level evidence."
            ),
        ),
        ValidationGap(
            gapId="dermal_transfer_external_validation_candidate_only",
            title="Dermal transfer and retention validation remains candidate-only",
            severity=ValidationGapSeverity.MEDIUM,
            appliesToDomains=["dermal_direct_application", "dermal_secondary_transfer"],
            relatedSourceIds=["heuristic_screening_defaults_v1"],
            note=(
                "Dermal direct-application arithmetic is benchmarked, but transfer and "
                "retention factors still depend on candidate external validation families."
            ),
            recommendation=(
                "Replace transfer and retention heuristics with curated packs tied to product "
                "family and route-specific external recovery datasets."
            ),
        ),
        ValidationGap(
            gapId="oral_regimen_external_validation_candidate_only",
            title="Direct-oral regimen validation remains candidate-only",
            severity=ValidationGapSeverity.MEDIUM,
            appliesToDomains=["oral_direct_intake"],
            relatedSourceIds=["heuristic_screening_defaults_v1"],
            note=(
                "Direct-oral screening is benchmarked internally, but external regimen or "
                "dispensed-amount validation is still only planned."
            ),
            recommendation=(
                "Add observed dosing or dispensed-amount datasets before broadening the "
                "direct-oral evidence posture."
            ),
        ),
        ValidationGap(
            gapId="heuristic_defaults_active",
            title="Heuristic defaults remain active in the screening registry",
            severity=ValidationGapSeverity.HIGH,
            appliesToDomains=["global"],
            relatedSourceIds=heuristic_source_ids,
            note=(
                "Some screening factor families still resolve from heuristic defaults rather "
                "than curated, evidence-linked source packs."
            ),
            recommendation=(
                "Prioritize curated replacements for transfer efficiency, retention, density, "
                "aerosolization, and regional room defaults."
            ),
        ),
    ]
    return gaps


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
    if scenario.tier_semantics.tier_claimed.value == "tier_1":
        return "inhalation_near_field_far_field"
    if profile.application_method in {"trigger_spray", "pump_spray", "aerosol_spray"}:
        return "inhalation_well_mixed_spray"
    return "inhalation_room_average"


def build_validation_dossier_report(
    registry: DefaultsRegistry | None = None,
) -> ValidationDossierReport:
    active_registry = registry or DefaultsRegistry.load()
    fixture = load_benchmark_manifest()
    benchmark_domains: dict[str, list[str]] = {}
    for case in fixture.get("cases", []):
        domain = BENCHMARK_CASE_DOMAINS.get(case["id"], "unclassified")
        benchmark_domains.setdefault(domain, []).append(case["id"])
    domains = [
        ValidationBenchmarkDomain(
            domain=domain,
            caseIds=sorted(case_ids),
            validationStatus=ValidationStatus.BENCHMARK_REGRESSION,
            highestSupportedUncertaintyTier=(
                UncertaintyTier.TIER_C
                if domain == "inhalation_near_field_far_field"
                else UncertaintyTier.TIER_B
            ),
            notes=BENCHMARK_DOMAIN_NOTES.get(domain, []),
        )
        for domain, case_ids in sorted(benchmark_domains.items())
    ]
    return ValidationDossierReport(
        policyVersion="2026.03.25.v2",
        benchmarkDomains=domains,
        externalDatasets=EXTERNAL_DATASET_CANDIDATES,
        heuristicSourceIds=_heuristic_source_ids(active_registry),
        openGaps=_open_validation_gaps(active_registry),
        notes=[
            (
                "Current validation posture is benchmark regression plus verification, "
                "with typed external-dataset candidates and open gap tracking."
            ),
            "No external validation datasets are wired into executable scoring yet.",
            (
                "Tier 1 inhalation NF/FF screening is implemented for spray scenarios, but "
                "external validation remains a governed future capability rather than "
                "an active pass gate."
            ),
            (
                "Probabilistic tiers remain gated until dependency handling and "
                "external validation mature."
            ),
        ],
    )


def validation_manifest() -> dict:
    return build_validation_dossier_report().model_dump(mode="json", by_alias=True)


def _evidence_readiness(
    benchmark_case_ids: list[str],
    datasets: list[ExternalValidationDataset],
) -> ValidationEvidenceReadiness:
    statuses = {item.status for item in datasets}
    if ExternalValidationDatasetStatus.ACCEPTED_REFERENCE in statuses:
        return ValidationEvidenceReadiness.CALIBRATED
    if ExternalValidationDatasetStatus.PARTIAL in statuses:
        return ValidationEvidenceReadiness.EXTERNAL_PARTIAL
    if benchmark_case_ids and datasets:
        return ValidationEvidenceReadiness.BENCHMARK_PLUS_EXTERNAL_CANDIDATES
    return ValidationEvidenceReadiness.BENCHMARK_ONLY


def _scenario_validation_gap_ids(
    route_mechanism: str,
    *,
    heuristic_assumption_names: list[str],
    dossier: ValidationDossierReport,
) -> list[str]:
    gap_ids: list[str] = []
    for gap in dossier.open_gaps:
        if gap.gap_id == "heuristic_defaults_active" and not heuristic_assumption_names:
            continue
        if "global" in gap.applies_to_domains or route_mechanism in gap.applies_to_domains:
            gap_ids.append(gap.gap_id)
    return gap_ids


def build_validation_summary(scenario: ExposureScenario) -> ValidationSummary:
    route_mechanism = infer_route_mechanism(scenario)
    dossier = build_validation_dossier_report()
    benchmark_case_ids: list[str] = []
    highest_supported_tier = UncertaintyTier.TIER_B
    for item in dossier.benchmark_domains:
        if item.domain == route_mechanism:
            benchmark_case_ids = list(item.case_ids)
            highest_supported_tier = item.highest_supported_uncertainty_tier
            break
    matched_datasets = [
        item for item in dossier.external_datasets if item.domain == route_mechanism
    ]
    external_dataset_ids = [item.dataset_id for item in matched_datasets]
    heuristic_assumption_names = sorted(
        item.name
        for item in scenario.assumptions
        if item.source.source_id.startswith("heuristic_")
    )
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
        evidence_readiness=_evidence_readiness(benchmark_case_ids, matched_datasets),
        heuristic_assumption_names=heuristic_assumption_names,
        validation_gap_ids=_scenario_validation_gap_ids(
            route_mechanism,
            heuristic_assumption_names=heuristic_assumption_names,
            dossier=dossier,
        ),
        highest_supported_uncertainty_tier=highest_supported_tier,
        probabilistic_enablement="blocked",
        notes=[
            "Deterministic verification and benchmark regression are available for this domain.",
            (
                "External validation remains a documented future capability rather than "
                "an active gate."
            ),
            (
                "Heuristic assumption names are emitted explicitly so evidence gaps stay "
                "attached to the scenario rather than hidden in source packs."
            ),
            (
                "Probabilistic outputs stay disabled until dependencies and validation "
                "evidence mature."
            ),
        ],
    )
