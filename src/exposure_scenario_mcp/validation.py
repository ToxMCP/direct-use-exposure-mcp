"""Validation posture and benchmark-domain metadata."""

from __future__ import annotations

from exposure_scenario_mcp.benchmarks import load_benchmark_manifest
from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.models import (
    ExecutedValidationCheck,
    ExposureScenario,
    ExternalValidationDataset,
    ExternalValidationDatasetStatus,
    Route,
    TierLevel,
    UncertaintyTier,
    ValidationBenchmarkDomain,
    ValidationCheckStatus,
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

HAND_CREAM_LOADING_REFERENCE_LOWER = 0.37
HAND_CREAM_LOADING_REFERENCE_UPPER = 1.57
WET_CLOTH_CONTACT_REFERENCE_LOWER = 0.31
WET_CLOTH_CONTACT_REFERENCE_UPPER = 0.62

EXTERNAL_VALIDATION_DATASETS = [
    ExternalValidationDataset(
        datasetId="cleaning_trigger_spray_airborne_mass_fraction_2019",
        domain="inhalation_well_mixed_spray",
        status=ExternalValidationDatasetStatus.PARTIAL,
        observable="total airborne mass fraction and aerosol size distribution",
        targetMetrics=["aerosolized_fraction", "average_air_concentration_mg_per_m3"],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["household_cleaner"],
        referenceTitle=(
            "Characterization of airborne particles from cleaning sprays and their "
            "corresponding respiratory deposition fractions"
        ),
        referenceLocator="https://pubmed.ncbi.nlm.nih.gov/31361572/",
        note=(
            "Seven ready-to-use trigger cleaning sprays produced total airborne mass "
            "fractions between 2.7% and 32.2% of emitted mass. This is a useful emission-side "
            "anchor for Tier 0 spray screening, but it is not a full executable "
            "scenario-to-dose calibration set."
        ),
    ),
    ExternalValidationDataset(
        datasetId="consumer_spray_inhalation_exposure_2015",
        domain="inhalation_near_field_far_field",
        status=ExternalValidationDatasetStatus.PARTIAL,
        observable="breathing-zone inhalation exposure and deposited dose during spray use",
        targetMetrics=[
            "breathing_zone_time_weighted_average_mg_per_m3",
            "inhaled_mass_mg_per_day",
        ],
        applicableTierClaims=[TierLevel.TIER_1],
        productFamilies=["household_cleaner", "personal_care"],
        referenceTitle=(
            "Quantitative assessment of inhalation exposure and deposited dose of aerosol "
            "from nanotechnology-based consumer sprays"
        ),
        referenceLocator="https://pmc.ncbi.nlm.nih.gov/articles/PMC4303255/",
        note=(
            "Mannequin-head sampling under realistic consumer spray application reported "
            "product-specific inhalation exposure and deposited-dose ranges. This is useful "
            "for near-field burden checks, but it is not a direct calibration dataset for "
            "the MCP NF/FF mass-balance solver."
        ),
    ),
    ExternalValidationDataset(
        datasetId="skin_protection_cream_dose_per_area_2012",
        domain="dermal_direct_application",
        status=ExternalValidationDatasetStatus.PARTIAL,
        observable="applied product mass per hand surface area in workplace use",
        targetMetrics=["use_amount_per_event", "surface_loading_mg_per_cm2_day"],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["personal_care"],
        referenceTitle=(
            "How much skin protection cream is actually applied in the workplace? "
            "Determination of dose per skin surface area in nurses"
        ),
        referenceLocator="https://pubmed.ncbi.nlm.nih.gov/22709142/",
        note=(
            "Observed mean skin-protection-cream dose was 0.97 ± 0.6 mg/cm² across 31 nurses "
            "over five workdays. This is useful for direct-application amount realism and "
            "supports a narrow executable loading check when a hand-scale exposed area is "
            "supplied, but it does not validate the MCP transfer or retention factors."
        ),
    ),
    ExternalValidationDataset(
        datasetId="rivm_wet_cloth_dermal_contact_loading_2018",
        domain="dermal_secondary_transfer",
        status=ExternalValidationDatasetStatus.PARTIAL,
        observable="product mass subject to dermal exposure from touching a wet cloth",
        targetMetrics=["product_contact_mass_g_per_event"],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["household_cleaner"],
        referenceTitle="Cleaning Products Fact Sheet",
        referenceLocator="https://www.rivm.nl/bibliotheek/rapporten/2016-0179.pdf",
        note=(
            "RIVM cleaning-product scenarios derive wet-cloth dermal contact amounts of "
            "0.31 g for an all-purpose cleaner spray rinsing case and 0.62 g for a floor "
            "cleaner liquid case. These support an executable secondary-contact realism "
            "check for household-cleaner wipe scenarios, but not a calibrated transfer model."
        ),
    ),
    ExternalValidationDataset(
        datasetId="vigabatrin_ready_to_use_dosing_accuracy_2025",
        domain="oral_direct_intake",
        status=ExternalValidationDatasetStatus.PARTIAL,
        observable="delivered oral dose relative to a target dose during caregiver use",
        targetMetrics=["chemical_mass_mg_per_event", "external_mass_mg_per_day"],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["medicinal_liquid"],
        referenceTitle=(
            "Liquid Medication Dosing Errors: Comparison of a Ready-to-Use Vigabatrin "
            "Solution to Reconstituted Solutions of Vigabatrin Powder for Oral Solution"
        ),
        referenceLocator="https://doi.org/10.1007/s12325-024-03089-0",
        note=(
            "Thirty lay users delivered single oral doses to a collection bottle against a "
            "1125 mg target; the ready-to-use solution stayed within ±5%, while the "
            "reconstituted product stayed within ±10% for 23 of 30 users. This is useful "
            "for delivered-dose realism, but it is not a general medication-use calibration set."
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
            gapId="tier1_nf_ff_external_validation_partial_only",
            title="Tier 1 NF/FF external validation is reference-linked but not executable",
            severity=ValidationGapSeverity.HIGH,
            appliesToDomains=["inhalation_near_field_far_field"],
            relatedSourceIds=["benchmark_tier1_nf_ff_parameter_pack_v1"],
            note=(
                "Tier 1 NF/FF spray screening now has benchmark coverage plus a cited "
                "consumer-spray inhalation study, but the dossier still lacks raw time-series "
                "datasets and acceptance bands that can be executed against the NF/FF solver."
            ),
            recommendation=(
                "Add chamber or breathing-zone datasets with raw time-series coverage and "
                "scenario metadata for near-field and far-field concentrations in "
                "personal-care and cleaner spray contexts."
            ),
        ),
        ValidationGap(
            gapId="tier0_spray_external_validation_partial_only",
            title="Tier 0 spray validation is partial and still not executable",
            severity=ValidationGapSeverity.MEDIUM,
            appliesToDomains=["inhalation_well_mixed_spray"],
            relatedSourceIds=[
                "peer_reviewed_cleaning_trigger_spray_airborne_fraction_2019",
                "rivm_cleaning_sprays_airborne_fraction_2018",
                "heuristic_residual_spray_airborne_fraction_defaults_v1",
            ],
            note=(
                "Tier 0 spray screening is benchmark-regressed and now tied to a real "
                "cleaning-spray study for trigger sprays plus an RIVM fact-sheet default for "
                "household-cleaner surface sprays, but non-cleaner pump-spray and aerosol-"
                "spray defaults remain heuristic and no executable chamber validation is wired in."
            ),
            recommendation=(
                "Add raw chamber or room-concentration datasets before promoting spray "
                "screening defaults beyond partial reference support."
            ),
        ),
        ValidationGap(
            gapId="dermal_validation_partial_only",
            title="Dermal validation is partial for direct application and thin for transfer",
            severity=ValidationGapSeverity.MEDIUM,
            appliesToDomains=["dermal_direct_application", "dermal_secondary_transfer"],
            relatedSourceIds=[
                "rivm_cosmetics_hand_cream_direct_application_defaults_2025",
                "rivm_cleaning_wet_cloth_transfer_defaults_2018",
                "screening_route_semantics_defaults_v1",
                "heuristic_retention_defaults_v1",
                "heuristic_transfer_efficiency_defaults_v1",
            ],
            note=(
                "Dermal direct-application amount realism is now linked to a real workplace "
                "cream-application study, personal-care hand-application and household-cleaner "
                "wet-cloth transfer defaults now have curated RIVM anchors, surface-contact "
                "retention still remains a screening default, and only narrow executable "
                "reference checks are wired in for the current secondary-transfer path."
            ),
            recommendation=(
                "Replace the remaining transfer and retention heuristics with curated packs "
                "tied to product family and external recovery datasets, especially beyond "
                "hand cream and household-cleaner wipe contexts."
            ),
        ),
        ValidationGap(
            gapId="oral_regimen_validation_partial_only",
            title="Direct-oral regimen validation is reference-linked but narrow",
            severity=ValidationGapSeverity.MEDIUM,
            appliesToDomains=["oral_direct_intake"],
            relatedSourceIds=[
                "screening_route_semantics_defaults_v1",
                "heuristic_density_defaults_v1",
                "heuristic_incidental_oral_defaults_v1",
            ],
            note=(
                "Direct-oral screening is benchmarked internally and now linked to a real "
                "delivered-dose study, but that reference is a narrow medicinal-liquid use "
                "case rather than a broad oral-product calibration set."
            ),
            recommendation=(
                "Add broader observed dosing or dispensed-amount datasets before broadening "
                "the direct-oral evidence posture beyond medicinal-liquid workflows."
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
                "Prioritize curated replacements for residual transfer-efficiency fallbacks, "
                "surface-contact retention, density, residual non-cleaner spray airborne "
                "fractions, incidental oral defaults, and time-limited release duration "
                "defaults."
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
        policyVersion="2026.03.25.v4",
        benchmarkDomains=domains,
        externalDatasets=EXTERNAL_VALIDATION_DATASETS,
        heuristicSourceIds=_heuristic_source_ids(active_registry),
        openGaps=_open_validation_gaps(active_registry),
        notes=[
            (
                "Current validation posture is benchmark regression plus verification, "
                "with typed external validation references, benchmark domains, and open "
                "gap tracking."
            ),
            (
                "Reference-linked validation targets are published for inhalation, dermal, "
                "and direct-oral screening, and selected dermal scenarios now support narrow "
                "executable reference checks."
            ),
            (
                "Selected dermal scenarios now support narrow executable reference checks "
                "through validationSummary.executedValidationChecks."
            ),
            (
                "Tier 1 inhalation NF/FF screening is implemented for spray scenarios, but "
                "external validation remains a governed future capability rather than an "
                "active pass gate."
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


def _assumption_value(scenario: ExposureScenario, name: str) -> float | None:
    for item in scenario.assumptions:
        if item.name == name and isinstance(item.value, int | float):
            return float(item.value)
    return None


def _executed_validation_checks(scenario: ExposureScenario) -> list[ExecutedValidationCheck]:
    profile = scenario.product_use_profile
    checks: list[ExecutedValidationCheck] = []

    if (
        scenario.route == Route.DERMAL
        and profile.product_category == "personal_care"
        and profile.physical_form == "cream"
        and profile.application_method == "hand_application"
        and profile.retention_type == "leave_on"
    ):
        exposed_area = _assumption_value(scenario, "exposed_surface_area_cm2")
        product_mass_g_event = _assumption_value(scenario, "product_mass_g_per_event")
        if (
            exposed_area is not None
            and product_mass_g_event is not None
            and 0.0 < exposed_area <= 1200.0
        ):
            observed = (product_mass_g_event * 1000.0) / exposed_area
            status = (
                ValidationCheckStatus.PASS
                if HAND_CREAM_LOADING_REFERENCE_LOWER
                <= observed
                <= HAND_CREAM_LOADING_REFERENCE_UPPER
                else ValidationCheckStatus.WARNING
            )
            checks.append(
                ExecutedValidationCheck(
                    checkId="hand_cream_application_loading_2012",
                    title="Hand cream application loading vs nurse workplace study",
                    referenceDatasetId="skin_protection_cream_dose_per_area_2012",
                    status=status,
                    comparedMetric="product_loading_mg_per_cm2_per_event",
                    observedValue=round(observed, 8),
                    referenceLower=HAND_CREAM_LOADING_REFERENCE_LOWER,
                    referenceUpper=HAND_CREAM_LOADING_REFERENCE_UPPER,
                    unit="mg/cm2/event",
                    note=(
                        "Observed hand-cream application loading is compared against the "
                        "reported mean ± SD band from Schliemann et al. when the supplied "
                        "exposed area is hand-scale."
                    ),
                )
            )

    if (
        scenario.route == Route.DERMAL
        and profile.product_category == "household_cleaner"
        and profile.application_method == "wipe"
        and profile.retention_type == "surface_contact"
        and profile.concentration_fraction > 0.0
        and profile.use_events_per_day > 0.0
    ):
        external_mass_mg_day = float(scenario.route_metrics.get("external_mass_mg_per_day", 0.0))
        observed = external_mass_mg_day / (
            1000.0 * profile.concentration_fraction * profile.use_events_per_day
        )
        status = (
            ValidationCheckStatus.PASS
            if WET_CLOTH_CONTACT_REFERENCE_LOWER
            <= observed
            <= WET_CLOTH_CONTACT_REFERENCE_UPPER
            else ValidationCheckStatus.WARNING
        )
        checks.append(
            ExecutedValidationCheck(
                checkId="wet_cloth_contact_mass_2018",
                title="Wet-cloth cleaner contact mass vs RIVM cleaning-product scenarios",
                referenceDatasetId="rivm_wet_cloth_dermal_contact_loading_2018",
                status=status,
                comparedMetric="product_contact_mass_g_per_event",
                observedValue=round(observed, 8),
                referenceLower=WET_CLOTH_CONTACT_REFERENCE_LOWER,
                referenceUpper=WET_CLOTH_CONTACT_REFERENCE_UPPER,
                unit="g/event",
                note=(
                    "Observed product mass at the skin boundary is compared against RIVM "
                    "wet-cloth contact amounts derived for household cleaning scenarios."
                ),
            )
        )

    return checks


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
    executed_validation_checks = _executed_validation_checks(scenario)
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
        executed_validation_checks=executed_validation_checks,
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
        ]
        + (
            [
                (
                    "Executable validation checks were run because the scenario matched one "
                    "or more published reference patterns."
                )
            ]
            if executed_validation_checks
            else []
        ),
    )
