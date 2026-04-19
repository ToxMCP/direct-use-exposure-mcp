"""Generated example payloads for contracts and tests."""

from __future__ import annotations

from typing import Any, cast

from exposure_scenario_mcp.archetypes import ArchetypeLibraryRegistry
from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.errors import ExposureScenarioError
from exposure_scenario_mcp.integrations import (
    CompToxChemicalRecord,
    ConsExpoEvidenceRecord,
    CosIngIngredientRecord,
    NanoMaterialEvidenceRecord,
    ProductUseEvidenceRecord,
    RunIntegratedExposureWorkflowInput,
    SccsCosmeticsEvidenceRecord,
    SccsOpinionEvidenceRecord,
    SyntheticPolymerMicroparticleEvidenceRecord,
    apply_comptox_enrichment,
    apply_product_use_evidence,
    assess_product_use_evidence_fit,
    build_pbpk_external_import_package,
    build_product_use_evidence_from_comptox,
    build_product_use_evidence_from_consexpo,
    build_product_use_evidence_from_cosing,
    build_product_use_evidence_from_nanomaterial,
    build_product_use_evidence_from_sccs,
    build_product_use_evidence_from_sccs_opinion,
    build_product_use_evidence_from_synthetic_polymer_microparticle,
    build_toxclaw_evidence_bundle,
    build_toxclaw_evidence_envelope,
    build_toxclaw_refinement_bundle,
    check_pbpk_compatibility,
    reconcile_product_use_evidence,
    run_integrated_exposure_workflow,
)
from exposure_scenario_mcp.models import (
    AggregationMode,
    AirflowDirectionality,
    BuildAggregateExposureScenarioInput,
    BuildExposureEnvelopeFromLibraryInput,
    BuildExposureEnvelopeInput,
    BuildParameterBoundsInput,
    BuildProbabilityBoundsFromProfileInput,
    BuildProbabilityBoundsFromScenarioPackageInput,
    ChemicalIdentity,
    CompareExposureScenariosInput,
    CompareJurisdictionalScenariosInput,
    ConcentrationSurface,
    EnvelopeArchetypeInput,
    EnvironmentalReleaseScenario,
    ExportPbpkExternalImportBundleRequest,
    ExportPbpkScenarioInputRequest,
    ExportToxClawEvidenceBundleRequest,
    ExportToxClawRefinementBundleRequest,
    ExposureEnvelopeSummary,
    ExposureScenarioDefinition,
    ExposureScenarioRequest,
    FitForPurpose,
    InhalationResidualAirReentryScenarioRequest,
    InhalationScenarioRequest,
    InhalationTier1ScenarioRequest,
    IntendedUseFamily,
    LimitationNote,
    OralExposureContext,
    ParameterBoundInput,
    ParameterBoundsSummary,
    ParticleAgglomerationState,
    ParticleCompositionFamily,
    ParticleMaterialClass,
    ParticleMaterialContext,
    ParticleNanoStatus,
    ParticleShapeFamily,
    ParticleSizeDomain,
    ParticleSizeRegime,
    ParticleSolubilityClass,
    PhyschemContext,
    PopulationProfile,
    ProbabilityBoundsProfileSummary,
    ProductAmountUnit,
    ProductUseProfile,
    ProvenanceBundle,
    QualityFlag,
    ReleaseMediumFraction,
    ResidualAirReentryMode,
    Route,
    RouteBioavailabilityAdjustment,
    RouteDoseEstimate,
    ScenarioClass,
    ScenarioPackageProbabilitySummary,
    Severity,
    TierLevel,
    WorkerTaskRoutingInput,
)
from exposure_scenario_mcp.package_metadata import CURRENT_VERSION
from exposure_scenario_mcp.plugins import InhalationScreeningPlugin, ScreeningScenarioPlugin
from exposure_scenario_mcp.plugins.inhalation import (
    build_inhalation_residual_air_reentry_scenario,
    build_inhalation_tier_1_screening_scenario,
)
from exposure_scenario_mcp.probability_bounds import (
    build_probability_bounds_from_profile,
    build_probability_bounds_from_scenario_package,
)
from exposure_scenario_mcp.probability_profiles import ProbabilityBoundsProfileRegistry
from exposure_scenario_mcp.result_meta import build_tool_result_meta
from exposure_scenario_mcp.runtime import (
    PluginRegistry,
    ScenarioEngine,
    aggregate_scenarios,
    compare_jurisdictional_scenarios,
    compare_scenarios,
    export_pbpk_input,
)
from exposure_scenario_mcp.scenario_probability_packages import ScenarioProbabilityPackageRegistry
from exposure_scenario_mcp.uncertainty import (
    build_exposure_envelope,
    build_exposure_envelope_from_library,
    build_parameter_bounds_summary,
    enrich_scenario_uncertainty,
)
from exposure_scenario_mcp.worker_dermal import (
    ExecuteWorkerDermalAbsorbedDoseRequest,
    ExportWorkerDermalAbsorbedDoseBridgeRequest,
    WorkerDermalAbsorbedDoseExecutionOverrides,
    WorkerDermalContactPattern,
    WorkerDermalModelFamily,
    WorkerDermalPpeState,
    build_worker_dermal_absorbed_dose_bridge,
    execute_worker_dermal_absorbed_dose_task,
    ingest_worker_dermal_absorbed_dose_task,
)
from exposure_scenario_mcp.worker_routing import route_worker_task
from exposure_scenario_mcp.worker_tier2 import (
    ExecuteWorkerInhalationTier2Request,
    ExportWorkerArtExecutionPackageRequest,
    ExportWorkerInhalationTier2BridgeRequest,
    ImportWorkerArtExecutionResultRequest,
    WorkerArtArtifactAdapterId,
    WorkerArtExternalArtifact,
    WorkerArtExternalExecutionResult,
    WorkerInhalationTier2ExecutionOverrides,
    WorkerTier2ModelFamily,
    WorkerVentilationContext,
    build_worker_inhalation_tier2_bridge,
    execute_worker_inhalation_tier2_task,
    export_worker_inhalation_art_execution_package,
    import_worker_inhalation_art_execution_result,
    ingest_worker_inhalation_tier2_task,
)

EXAMPLE_GENERATED_AT = "2026-03-24T00:00:00+00:00"
EXAMPLE_IDS = {
    "screening_dermal_scenario": "exp-example-dermal-001",
    "screening_dermal_refined_scenario": "exp-example-dermal-refined-001",
    "inhalation_scenario": "inh-example-room-001",
    "inhalation_residual_reentry_scenario": "inh-example-reentry-001",
    "inhalation_residual_reentry_native_scenario": "inh-example-reentry-native-001",
    "inhalation_tier1_scenario": "inh-tier1-example-001",
    "aggregate_summary": "agg-example-couse-001",
    "aggregate_internal_equivalent_summary": "agg-example-couse-internal-001",
    "envelope_summary": "env-example-dermal-001",
    "bounds_summary": "bnd-example-dermal-001",
    "envelope_low_scenario": "exp-example-envelope-low-001",
    "envelope_typical_scenario": "exp-example-envelope-typical-001",
    "envelope_high_scenario": "exp-example-envelope-high-001",
    "library_envelope_summary": "env-example-library-dermal-001",
    "library_envelope_low_scenario": "exp-example-library-envelope-low-001",
    "library_envelope_typical_scenario": "exp-example-library-envelope-typical-001",
    "library_envelope_high_scenario": "exp-example-library-envelope-high-001",
    "tier1_library_envelope_summary": "env-example-library-tier1-001",
    "tier1_library_envelope_low_scenario": "inh-tier1-example-library-low-001",
    "tier1_library_envelope_typical_scenario": "inh-tier1-example-library-typical-001",
    "tier1_library_envelope_high_scenario": "inh-tier1-example-library-high-001",
    "bounds_min_scenario": "exp-example-bounds-min-001",
    "bounds_max_scenario": "exp-example-bounds-max-001",
    "probability_bounds_summary": "pbnd-example-dermal-001",
    "scenario_package_probability_summary": "pspkg-example-dermal-001",
    "scenario_package_probability_low_scenario": "exp-example-package-low-001",
    "scenario_package_probability_typical_scenario": "exp-example-package-typical-001",
    "scenario_package_probability_high_scenario": "exp-example-package-high-001",
    "tier1_scenario_package_probability_summary": "pspkg-example-tier1-001",
    "tier1_scenario_package_probability_low_scenario": "inh-tier1-example-package-low-001",
    "tier1_scenario_package_probability_typical_scenario": (
        "inh-tier1-example-package-typical-001"
    ),
    "tier1_scenario_package_probability_high_scenario": "inh-tier1-example-package-high-001",
    "integrated_workflow_scenario": "inh-example-integrated-001",
}


def _freeze_provenance(provenance):
    return provenance.model_copy(update={"generated_at": EXAMPLE_GENERATED_AT}, deep=True)


def _freeze_scenario(scenario, scenario_id: str):
    return scenario.model_copy(
        update={
            "scenario_id": scenario_id,
            "provenance": _freeze_provenance(scenario.provenance),
        },
        deep=True,
    )


def _freeze_aggregate(summary):
    return summary.model_copy(
        update={
            "scenario_id": EXAMPLE_IDS["aggregate_summary"],
            "provenance": _freeze_provenance(summary.provenance),
        },
        deep=True,
    )


def _freeze_aggregate_with_id(summary, scenario_id: str):
    return summary.model_copy(
        update={
            "scenario_id": scenario_id,
            "provenance": _freeze_provenance(summary.provenance),
        },
        deep=True,
    )


def _freeze_comparison(record):
    return record.model_copy(
        update={"provenance": _freeze_provenance(record.provenance)},
        deep=True,
    )


def _freeze_jurisdictional_comparison(record):
    return record.model_copy(
        update={
            "comparison_id": "jurisdictional-comparison-example-001",
            "provenance": _freeze_provenance(record.provenance),
        },
        deep=True,
    )


def _freeze_pbpk_input(pbpk_input):
    return pbpk_input.model_copy(
        update={"provenance": _freeze_provenance(pbpk_input.provenance)},
        deep=True,
    )


def _replace_nested_string(value: Any, target: str, replacement: str) -> Any:
    if isinstance(value, dict):
        return {
            key: _replace_nested_string(item, target, replacement) for key, item in value.items()
        }
    if isinstance(value, list):
        return [_replace_nested_string(item, target, replacement) for item in value]
    if isinstance(value, str):
        return value.replace(target, replacement)
    return value


def _replace_nested_exact_string(value: Any, target: str, replacement: str) -> Any:
    if isinstance(value, dict):
        return {
            key: _replace_nested_exact_string(item, target, replacement)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_replace_nested_exact_string(item, target, replacement) for item in value]
    if isinstance(value, str):
        return replacement if value == target else value
    return value


def _freeze_integrated_workflow_result(result: Any) -> dict[str, Any]:
    frozen = result.model_dump(mode="json", by_alias=True)
    source_scenario_id = frozen["scenario"]["scenario_id"]
    source_generated_at = frozen["scenario"]["provenance"]["generated_at"]
    frozen = _replace_nested_string(
        frozen,
        source_scenario_id,
        EXAMPLE_IDS["integrated_workflow_scenario"],
    )
    return cast(
        dict[str, Any],
        _replace_nested_exact_string(
            frozen,
            source_generated_at,
            EXAMPLE_GENERATED_AT,
        ),
    )


def _freeze_envelope(summary: ExposureEnvelopeSummary) -> ExposureEnvelopeSummary:
    return _freeze_envelope_with_ids(
        summary,
        summary_id=EXAMPLE_IDS["envelope_summary"],
        label_ids={
            "Lower plausible use": EXAMPLE_IDS["envelope_low_scenario"],
            "Typical use": EXAMPLE_IDS["envelope_typical_scenario"],
            "Upper plausible use": EXAMPLE_IDS["envelope_high_scenario"],
        },
    )


def _freeze_envelope_with_ids(
    summary: ExposureEnvelopeSummary,
    *,
    summary_id: str,
    label_ids: dict[str, str],
) -> ExposureEnvelopeSummary:
    frozen_labels = {
        **label_ids,
    }
    frozen_archetypes = []
    for item in summary.archetypes:
        scenario_id = frozen_labels.get(item.label, item.scenario.scenario_id)
        frozen_archetypes.append(
            item.model_copy(
                update={"scenario": _freeze_scenario(item.scenario, scenario_id)},
                deep=True,
            )
        )
    min_dose = min(
        frozen_archetypes, key=lambda item: item.scenario.external_dose.value
    ).scenario.external_dose
    max_dose = max(
        frozen_archetypes, key=lambda item: item.scenario.external_dose.value
    ).scenario.external_dose
    return summary.model_copy(
        update={
            "envelope_id": summary_id,
            "archetypes": frozen_archetypes,
            "min_dose": min_dose,
            "max_dose": max_dose,
            "provenance": _freeze_provenance(summary.provenance),
        },
        deep=True,
    )


def _freeze_bounds_summary(summary: ParameterBoundsSummary) -> ParameterBoundsSummary:
    return summary.model_copy(
        update={
            "summary_id": EXAMPLE_IDS["bounds_summary"],
            "base_scenario": _freeze_scenario(
                summary.base_scenario,
                EXAMPLE_IDS["screening_dermal_scenario"],
            ),
            "min_scenario": _freeze_scenario(
                summary.min_scenario,
                EXAMPLE_IDS["bounds_min_scenario"],
            ),
            "max_scenario": _freeze_scenario(
                summary.max_scenario,
                EXAMPLE_IDS["bounds_max_scenario"],
            ),
            "provenance": _freeze_provenance(summary.provenance),
        },
        deep=True,
    )


def _freeze_probability_bounds_summary(
    summary: ProbabilityBoundsProfileSummary,
) -> ProbabilityBoundsProfileSummary:
    return summary.model_copy(
        update={
            "summary_id": EXAMPLE_IDS["probability_bounds_summary"],
            "base_scenario": _freeze_scenario(
                summary.base_scenario,
                EXAMPLE_IDS["screening_dermal_scenario"],
            ),
            "provenance": _freeze_provenance(summary.provenance),
        },
        deep=True,
    )


def _freeze_scenario_package_probability_summary(
    summary: ScenarioPackageProbabilitySummary,
) -> ScenarioPackageProbabilitySummary:
    return _freeze_scenario_package_probability_summary_with_ids(
        summary,
        summary_id=EXAMPLE_IDS["scenario_package_probability_summary"],
        template_ids={
            "adult_leave_on_hand_cream_low": EXAMPLE_IDS[
                "scenario_package_probability_low_scenario"
            ],
            "adult_leave_on_hand_cream_typical": EXAMPLE_IDS[
                "scenario_package_probability_typical_scenario"
            ],
            "adult_leave_on_hand_cream_high": EXAMPLE_IDS[
                "scenario_package_probability_high_scenario"
            ],
        },
    )


def _freeze_scenario_package_probability_summary_with_ids(
    summary: ScenarioPackageProbabilitySummary,
    *,
    summary_id: str,
    template_ids: dict[str, str],
) -> ScenarioPackageProbabilitySummary:
    frozen_points = []
    for item in summary.support_points:
        scenario_id = template_ids.get(item.template_id, item.scenario.scenario_id)
        frozen_points.append(
            item.model_copy(
                update={"scenario": _freeze_scenario(item.scenario, scenario_id)},
                deep=True,
            )
        )
    return summary.model_copy(
        update={
            "summary_id": summary_id,
            "support_points": frozen_points,
            "provenance": _freeze_provenance(summary.provenance),
            "minimum_dose": min(
                frozen_points, key=lambda item: item.scenario.external_dose.value
            ).scenario.external_dose,
            "maximum_dose": max(
                frozen_points, key=lambda item: item.scenario.external_dose.value
            ).scenario.external_dose,
        },
        deep=True,
    )


def _engine() -> ScenarioEngine:
    defaults_registry = DefaultsRegistry.load()
    registry = PluginRegistry()
    registry.register(ScreeningScenarioPlugin())
    registry.register(InhalationScreeningPlugin())
    return ScenarioEngine(registry=registry, defaults_registry=defaults_registry)


def build_examples() -> dict[str, dict]:
    engine = _engine()
    defaults_registry = DefaultsRegistry.load()
    archetype_library = ArchetypeLibraryRegistry.load()
    probability_profiles = ProbabilityBoundsProfileRegistry.load()
    scenario_probability_packages = ScenarioProbabilityPackageRegistry.load()

    dermal_request = ExposureScenarioRequest(
        chemical_id="DTXSID7020182",
        chemical_name="Example Solvent A",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_name="Example Hand Cream",
            product_category="personal_care",
            physical_form="cream",
            application_method="hand_application",
            retention_type="leave_on",
            concentration_fraction=0.02,
            use_amount_per_event=1.5,
            use_amount_unit=ProductAmountUnit.G,
            use_events_per_day=3,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            demographic_tags=["consumer", "general_population"],
            region="EU",
        ),
    )
    chemical_identity = ChemicalIdentity(
        chemicalId="DTXSID7020182",
        preferredName="Example Solvent A",
        casrn="123-45-6",
        dtxsid="DTXSID7020182",
        externalIdentifiers={"exampleRegistry": "EX-0001"},
        notes=["Illustrative shared suite identity contract derived from the example scenario."],
    )
    exposure_scenario_definition = ExposureScenarioDefinition(
        scenarioDefinitionId="exp-def-example-001",
        chemicalIdentity=chemical_identity,
        route=Route.DERMAL,
        scenarioClass=ScenarioClass.SCREENING,
        pathwaySemantics="direct_use",
        productUseProfile=dermal_request.product_use_profile,
        populationProfile=dermal_request.population_profile,
        assumptionOverrides=dermal_request.assumption_overrides,
        notes=[
            "Example shared scenario-definition contract for a direct-use consumer hand cream case."
        ],
    )
    tcm_medicinal_oral_request = ExposureScenarioRequest(
        chemical_id="TCM-EXAMPLE-001",
        chemical_name="Example TCM Pill Constituent",
        route=Route.ORAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_name="Example Traditional Chinese Medicine Pill",
            product_category="herbal_medicinal_product",
            physical_form="tablet",
            application_method="direct_oral",
            retention_type="ingested",
            concentration_fraction=0.25,
            use_amount_per_event=0.8,
            use_amount_unit=ProductAmountUnit.G,
            dosageUnitCountPerEvent=4,
            dosageUnitMassG=0.2,
            dosageUnitLabel="pill",
            use_events_per_day=2,
            intendedUseFamily=IntendedUseFamily.MEDICINAL,
            oralExposureContext=OralExposureContext.DIRECT_USE_MEDICINAL,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=60,
            region="CN",
        ),
    )
    botanical_supplement_oral_request = ExposureScenarioRequest(
        chemical_id="SUPPLEMENT-EXAMPLE-001",
        chemical_name="Example Botanical Supplement Constituent",
        route=Route.ORAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_name="Example Botanical Supplement Capsule",
            product_category="dietary_supplement",
            physical_form="capsule",
            application_method="direct_oral",
            retention_type="ingested",
            concentration_fraction=0.12,
            use_amount_per_event=0.6,
            use_amount_unit=ProductAmountUnit.G,
            dosageUnitCountPerEvent=2,
            dosageUnitMassG=0.3,
            dosageUnitLabel="capsule",
            use_events_per_day=1,
            intendedUseFamily=IntendedUseFamily.SUPPLEMENT,
            oralExposureContext=OralExposureContext.DIRECT_USE_SUPPLEMENT,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=70,
            region="EU",
        ),
    )
    dietary_supplement_oral_request = ExposureScenarioRequest(
        chemical_id="SUPPLEMENT-IRON-EXAMPLE-001",
        chemical_name="Example Iron Supplement Constituent",
        route=Route.ORAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_name="Example Iron Supplement Capsule",
            product_category="dietary_supplement",
            product_subtype="iron_capsule",
            physical_form="capsule",
            application_method="direct_oral",
            retention_type="ingested",
            concentration_fraction=0.3,
            use_amount_per_event=0.1,
            use_amount_unit=ProductAmountUnit.G,
            dosageUnitCountPerEvent=1,
            dosageUnitMassG=0.1,
            dosageUnitLabel="capsule",
            use_events_per_day=1,
            intendedUseFamily=IntendedUseFamily.SUPPLEMENT,
            oralExposureContext=OralExposureContext.DIRECT_USE_SUPPLEMENT,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=70,
            region="US",
        ),
    )
    herbal_medicinal_infusion_request = ExposureScenarioRequest(
        chemical_id="HMPC-INFUSION-EXAMPLE-001",
        chemical_name="Example Valerian Infusion Constituent",
        route=Route.ORAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_name="Example Herbal Medicinal Infusion",
            product_category="herbal_medicinal_product",
            product_subtype="valerian_root_infusion",
            physical_form="herbal_tea",
            application_method="direct_oral",
            retention_type="ingested",
            concentration_fraction=1.0,
            use_amount_per_event=2.0,
            use_amount_unit=ProductAmountUnit.G,
            use_events_per_day=2,
            intendedUseFamily=IntendedUseFamily.MEDICINAL,
            oralExposureContext=OralExposureContext.DIRECT_USE_MEDICINAL,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=70,
            region="EU",
        ),
    )
    tcm_topical_balm_request = ExposureScenarioRequest(
        chemical_id="TCM-TOPICAL-001",
        chemical_name="Example Herbal Balm Constituent",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_name="Example TCM Balm",
            product_category="herbal_topical_product",
            physical_form="ointment",
            application_method="hand_application",
            retention_type="leave_on",
            concentration_fraction=0.04,
            use_amount_per_event=1.2,
            use_amount_unit=ProductAmountUnit.G,
            use_events_per_day=3,
            intendedUseFamily=IntendedUseFamily.MEDICINAL,
            applicationStripLengthCm=3.0,
            applicationCoverageContext="palm_sized_area",
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=60,
            region="CN",
        ),
    )
    herbal_topical_spray_request = ExposureScenarioRequest(
        chemical_id="HERBAL-SPRAY-EXAMPLE-001",
        chemical_name="Example Herbal Topical Spray Formulation",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_name="Example Herbal Topical Spray",
            product_category="herbal_topical_product",
            product_subtype="herbal_topical_spray",
            physical_form="spray",
            application_method="pump_spray",
            retention_type="leave_on",
            concentration_fraction=1.0,
            use_amount_per_event=0.75,
            use_amount_unit=ProductAmountUnit.ML,
            density_g_per_ml=1.0,
            transfer_efficiency=1.0,
            use_events_per_day=1,
            intendedUseFamily=IntendedUseFamily.MEDICINAL,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=70,
            region="US",
        ),
    )
    herbal_recovery_patch_request = ExposureScenarioRequest(
        chemical_id="HERBAL-PATCH-EXAMPLE-001",
        chemical_name="Example Herbal Recovery Patch Constituent",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_name="Example Herbal Recovery Patch",
            product_category="herbal_topical_product",
            product_subtype="herbal_recovery_patch",
            physical_form="patch",
            application_method="patch_application",
            retention_type="leave_on",
            concentration_fraction=0.108,
            use_amount_per_event=14.0,
            use_amount_unit=ProductAmountUnit.G,
            transfer_efficiency=1.0,
            use_events_per_day=1,
            intendedUseFamily=IntendedUseFamily.MEDICINAL,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=70,
            region="US",
        ),
    )
    capsicum_hydrogel_patch_request = ExposureScenarioRequest(
        chemical_id="CAPSICUM-PATCH-EXAMPLE-001",
        chemical_name="Example Capsicum Patch Constituent",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_name="Example Capsicum Hydrogel Patch",
            product_category="botanical_topical_patch",
            product_subtype="capsicum_hydrogel_patch",
            physical_form="patch",
            application_method="patch_application",
            retention_type="leave_on",
            concentration_fraction=0.022,
            use_amount_per_event=1.0,
            use_amount_unit=ProductAmountUnit.G,
            transfer_efficiency=1.0,
            use_events_per_day=1,
            intendedUseFamily=IntendedUseFamily.MEDICINAL,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=70,
            region="US",
        ),
    )
    dermal_scenario = _freeze_scenario(
        engine.build(dermal_request),
        EXAMPLE_IDS["screening_dermal_scenario"],
    )
    route_dose_estimate = RouteDoseEstimate(
        chemicalIdentity=chemical_identity,
        route=dermal_scenario.route,
        scenarioClass=dermal_scenario.scenario_class,
        dose=dermal_scenario.external_dose,
        sourceScenarioDefinitionId=exposure_scenario_definition.scenario_definition_id,
        sourceScenarioId=dermal_scenario.scenario_id,
        populationProfile=dermal_request.population_profile,
        fitForPurpose=dermal_scenario.fit_for_purpose,
        provenance=_freeze_provenance(dermal_scenario.provenance),
        limitations=dermal_scenario.limitations,
        qualityFlags=dermal_scenario.quality_flags,
        notes=[
            "Example shared route-dose contract emitted from a deterministic direct-use scenario."
        ],
    )
    environmental_release_scenario = EnvironmentalReleaseScenario(
        releaseScenarioId="rel-example-001",
        chemicalIdentity=chemical_identity,
        sourceTermType="mass",
        releaseMassMg=2500.0,
        releaseDurationHours=24.0,
        timingPattern="single post-application environmental release window",
        regionScope="EU residential fringe",
        siteContext="treated outdoor perimeter near residential receptor",
        releaseMediaFractions=[
            ReleaseMediumFraction(medium="air", fraction=0.6),
            ReleaseMediumFraction(medium="soil", fraction=0.4),
        ],
        treatmentOrRemovalFraction=0.1,
        evidenceSources=["ExampleFateEvidence:release-scenario-001"],
        notes=[
            "Illustrative future Fate MCP ingress contract published by Exposure MCP "
            "for boundary alignment."
        ],
    )
    concentration_surface = ConcentrationSurface(
        surfaceId="conc-surface-example-001",
        chemicalIdentity=chemical_identity,
        medium="air",
        compartment="outdoor_residential_air",
        geographicScope="EU residential screening zone",
        compartmentContext={
            "distanceBandMeters": "0-100",
            "microenvironment": "outdoor_residential",
        },
        timeSemantics="24h average post-application concentration",
        concentrationValue=0.018,
        concentrationUnit="mg/m3",
        modelFamily="future_fate_mcp_adapter",
        sourceReleaseScenarioId=environmental_release_scenario.release_scenario_id,
        fitForPurpose=FitForPurpose(
            label="future_fate_handoff",
            suitable_for=[
                "Future concentration-to-dose workflows",
                "Cross-MCP fate-to-exposure integration testing",
            ],
            not_suitable_for=[
                "Direct body-weight-normalized dose interpretation without a downstream consumer",
                "Final risk conclusions",
            ],
        ),
        provenance=ProvenanceBundle(
            algorithm_id="example.future_fate_handoff.v1",
            plugin_id="shared_contract_example_generator",
            plugin_version=CURRENT_VERSION,
            defaults_version=defaults_registry.version,
            defaults_hash_sha256=defaults_registry.sha256,
            generated_at=EXAMPLE_GENERATED_AT,
            notes=[
                "Illustrative concentration surface example for cross-MCP contract publication."
            ],
        ),
        limitations=[
            LimitationNote(
                code="future_fate_contract_example_only",
                severity=Severity.WARNING,
                message=(
                    "This example is a contract-alignment payload, not the output of a native "
                    "Fate MCP solver."
                ),
            )
        ],
        qualityFlags=[
            QualityFlag(
                code="external_normalized_future_surface",
                severity=Severity.INFO,
                message=("This example shows the future concentration-surface handoff shape only."),
            )
        ],
        notes=[
            "Published by Exposure MCP so sibling Fate and Dietary services can build "
            "against a stable shared contract."
        ],
    )

    inhalation_request = InhalationScenarioRequest(
        chemical_id="DTXSID7020182",
        chemical_name="Example Solvent A",
        route=Route.INHALATION,
        physchemContext=PhyschemContext(
            vaporPressureMmhg=8.0,
            molecularWeightGPerMol=120.15,
            logKow=2.1,
            waterSolubilityMgPerL=950.0,
        ),
        product_use_profile=ProductUseProfile(
            product_name="Example Trigger Spray",
            product_category="household_cleaner",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.05,
            use_amount_per_event=12,
            use_amount_unit=ProductAmountUnit.ML,
            use_events_per_day=1,
            room_volume_m3=25,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=68,
            inhalation_rate_m3_per_hour=0.9,
            region="EU",
        ),
    )
    inhalation_scenario = _freeze_scenario(
        engine.build(inhalation_request),
        EXAMPLE_IDS["inhalation_scenario"],
    )
    inhalation_residual_reentry_request = InhalationResidualAirReentryScenarioRequest(
        chemical_id="DTXSID8020230",
        chemical_name="Example Insecticide B",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_name="Example Indoor Surface Insecticide",
            product_category="pesticide",
            product_subtype="indoor_surface_insecticide",
            physical_form="spray",
            application_method="residual_air_reentry",
            retention_type="surface_contact",
            concentration_fraction=0.005,
            use_amount_per_event=20,
            use_amount_unit=ProductAmountUnit.ML,
            use_events_per_day=1,
            room_volume_m3=30,
            air_exchange_rate_per_hour=0.5,
            exposure_duration_hours=4.0,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=80,
            inhalation_rate_m3_per_hour=0.83,
            region="EU",
        ),
        airConcentrationAtReentryStartMgPerM3=0.08,
        additionalDecayRatePerHour=0.03,
        postApplicationDelayHours=4.0,
    )
    inhalation_residual_reentry_scenario = _freeze_scenario(
        enrich_scenario_uncertainty(
            engine,
            build_inhalation_residual_air_reentry_scenario(
                inhalation_residual_reentry_request,
                defaults_registry,
                generated_at=EXAMPLE_GENERATED_AT,
            ),
        ),
        EXAMPLE_IDS["inhalation_residual_reentry_scenario"],
    )
    inhalation_residual_reentry_native_request = InhalationResidualAirReentryScenarioRequest(
        chemical_id="DTXSID8020230",
        chemical_name="Example Insecticide B",
        route=Route.INHALATION,
        reentryMode=ResidualAirReentryMode.NATIVE_TREATED_SURFACE_REENTRY,
        physchemContext=PhyschemContext(
            vaporPressureMmhg=0.02,
            molecularWeightGPerMol=304.1,
            logKow=4.9,
            waterSolubilityMgPerL=40.0,
        ),
        product_use_profile=ProductUseProfile(
            product_name="Example Indoor Surface Insecticide",
            product_category="pesticide",
            product_subtype="indoor_surface_insecticide",
            physical_form="spray",
            application_method="residual_air_reentry",
            retention_type="surface_contact",
            concentration_fraction=0.005,
            use_amount_per_event=20,
            use_amount_unit=ProductAmountUnit.ML,
            use_events_per_day=1,
            room_volume_m3=30,
            air_exchange_rate_per_hour=0.5,
            exposure_duration_hours=4.0,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=80,
            inhalation_rate_m3_per_hour=0.83,
            region="EU",
        ),
        additionalDecayRatePerHour=0.03,
        postApplicationDelayHours=4.0,
    )
    inhalation_residual_reentry_native_scenario = _freeze_scenario(
        enrich_scenario_uncertainty(
            engine,
            build_inhalation_residual_air_reentry_scenario(
                inhalation_residual_reentry_native_request,
                defaults_registry,
                generated_at=EXAMPLE_GENERATED_AT,
            ),
        ),
        EXAMPLE_IDS["inhalation_residual_reentry_native_scenario"],
    )
    inhalation_tier1_request = InhalationTier1ScenarioRequest(
        chemical_id="DTXSID7020182",
        chemical_name="Example Solvent A",
        route=Route.INHALATION,
        physchemContext=PhyschemContext(
            vaporPressureMmhg=8.0,
            molecularWeightGPerMol=120.15,
            logKow=2.1,
            waterSolubilityMgPerL=950.0,
        ),
        product_use_profile=ProductUseProfile(
            product_name="Example Trigger Spray",
            product_category="household_cleaner",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.05,
            use_amount_per_event=12,
            use_amount_unit=ProductAmountUnit.ML,
            use_events_per_day=1,
            room_volume_m3=25,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=68,
            inhalation_rate_m3_per_hour=0.9,
            region="EU",
        ),
        source_distance_m=0.35,
        spray_duration_seconds=8.0,
        near_field_volume_m3=2.0,
        airflow_directionality=AirflowDirectionality.CROSS_DRAFT,
        particle_size_regime=ParticleSizeRegime.COARSE_SPRAY,
    )
    inhalation_tier1_request_two_zone = inhalation_tier1_request.model_copy(
        update={"solver_variant": "two_zone_v1"}
    )
    inhalation_tier1_scenario = _freeze_scenario(
        enrich_scenario_uncertainty(
            engine,
            build_inhalation_tier_1_screening_scenario(
                inhalation_tier1_request_two_zone,
                defaults_registry,
                generated_at=EXAMPLE_GENERATED_AT,
            ),
        ),
        EXAMPLE_IDS["inhalation_tier1_scenario"],
    )

    refined_request = dermal_request.model_copy(
        update={
            "product_use_profile": dermal_request.product_use_profile.model_copy(
                update={"retention_factor": 0.65, "transfer_efficiency": 0.8}
            )
        }
    )
    refined_scenario = _freeze_scenario(
        engine.build(refined_request),
        EXAMPLE_IDS["screening_dermal_refined_scenario"],
    )
    envelope_input = BuildExposureEnvelopeInput(
        chemical_id="DTXSID7020182",
        label="Example dermal use envelope",
        archetypes=[
            EnvelopeArchetypeInput(
                label="Lower plausible use",
                description="Reduced amount and lower frequency archetype.",
                request=dermal_request.model_copy(
                    update={
                        "product_use_profile": (
                            dermal_request.product_use_profile.model_copy(
                                update={
                                    "use_amount_per_event": 1.0,
                                    "use_events_per_day": 2,
                                }
                            )
                        )
                    }
                ),
            ),
            EnvelopeArchetypeInput(
                label="Typical use",
                description="Baseline screening archetype.",
                request=dermal_request,
            ),
            EnvelopeArchetypeInput(
                label="Upper plausible use",
                description="Higher amount and explicit refinement modifiers.",
                request=refined_request.model_copy(
                    update={
                        "product_use_profile": (
                            refined_request.product_use_profile.model_copy(
                                update={
                                    "use_amount_per_event": 2.0,
                                    "use_events_per_day": 4,
                                }
                            )
                        )
                    }
                ),
            ),
        ],
    )
    envelope_summary = _freeze_envelope(
        build_exposure_envelope(
            envelope_input,
            engine,
            defaults_registry,
            generated_at=EXAMPLE_GENERATED_AT,
        )
    )
    library_envelope_request = BuildExposureEnvelopeFromLibraryInput(
        librarySetId="adult_leave_on_hand_cream",
        chemicalId="DTXSID7020182",
        chemicalName="Example Solvent A",
        label="Example library-backed dermal envelope",
    )
    library_envelope_summary = _freeze_envelope_with_ids(
        build_exposure_envelope_from_library(
            library_envelope_request,
            engine,
            defaults_registry,
            archetype_library,
            generated_at=EXAMPLE_GENERATED_AT,
        ),
        summary_id=EXAMPLE_IDS["library_envelope_summary"],
        label_ids={
            "Lower plausible use": EXAMPLE_IDS["library_envelope_low_scenario"],
            "Typical use": EXAMPLE_IDS["library_envelope_typical_scenario"],
            "Upper plausible use": EXAMPLE_IDS["library_envelope_high_scenario"],
        },
    )
    tier1_library_envelope_request = BuildExposureEnvelopeFromLibraryInput(
        librarySetId="adult_personal_care_pump_spray_tier1",
        chemicalId="DTXSID7020182",
        chemicalName="Example Solvent A",
        label="Example Tier 1 library-backed inhalation envelope",
    )
    tier1_library_envelope_summary = _freeze_envelope_with_ids(
        build_exposure_envelope_from_library(
            tier1_library_envelope_request,
            engine,
            defaults_registry,
            archetype_library,
            generated_at=EXAMPLE_GENERATED_AT,
        ),
        summary_id=EXAMPLE_IDS["tier1_library_envelope_summary"],
        label_ids={
            "Lower plausible near-face use": EXAMPLE_IDS["tier1_library_envelope_low_scenario"],
            "Typical near-face use": EXAMPLE_IDS["tier1_library_envelope_typical_scenario"],
            "Upper plausible near-face use": EXAMPLE_IDS["tier1_library_envelope_high_scenario"],
        },
    )
    parameter_bounds_summary = _freeze_bounds_summary(
        build_parameter_bounds_summary(
            BuildParameterBoundsInput(
                label="Example dermal parameter bounds",
                baseRequest=dermal_request,
                boundedParameters=[
                    ParameterBoundInput(
                        parameterName="concentration_fraction",
                        lowerValue=0.01,
                        upperValue=0.03,
                        rationale=(
                            "Bound ingredient concentration between low and high plausible values."
                        ),
                    ),
                    ParameterBoundInput(
                        parameterName="body_weight_kg",
                        lowerValue=60,
                        upperValue=90,
                        unit="kg",
                        rationale="Bound normalization by plausible adult body weights.",
                    ),
                ],
            ),
            engine,
            defaults_registry,
            generated_at=EXAMPLE_GENERATED_AT,
        )
    )
    probability_bounds_request = BuildProbabilityBoundsFromProfileInput(
        label="Example dermal probability bounds",
        baseRequest=dermal_request,
        driverProfileId="adult_leave_on_hand_cream_use_amount_per_event",
    )
    probability_bounds_summary = _freeze_probability_bounds_summary(
        build_probability_bounds_from_profile(
            probability_bounds_request,
            engine,
            defaults_registry,
            probability_profiles,
            generated_at=EXAMPLE_GENERATED_AT,
        )
    )
    scenario_package_probability_request = BuildProbabilityBoundsFromScenarioPackageInput(
        packageProfileId="adult_leave_on_hand_cream_use_intensity_package",
        chemicalId="DTXSID7020182",
        chemicalName="Example Solvent A",
        label="Example dermal scenario-package probability bounds",
    )
    scenario_package_probability_summary = _freeze_scenario_package_probability_summary(
        build_probability_bounds_from_scenario_package(
            scenario_package_probability_request,
            engine,
            defaults_registry,
            archetype_library,
            scenario_probability_packages,
            generated_at=EXAMPLE_GENERATED_AT,
        )
    )
    tier1_scenario_package_probability_request = BuildProbabilityBoundsFromScenarioPackageInput(
        packageProfileId="adult_personal_care_pump_spray_tier1_near_field_context_package",
        chemicalId="DTXSID7020182",
        chemicalName="Example Solvent A",
        label="Example Tier 1 scenario-package probability bounds",
    )
    tier1_scenario_package_probability_summary = (
        _freeze_scenario_package_probability_summary_with_ids(
            build_probability_bounds_from_scenario_package(
                tier1_scenario_package_probability_request,
                engine,
                defaults_registry,
                archetype_library,
                scenario_probability_packages,
                generated_at=EXAMPLE_GENERATED_AT,
            ),
            summary_id=EXAMPLE_IDS["tier1_scenario_package_probability_summary"],
            template_ids={
                "adult_personal_care_pump_spray_tier1_low": EXAMPLE_IDS[
                    "tier1_scenario_package_probability_low_scenario"
                ],
                "adult_personal_care_pump_spray_tier1_typical": EXAMPLE_IDS[
                    "tier1_scenario_package_probability_typical_scenario"
                ],
                "adult_personal_care_pump_spray_tier1_high": EXAMPLE_IDS[
                    "tier1_scenario_package_probability_high_scenario"
                ],
            },
        )
    )

    aggregate_input = BuildAggregateExposureScenarioInput(
        chemical_id="DTXSID7020182",
        label="Example co-use summary",
        component_scenarios=[dermal_scenario, inhalation_scenario],
    )
    aggregate_summary = _freeze_aggregate(aggregate_scenarios(aggregate_input, defaults_registry))
    aggregate_internal_equivalent_input = BuildAggregateExposureScenarioInput(
        chemical_id="DTXSID7020182",
        label="Example co-use internal-equivalent screening summary",
        aggregationMode=AggregationMode.INTERNAL_EQUIVALENT,
        routeBioavailabilityAdjustments=[
            RouteBioavailabilityAdjustment(route=Route.DERMAL, bioavailabilityFraction=0.1),
            RouteBioavailabilityAdjustment(route=Route.INHALATION, bioavailabilityFraction=1.0),
        ],
        component_scenarios=[dermal_scenario, inhalation_scenario],
    )
    aggregate_internal_equivalent_summary = _freeze_aggregate_with_id(
        aggregate_scenarios(aggregate_internal_equivalent_input, defaults_registry),
        EXAMPLE_IDS["aggregate_internal_equivalent_summary"],
    )
    pbpk_request = ExportPbpkScenarioInputRequest(
        scenario=dermal_scenario, regimen_name="screening_daily_use"
    )
    pbpk_input = _freeze_pbpk_input(
        export_pbpk_input(
            pbpk_request,
            defaults_registry,
        )
    )
    pbpk_input_transient = _freeze_pbpk_input(
        export_pbpk_input(
            ExportPbpkScenarioInputRequest(
                scenario=inhalation_scenario,
                regimen_name="screening_daily_use",
                includeTransientConcentrationProfile=True,
            ),
            defaults_registry,
        )
    )
    comparison_input = CompareExposureScenariosInput(
        baseline=dermal_scenario, comparison=refined_scenario
    )
    comparison = _freeze_comparison(
        compare_scenarios(
            comparison_input,
            defaults_registry,
        )
    )
    jurisdictional_comparison_input = CompareJurisdictionalScenariosInput(
        request=dermal_request,
        jurisdictions=["global", "china"],
    )
    jurisdictional_comparison = _freeze_jurisdictional_comparison(
        compare_jurisdictional_scenarios(
            jurisdictional_comparison_input,
        )
    )
    comp_tox_record = CompToxChemicalRecord(
        chemical_id="DTXSID7020182",
        preferred_name="Example Solvent A",
        casrn="123-45-6",
        product_use_categories=["personal_care", "household_cleaner"],
        physchem_summary={"vapor_pressure_pa": 150.0, "water_solubility_mg_l": 1200.0},
        evidence_sources=["CompTox:mock-record-001"],
    )
    comp_tox_enriched_request = apply_comptox_enrichment(dermal_request, comp_tox_record)
    comp_tox_product_use_evidence = build_product_use_evidence_from_comptox(comp_tox_record)
    cons_expo_evidence_record = ConsExpoEvidenceRecord(
        chemical_id="DTXSID7020182",
        preferred_name="Example Solvent A",
        casrn="123-45-6",
        factSheetId="pest_control_products_fact_sheet_2006",
        factSheetTitle="ConsExpo Pest Control Products Fact Sheet",
        factSheetVersion="RIVM report 320005002 / 2006",
        factSheetLocator="https://www.rivm.nl/bibliotheek/rapporten/320005002.pdf",
        productGroup="pest_control_products",
        productSubgroup="Indoor trigger spray insecticide",
        modelFamily="spray",
        supportedRoutes=[Route.DERMAL, Route.INHALATION],
        physical_forms=["spray"],
        application_methods=["trigger_spray"],
        retention_types=["surface_contact"],
        physchem_summary={"density_g_per_ml": 1.08},
        evidence_sources=["ConsExpo:pest_control_products_fact_sheet_2006"],
        notes=["Illustrative ConsExpo pest-control evidence mapped into the generic contract."],
    )
    cons_expo_product_use_evidence = build_product_use_evidence_from_consexpo(
        cons_expo_evidence_record
    )
    sccs_evidence_record = SccsCosmeticsEvidenceRecord(
        chemical_id="DTXSID7020182",
        preferred_name="Example Solvent A",
        casrn="123-45-6",
        guidanceId="sccs_nog_12th_revision_face_cream_2023",
        guidanceTitle=(
            "SCCS Notes of Guidance for the Testing of Cosmetic Ingredients and their "
            "Safety Evaluation, 12th revision"
        ),
        guidanceVersion="12th revision / 2023",
        guidanceLocator=(
            "https://health.ec.europa.eu/publications/"
            "sccs-notes-guidance-testing-cosmetic-ingredients-and-their-safety-"
            "evaluation-12th-revision_en"
        ),
        cosmeticProductType="Face cream",
        productFamily="skin_care",
        tableReferences=["Table 3A", "Table 4"],
        supportedRoutes=[Route.DERMAL],
        physical_forms=["cream"],
        application_methods=["hand_application"],
        retention_types=["leave_on"],
        productUseProfileOverrides={
            "use_amount_per_event": 0.71962617,
            "use_amount_unit": "g",
            "use_events_per_day": 2.14,
        },
        populationProfileOverrides={
            "body_weight_kg": 63.79453,
            "exposed_surface_area_cm2": 565.0,
            "region": "EU",
        },
        evidence_sources=["SCCS:NotesOfGuidance:12thRevision:FaceCream"],
        notes=["Illustrative SCCS cosmetics guidance evidence mapped into the generic contract."],
    )
    sccs_product_use_evidence = build_product_use_evidence_from_sccs(sccs_evidence_record)
    nano_particle_material_context = ParticleMaterialContext(
        materialClass=ParticleMaterialClass.NANOMATERIAL,
        nanoStatus=ParticleNanoStatus.NANO_SPECIFIC,
        particleSizeDomain=ParticleSizeDomain.NANO,
        compositionFamily=ParticleCompositionFamily.METAL_OXIDE,
        intentionallyManufacturedParticle=True,
        insolubleOrBiopersistent=True,
        solubilityClass=ParticleSolubilityClass.INSOLUBLE,
        agglomerationState=ParticleAgglomerationState.AGGLOMERATED,
        shapeFamily=ParticleShapeFamily.IRREGULAR,
        surfaceTreated=True,
        surfaceTreatmentNotes="Illustrative alumina/silica-coated UV filter particle.",
        medianPrimaryParticleSizeNm=35.0,
        sizeRangeNmLow=20.0,
        sizeRangeNmHigh=80.0,
        respirableFractionRelevance=True,
        dermalPenetrationConcern=True,
        article16NotificationRelevant=True,
        echaSpmRestrictionRelevant=False,
        notes=[
            "Illustrative nano TiO2 / ZnO-style cosmetics particle context.",
        ],
    )
    microplastic_particle_material_context = ParticleMaterialContext(
        materialClass=ParticleMaterialClass.SYNTHETIC_POLYMER_MICROPARTICLE,
        nanoStatus=ParticleNanoStatus.NON_NANO,
        particleSizeDomain=ParticleSizeDomain.MICRO,
        compositionFamily=ParticleCompositionFamily.POLYMER,
        intentionallyManufacturedParticle=True,
        insolubleOrBiopersistent=True,
        solubilityClass=ParticleSolubilityClass.INSOLUBLE,
        agglomerationState=ParticleAgglomerationState.MIXED,
        shapeFamily=ParticleShapeFamily.IRREGULAR,
        surfaceTreated=False,
        medianPrimaryParticleSizeNm=5000.0,
        sizeRangeNmLow=1000.0,
        sizeRangeNmHigh=10000.0,
        respirableFractionRelevance=False,
        dermalPenetrationConcern=False,
        article16NotificationRelevant=False,
        echaSpmRestrictionRelevant=True,
        notes=["Illustrative synthetic polymer microparticle context for direct-use cosmetics."],
    )
    non_plastic_particle_material_context = ParticleMaterialContext(
        materialClass=ParticleMaterialClass.NON_PLASTIC_MICRO_NANO_PARTICLE,
        nanoStatus=ParticleNanoStatus.CONTAINS_NANO_FRACTION,
        particleSizeDomain=ParticleSizeDomain.MIXED_MICRO_NANO,
        compositionFamily=ParticleCompositionFamily.SILICA,
        intentionallyManufacturedParticle=True,
        insolubleOrBiopersistent=True,
        solubilityClass=ParticleSolubilityClass.POORLY_SOLUBLE,
        agglomerationState=ParticleAgglomerationState.MIXED,
        shapeFamily=ParticleShapeFamily.IRREGULAR,
        surfaceTreated=False,
        medianPrimaryParticleSizeNm=150.0,
        sizeRangeNmLow=40.0,
        sizeRangeNmHigh=2000.0,
        respirableFractionRelevance=True,
        dermalPenetrationConcern=False,
        article16NotificationRelevant=False,
        echaSpmRestrictionRelevant=False,
        notes=["Illustrative non-plastic particle context such as silica or pigment particles."],
    )
    sccs_opinion_evidence_record = SccsOpinionEvidenceRecord(
        chemical_id="DTXSID7020182",
        preferred_name="Example Nano UV Filter",
        casrn="123-45-6",
        opinionId="sccs_opinion_nano_uv_filter_mock_2026",
        opinionTitle="SCCS scientific advice on a nano UV filter used in cosmetic products",
        opinionVersion="2026 mock example",
        opinionLocator="https://health.ec.europa.eu/scientific-committees/scientific-committee-consumer-safety-sccs_en",
        cosmeticProductTypes=["Spray sunscreen"],
        supportedRoutes=[Route.DERMAL, Route.INHALATION],
        physical_forms=["spray"],
        application_methods=["aerosol_spray"],
        retention_types=["leave_on"],
        particleMaterialContext=nano_particle_material_context,
        notes=["Illustrative SCCS opinion record for nano-enabled cosmetics."],
    )
    sccs_opinion_product_use_evidence = build_product_use_evidence_from_sccs_opinion(
        sccs_opinion_evidence_record
    )
    cosing_ingredient_record = CosIngIngredientRecord(
        chemical_id="DTXSID7020182",
        preferred_name="Example Nano UV Filter",
        inciName="Titanium Dioxide",
        casrn="13463-67-7",
        ecNumber="236-675-5",
        cosingLocator="https://single-market-economy.ec.europa.eu/sectors/cosmetics/cosmetic-ingredient-database_en",
        functions=["UV filter", "Opacifying"],
        annexReferences=["Annex VI"],
        nanomaterialFlag=True,
        particleMaterialContext=nano_particle_material_context,
        notes=["Illustrative CosIng identity/function record for a cosmetic UV filter."],
    )
    cosing_product_use_evidence = build_product_use_evidence_from_cosing(cosing_ingredient_record)
    nanomaterial_evidence_record = NanoMaterialEvidenceRecord(
        chemical_id="DTXSID7020182",
        preferred_name="Example Nano UV Filter",
        casrn="13463-67-7",
        sourceRecordId="sccs_nano_guidance_uv_filter_mock_2026",
        sourceTitle="SCCS Guidance on the safety assessment of nanomaterials in cosmetics",
        sourceVersion="2nd revision",
        sourceLocator="https://health.ec.europa.eu/publications/sccs-guidance-safety-assessment-nanomaterials-cosmetics-2nd-revision_en",
        sourceProgram="SCCS",
        cosmeticProductTypes=["Spray sunscreen", "Face cream"],
        supportedRoutes=[Route.DERMAL, Route.INHALATION],
        physical_forms=["spray", "cream"],
        application_methods=["aerosol_spray", "hand_application"],
        retention_types=["leave_on"],
        particleMaterialContext=nano_particle_material_context,
        jurisdictions=["EU", "SCCS", "CPNP"],
        notes=["Illustrative nanomaterial guidance record for EU cosmetic products."],
    )
    nanomaterial_product_use_evidence = build_product_use_evidence_from_nanomaterial(
        nanomaterial_evidence_record
    )
    synthetic_polymer_microparticle_evidence_record = SyntheticPolymerMicroparticleEvidenceRecord(
        chemical_id="DTXSID7020182",
        preferred_name="Example Polymeric Glitter Particle",
        sourceRecordId="echa_microplastics_personal_care_mock_2026",
        sourceTitle="ECHA microplastics restriction and reporting context",
        sourceVersion="2026 guidance context",
        sourceLocator="https://echa.europa.eu/hot-topics/microplastics",
        restrictionScope="Synthetic polymer microparticles in direct-use cosmetic products",
        productUseCategories=["personal_care"],
        supportedRoutes=[Route.DERMAL, Route.ORAL],
        physical_forms=["gel", "cream"],
        application_methods=["hand_application"],
        retention_types=["leave_on", "rinse_off"],
        particleMaterialContext=microplastic_particle_material_context,
        notes=["Illustrative synthetic polymer microparticle regulatory context."],
    )
    synthetic_polymer_microparticle_product_use_evidence = (
        build_product_use_evidence_from_synthetic_polymer_microparticle(
            synthetic_polymer_microparticle_evidence_record
        )
    )
    non_plastic_particle_product_use_evidence_record = NanoMaterialEvidenceRecord(
        chemical_id="DTXSID7020182",
        preferred_name="Example Silica Particle",
        casrn="7631-86-9",
        sourceRecordId="non_plastic_particle_guidance_mock_2026",
        sourceTitle="Illustrative non-plastic micro/nanoparticle cosmetics context",
        sourceVersion="2026 mock example",
        sourceLocator="https://health.ec.europa.eu/scientific-committees/scientific-committee-consumer-safety-sccs_en",
        sourceProgram="SCCS",
        cosmeticProductTypes=["Loose powder cosmetic"],
        supportedRoutes=[Route.DERMAL, Route.INHALATION],
        physical_forms=["powder"],
        application_methods=["dusting"],
        retention_types=["leave_on"],
        particleMaterialContext=non_plastic_particle_material_context,
        notes=["Illustrative non-plastic particle context for powders and pigments."],
    )
    non_plastic_particle_product_use_evidence = build_product_use_evidence_from_nanomaterial(
        non_plastic_particle_product_use_evidence_record
    )
    product_use_evidence_record = ProductUseEvidenceRecord(
        chemical_id="DTXSID7020182",
        preferred_name="Example Solvent A",
        casrn="123-45-6",
        source_name="EU product-use dossier example",
        source_kind="regulatory_dossier",
        review_status="reviewed",
        source_record_id="EU-DOSSIER-001",
        source_locator="https://example.org/eu-dossier/001",
        product_name="Example Surface Spray",
        product_subtype="indoor_surface_insecticide",
        product_use_categories=["pesticide"],
        physical_forms=["spray"],
        application_methods=["trigger_spray"],
        retention_types=["surface_contact"],
        region_scopes=["EU"],
        jurisdictions=["EU"],
        physchem_summary={"density_g_per_ml": 1.08},
        evidence_sources=["EU-Dossier:mock-001"],
        notes=["Illustrative region-specific product-use evidence for a spray pesticide."],
    )
    product_use_fit_report = assess_product_use_evidence_fit(
        inhalation_request,
        product_use_evidence_record,
    )
    product_use_enriched_request = apply_product_use_evidence(
        inhalation_request,
        product_use_evidence_record,
    )
    product_use_reconciliation_report = reconcile_product_use_evidence(
        inhalation_request,
        [
            comp_tox_product_use_evidence,
            cons_expo_product_use_evidence,
            product_use_evidence_record,
        ],
    )
    integrated_exposure_workflow_request = RunIntegratedExposureWorkflowInput(
        request=inhalation_request,
        compToxRecord=comp_tox_record,
        consExpoRecords=[cons_expo_evidence_record],
        evidenceRecords=[product_use_evidence_record],
        pbpkRegimenName="screening_daily_use",
        pbpkContextOfUse="screening-brief",
    )
    integrated_exposure_workflow_result = run_integrated_exposure_workflow(
        integrated_exposure_workflow_request,
        registry=defaults_registry,
        generated_at=EXAMPLE_GENERATED_AT,
    )
    worker_task_routing_request = WorkerTaskRoutingInput(
        chemical_id="DTXSID7020182",
        route=Route.INHALATION,
        scenario_class=ScenarioClass.INHALATION,
        product_use_profile=ProductUseProfile(
            product_name="Example Workplace Disinfectant Spray",
            product_category="disinfectant",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.03,
            use_amount_per_event=15,
            use_amount_unit=ProductAmountUnit.ML,
            use_events_per_day=2,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=75,
            inhalation_rate_m3_per_hour=1.1,
            demographic_tags=["worker", "occupational"],
            region="EU",
        ),
        requested_tier=TierLevel.TIER_1,
    )
    worker_task_routing_decision = route_worker_task(worker_task_routing_request, defaults_registry)
    worker_inhalation_tier2_bridge_request = ExportWorkerInhalationTier2BridgeRequest(
        baseRequest=InhalationTier1ScenarioRequest(
            chemical_id="DTXSID7020182",
            chemical_name="Example Solvent A",
            route=Route.INHALATION,
            product_use_profile=ProductUseProfile(
                product_name="Example Workplace Disinfectant Spray",
                product_category="disinfectant",
                physical_form="spray",
                application_method="trigger_spray",
                retention_type="surface_contact",
                concentration_fraction=0.03,
                use_amount_per_event=15,
                use_amount_unit=ProductAmountUnit.ML,
                use_events_per_day=2,
                room_volume_m3=35,
                air_exchange_rate_per_hour=2.0,
                exposure_duration_hours=0.5,
            ),
            population_profile=PopulationProfile(
                population_group="adult",
                body_weight_kg=75,
                inhalation_rate_m3_per_hour=1.1,
                demographic_tags=["worker", "occupational"],
                region="EU",
            ),
            source_distance_m=0.35,
            spray_duration_seconds=10.0,
            near_field_volume_m3=2.0,
            airflow_directionality=AirflowDirectionality.CROSS_DRAFT,
            particle_size_regime=ParticleSizeRegime.COARSE_SPRAY,
        ),
        targetModelFamily=WorkerTier2ModelFamily.ART,
        taskDescription="Worker trigger-spray disinfection task needing Tier 2 refinement",
        workplaceSetting="janitorial closet",
        taskDurationHours=0.5,
        ventilationContext=WorkerVentilationContext.GENERAL_VENTILATION,
        localControls=["general ventilation", "task segregation"],
        respiratoryProtection="none",
        emissionDescriptor="short trigger-spray cleaning mist near the breathing zone",
        contextOfUse="worker-tier2-bridge",
        notes=["Illustrative worker inhalation bridge package for a future ART-style adapter."],
    )
    worker_inhalation_tier2_bridge_package = build_worker_inhalation_tier2_bridge(
        worker_inhalation_tier2_bridge_request,
        registry=defaults_registry,
        generated_at=EXAMPLE_GENERATED_AT,
    )
    worker_inhalation_tier2_adapter_request = (
        worker_inhalation_tier2_bridge_package.tool_call.arguments
    )
    worker_inhalation_tier2_adapter_ingest_result = ingest_worker_inhalation_tier2_task(
        worker_inhalation_tier2_adapter_request,
        registry=defaults_registry,
        generated_at=EXAMPLE_GENERATED_AT,
    )
    worker_inhalation_tier2_execution_request = ExecuteWorkerInhalationTier2Request(
        adapterRequest=worker_inhalation_tier2_adapter_request,
        executionOverrides=WorkerInhalationTier2ExecutionOverrides(
            controlFactor=0.7,
            respiratoryProtectionFactor=0.5,
        ),
        contextOfUse="worker-art-execution",
    )
    worker_inhalation_tier2_execution_result = execute_worker_inhalation_tier2_task(
        worker_inhalation_tier2_execution_request,
        registry=defaults_registry,
        generated_at=EXAMPLE_GENERATED_AT,
    )
    worker_art_execution_package_request = ExportWorkerArtExecutionPackageRequest(
        adapterRequest=worker_inhalation_tier2_adapter_request,
        contextOfUse="worker-art-external-exchange",
    )
    worker_art_execution_package = export_worker_inhalation_art_execution_package(
        worker_art_execution_package_request,
        registry=defaults_registry,
        generated_at=EXAMPLE_GENERATED_AT,
    )
    worker_art_external_result = WorkerArtExternalExecutionResult(
        sourceSystem="ART",
        sourceRunId="art-run-001",
        modelVersion="ART-1.5.0",
        resultStatus="completed",
        breathingZoneConcentrationMgPerM3=0.72,
        inhaledMassMgPerDay=1.575,
        normalizedExternalDoseMgPerKgDay=0.021,
        determinantSnapshot={
            "workplaceSettingType": "janitorial_closet_or_small_room",
            "ventilationDeterminant": "general_ventilation",
            "taskFamily": "janitorial_disinfectant_trigger_spray",
        },
        qualityNotes=[],
        rawArtifacts=[
            WorkerArtExternalArtifact(
                label="ART run summary",
                locator="artifact://art-run-001/summary.json",
                mediaType="application/json",
                adapterHint=WorkerArtArtifactAdapterId.EXECUTION_REPORT_JSON_V1,
                contentJson={
                    "schemaVersion": "artWorkerExecutionReport.v1",
                    "run": {"id": "art-run-001", "modelVersion": "ART-1.5.0"},
                    "task": {"durationHours": 0.5},
                    "results": {
                        "status": "completed",
                        "taskDurationHours": 0.5,
                        "breathingZoneConcentrationMgPerM3": 0.72,
                        "inhaledMassMgPerDay": 1.575,
                        "normalizedExternalDoseMgPerKgDay": 0.021,
                    },
                    "determinants": {
                        "workplaceSettingType": "janitorial_closet_or_small_room",
                        "ventilationDeterminant": "general_ventilation",
                        "taskFamily": "janitorial_disinfectant_trigger_spray",
                    },
                },
                note="Illustrative nested external ART runner report artifact.",
            )
        ],
    )
    worker_art_execution_result_import_request = ImportWorkerArtExecutionResultRequest(
        adapterRequest=worker_inhalation_tier2_adapter_request,
        externalResult=worker_art_external_result,
        contextOfUse="worker-art-external-import",
    )
    worker_art_execution_result_import = import_worker_inhalation_art_execution_result(
        worker_art_execution_result_import_request,
        registry=defaults_registry,
        generated_at=EXAMPLE_GENERATED_AT,
    )
    worker_dermal_absorbed_dose_bridge_request = ExportWorkerDermalAbsorbedDoseBridgeRequest(
        baseRequest=ExposureScenarioRequest(
            chemical_id="DTXSID7020182",
            chemical_name="Example Solvent A",
            route=Route.DERMAL,
            scenario_class=ScenarioClass.SCREENING,
            product_use_profile=ProductUseProfile(
                product_name="Example Workplace Wipe Cleaner",
                product_category="household_cleaner",
                physical_form="liquid",
                application_method="wipe",
                retention_type="surface_contact",
                concentration_fraction=0.02,
                use_amount_per_event=10,
                use_amount_unit=ProductAmountUnit.G,
                use_events_per_day=3,
                exposure_duration_hours=0.75,
            ),
            population_profile=PopulationProfile(
                population_group="adult",
                body_weight_kg=75,
                exposed_surface_area_cm2=840,
                demographic_tags=["worker", "occupational"],
                region="EU",
            ),
        ),
        targetModelFamily=WorkerDermalModelFamily.DERMAL_ABSORPTION_PPE,
        taskDescription="Worker wet-wipe cleaning task with gloved hand contact",
        workplaceSetting="custodial closet",
        contactDurationHours=0.75,
        contactPattern=WorkerDermalContactPattern.SURFACE_TRANSFER,
        exposedBodyAreas=["hands"],
        ppeState=WorkerDermalPpeState.WORK_GLOVES,
        controlMeasures=["task segregation", "prompt hand washing"],
        surfaceLoadingContext="wet cleaning cloth contact with surface residue transfer",
        contextOfUse="worker-dermal-bridge",
        notes=["Illustrative worker dermal bridge package for a future absorbed-dose workflow."],
    )
    worker_dermal_absorbed_dose_bridge_package = build_worker_dermal_absorbed_dose_bridge(
        worker_dermal_absorbed_dose_bridge_request,
        registry=defaults_registry,
        generated_at=EXAMPLE_GENERATED_AT,
    )
    worker_dermal_absorbed_dose_adapter_request = (
        worker_dermal_absorbed_dose_bridge_package.tool_call.arguments
    )
    worker_dermal_absorbed_dose_adapter_ingest_result = ingest_worker_dermal_absorbed_dose_task(
        worker_dermal_absorbed_dose_adapter_request,
        registry=defaults_registry,
        generated_at=EXAMPLE_GENERATED_AT,
    )
    worker_dermal_absorbed_dose_execution_request = ExecuteWorkerDermalAbsorbedDoseRequest(
        adapterRequest=worker_dermal_absorbed_dose_adapter_request,
        executionOverrides=WorkerDermalAbsorbedDoseExecutionOverrides(ppePenetrationFactor=0.3),
        contextOfUse="worker-dermal-execution",
    )
    worker_dermal_absorbed_dose_execution_result = execute_worker_dermal_absorbed_dose_task(
        worker_dermal_absorbed_dose_execution_request,
        registry=defaults_registry,
        generated_at=EXAMPLE_GENERATED_AT,
    )
    toxclaw_evidence = build_toxclaw_evidence_envelope(
        dermal_scenario,
        context_of_use="screening_prioritization",
    )
    toxclaw_evidence_bundle = build_toxclaw_evidence_bundle(
        ExportToxClawEvidenceBundleRequest(
            scenario=dermal_scenario,
            case_id="case-example-001",
            report_id="report-example-001",
            context_of_use="screening-brief",
        )
    )
    toxclaw_refinement_bundle = build_toxclaw_refinement_bundle(
        ExportToxClawRefinementBundleRequest(
            baseline=dermal_scenario,
            comparison=refined_scenario,
            case_id="case-example-001",
            report_id="report-example-001",
            workflow_action="scenario_comparison",
        ),
        generated_at=EXAMPLE_GENERATED_AT,
    )
    pbpk_compatibility = check_pbpk_compatibility(dermal_scenario)
    pbpk_external_import_package = build_pbpk_external_import_package(
        ExportPbpkExternalImportBundleRequest(
            scenario=dermal_scenario,
            context_of_use="screening-brief",
        ),
        generated_at=EXAMPLE_GENERATED_AT,
    )
    tool_result_meta_completed = build_tool_result_meta(
        result_status="completed",
        payload_model=dermal_scenario,
    )
    tool_result_meta_failed = build_tool_result_meta(
        result_status="failed",
        error=ExposureScenarioError(
            code="example_failure",
            message="Illustrative failure for result-status metadata.",
        ),
    )
    return {
        "chemical_identity": chemical_identity.model_dump(mode="json", by_alias=True),
        "exposure_scenario_definition": exposure_scenario_definition.model_dump(
            mode="json", by_alias=True
        ),
        "tcm_medicinal_oral_request": tcm_medicinal_oral_request.model_dump(
            mode="json", by_alias=True
        ),
        "botanical_supplement_oral_request": botanical_supplement_oral_request.model_dump(
            mode="json", by_alias=True
        ),
        "dietary_supplement_oral_request": dietary_supplement_oral_request.model_dump(
            mode="json", by_alias=True
        ),
        "herbal_medicinal_infusion_request": herbal_medicinal_infusion_request.model_dump(
            mode="json", by_alias=True
        ),
        "tcm_topical_balm_request": tcm_topical_balm_request.model_dump(mode="json", by_alias=True),
        "herbal_topical_spray_request": herbal_topical_spray_request.model_dump(
            mode="json", by_alias=True
        ),
        "herbal_recovery_patch_request": herbal_recovery_patch_request.model_dump(
            mode="json", by_alias=True
        ),
        "capsicum_hydrogel_patch_request": capsicum_hydrogel_patch_request.model_dump(
            mode="json", by_alias=True
        ),
        "route_dose_estimate": route_dose_estimate.model_dump(mode="json", by_alias=True),
        "environmental_release_scenario": environmental_release_scenario.model_dump(
            mode="json", by_alias=True
        ),
        "concentration_surface": concentration_surface.model_dump(mode="json", by_alias=True),
        "screening_dermal_request": dermal_request.model_dump(mode="json", by_alias=True),
        "screening_dermal_scenario": dermal_scenario.model_dump(mode="json", by_alias=True),
        "inhalation_request": inhalation_request.model_dump(mode="json", by_alias=True),
        "inhalation_scenario": inhalation_scenario.model_dump(mode="json", by_alias=True),
        "inhalation_residual_reentry_request": inhalation_residual_reentry_request.model_dump(
            mode="json", by_alias=True
        ),
        "inhalation_residual_reentry_scenario": (
            inhalation_residual_reentry_scenario.model_dump(mode="json", by_alias=True)
        ),
        "inhalation_residual_reentry_native_request": (
            inhalation_residual_reentry_native_request.model_dump(mode="json", by_alias=True)
        ),
        "inhalation_residual_reentry_native_scenario": (
            inhalation_residual_reentry_native_scenario.model_dump(mode="json", by_alias=True)
        ),
        "inhalation_tier1_request": inhalation_tier1_request.model_dump(mode="json", by_alias=True),
        "inhalation_tier1_request_two_zone": inhalation_tier1_request_two_zone.model_dump(
            mode="json", by_alias=True
        ),
        "inhalation_tier1_scenario": inhalation_tier1_scenario.model_dump(
            mode="json", by_alias=True
        ),
        "build_envelope_request": envelope_input.model_dump(mode="json", by_alias=True),
        "exposure_envelope_summary": envelope_summary.model_dump(mode="json", by_alias=True),
        "exposure_envelope_from_library_request": library_envelope_request.model_dump(
            mode="json", by_alias=True
        ),
        "exposure_envelope_from_library_summary": library_envelope_summary.model_dump(
            mode="json", by_alias=True
        ),
        "inhalation_tier1_envelope_from_library_request": (
            tier1_library_envelope_request.model_dump(mode="json", by_alias=True)
        ),
        "inhalation_tier1_envelope_from_library_summary": (
            tier1_library_envelope_summary.model_dump(mode="json", by_alias=True)
        ),
        "parameter_bounds_summary": parameter_bounds_summary.model_dump(mode="json", by_alias=True),
        "probability_bounds_from_profile_request": probability_bounds_request.model_dump(
            mode="json", by_alias=True
        ),
        "probability_bounds_profile_summary": probability_bounds_summary.model_dump(
            mode="json", by_alias=True
        ),
        "scenario_package_probability_request": scenario_package_probability_request.model_dump(
            mode="json", by_alias=True
        ),
        "scenario_package_probability_summary": (
            scenario_package_probability_summary.model_dump(mode="json", by_alias=True)
        ),
        "inhalation_tier1_scenario_package_probability_request": (
            tier1_scenario_package_probability_request.model_dump(mode="json", by_alias=True)
        ),
        "inhalation_tier1_scenario_package_probability_summary": (
            tier1_scenario_package_probability_summary.model_dump(mode="json", by_alias=True)
        ),
        "aggregate_scenario_request": aggregate_input.model_dump(mode="json", by_alias=True),
        "aggregate_summary": aggregate_summary.model_dump(mode="json", by_alias=True),
        "aggregate_internal_equivalent_summary": aggregate_internal_equivalent_summary.model_dump(
            mode="json", by_alias=True
        ),
        "export_pbpk_request": pbpk_request.model_dump(mode="json", by_alias=True),
        "pbpk_input": pbpk_input.model_dump(mode="json", by_alias=True),
        "pbpk_input_transient": pbpk_input_transient.model_dump(mode="json", by_alias=True),
        "pbpk_external_import_request": pbpk_external_import_package.request_payload.model_dump(
            mode="json", by_alias=True
        ),
        "pbpk_external_import_tool_call": pbpk_external_import_package.tool_call.model_dump(
            mode="json", by_alias=True
        ),
        "toxclaw_pbpk_module_params": pbpk_external_import_package.toxclaw_module_params.model_dump(
            mode="json", by_alias=True
        ),
        "pbpk_external_import_package": pbpk_external_import_package.model_dump(
            mode="json", by_alias=True
        ),
        "compare_scenarios_request": comparison_input.model_dump(mode="json", by_alias=True),
        "comparison_record": comparison.model_dump(mode="json", by_alias=True),
        "compare_jurisdictional_scenarios_request": (
            jurisdictional_comparison_input.model_dump(mode="json", by_alias=True)
        ),
        "jurisdictional_comparison_result": jurisdictional_comparison.model_dump(
            mode="json", by_alias=True
        ),
        "comp_tox_record": comp_tox_record.model_dump(mode="json", by_alias=True),
        "comp_tox_enriched_request": comp_tox_enriched_request.model_dump(
            mode="json", by_alias=True
        ),
        "cons_expo_evidence_record": cons_expo_evidence_record.model_dump(
            mode="json", by_alias=True
        ),
        "cons_expo_product_use_evidence": cons_expo_product_use_evidence.model_dump(
            mode="json", by_alias=True
        ),
        "sccs_evidence_record": sccs_evidence_record.model_dump(mode="json", by_alias=True),
        "sccs_product_use_evidence": sccs_product_use_evidence.model_dump(
            mode="json", by_alias=True
        ),
        "sccs_opinion_evidence_record": sccs_opinion_evidence_record.model_dump(
            mode="json", by_alias=True
        ),
        "sccs_opinion_product_use_evidence": sccs_opinion_product_use_evidence.model_dump(
            mode="json", by_alias=True
        ),
        "cosing_ingredient_record": cosing_ingredient_record.model_dump(mode="json", by_alias=True),
        "cosing_product_use_evidence": cosing_product_use_evidence.model_dump(
            mode="json", by_alias=True
        ),
        "nanomaterial_evidence_record": nanomaterial_evidence_record.model_dump(
            mode="json", by_alias=True
        ),
        "nanomaterial_product_use_evidence": nanomaterial_product_use_evidence.model_dump(
            mode="json", by_alias=True
        ),
        "synthetic_polymer_microparticle_evidence_record": (
            synthetic_polymer_microparticle_evidence_record.model_dump(mode="json", by_alias=True)
        ),
        "synthetic_polymer_microparticle_product_use_evidence": (
            synthetic_polymer_microparticle_product_use_evidence.model_dump(
                mode="json", by_alias=True
            )
        ),
        "non_plastic_particle_product_use_evidence_record": (
            non_plastic_particle_product_use_evidence_record.model_dump(mode="json", by_alias=True)
        ),
        "non_plastic_particle_product_use_evidence": (
            non_plastic_particle_product_use_evidence.model_dump(mode="json", by_alias=True)
        ),
        "product_use_evidence_record": product_use_evidence_record.model_dump(
            mode="json", by_alias=True
        ),
        "product_use_evidence_fit_report": product_use_fit_report.model_dump(
            mode="json", by_alias=True
        ),
        "product_use_evidence_enriched_request": product_use_enriched_request.model_dump(
            mode="json", by_alias=True
        ),
        "product_use_evidence_reconciliation_report": (
            product_use_reconciliation_report.model_dump(mode="json", by_alias=True)
        ),
        "integrated_exposure_workflow_request": (
            integrated_exposure_workflow_request.model_dump(mode="json", by_alias=True)
        ),
        "integrated_exposure_workflow_result": _freeze_integrated_workflow_result(
            integrated_exposure_workflow_result
        ),
        "worker_task_routing_request": worker_task_routing_request.model_dump(
            mode="json", by_alias=True
        ),
        "worker_task_routing_decision": worker_task_routing_decision.model_dump(
            mode="json", by_alias=True
        ),
        "worker_inhalation_tier2_bridge_request": (
            worker_inhalation_tier2_bridge_request.model_dump(mode="json", by_alias=True)
        ),
        "worker_inhalation_tier2_bridge_package": (
            worker_inhalation_tier2_bridge_package.model_dump(mode="json", by_alias=True)
        ),
        "worker_inhalation_tier2_adapter_request": (
            worker_inhalation_tier2_adapter_request.model_dump(mode="json", by_alias=True)
        ),
        "worker_inhalation_tier2_adapter_ingest_result": (
            worker_inhalation_tier2_adapter_ingest_result.model_dump(mode="json", by_alias=True)
        ),
        "worker_inhalation_tier2_execution_request": (
            worker_inhalation_tier2_execution_request.model_dump(
                mode="json",
                by_alias=True,
            )
        ),
        "worker_inhalation_tier2_execution_result": (
            worker_inhalation_tier2_execution_result.model_dump(
                mode="json",
                by_alias=True,
            )
        ),
        "worker_art_execution_package_request": (
            worker_art_execution_package_request.model_dump(mode="json", by_alias=True)
        ),
        "worker_art_execution_package": (
            worker_art_execution_package.model_dump(mode="json", by_alias=True)
        ),
        "worker_art_external_result": worker_art_external_result.model_dump(
            mode="json",
            by_alias=True,
        ),
        "worker_art_execution_result_import_request": (
            worker_art_execution_result_import_request.model_dump(mode="json", by_alias=True)
        ),
        "worker_art_execution_result_import": (
            worker_art_execution_result_import.model_dump(mode="json", by_alias=True)
        ),
        "worker_dermal_absorbed_dose_bridge_request": (
            worker_dermal_absorbed_dose_bridge_request.model_dump(mode="json", by_alias=True)
        ),
        "worker_dermal_absorbed_dose_bridge_package": (
            worker_dermal_absorbed_dose_bridge_package.model_dump(mode="json", by_alias=True)
        ),
        "worker_dermal_absorbed_dose_adapter_request": (
            worker_dermal_absorbed_dose_adapter_request.model_dump(mode="json", by_alias=True)
        ),
        "worker_dermal_absorbed_dose_adapter_ingest_result": (
            worker_dermal_absorbed_dose_adapter_ingest_result.model_dump(mode="json", by_alias=True)
        ),
        "worker_dermal_absorbed_dose_execution_request": (
            worker_dermal_absorbed_dose_execution_request.model_dump(
                mode="json",
                by_alias=True,
            )
        ),
        "worker_dermal_absorbed_dose_execution_result": (
            worker_dermal_absorbed_dose_execution_result.model_dump(
                mode="json",
                by_alias=True,
            )
        ),
        "toxclaw_evidence_envelope": toxclaw_evidence.model_dump(mode="json", by_alias=True),
        "toxclaw_evidence_bundle": toxclaw_evidence_bundle.model_dump(mode="json", by_alias=True),
        "toxclaw_refinement_bundle": toxclaw_refinement_bundle.model_dump(
            mode="json", by_alias=True
        ),
        "pbpk_compatibility_report": pbpk_compatibility.model_dump(mode="json", by_alias=True),
        "tool_result_meta_completed": tool_result_meta_completed,
        "tool_result_meta_failed": tool_result_meta_failed,
    }
