"""Schema, example, and manifest helpers."""

from __future__ import annotations

import tomllib
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel

from exposure_scenario_mcp.archetypes import ArchetypeLibraryRegistry
from exposure_scenario_mcp.assets import repo_path
from exposure_scenario_mcp.benchmarks import load_benchmark_manifest, load_goldset_manifest
from exposure_scenario_mcp.defaults import DefaultsRegistry, build_defaults_curation_report
from exposure_scenario_mcp.examples import build_examples
from exposure_scenario_mcp.http_security import streamable_http_boundary_controls_available
from exposure_scenario_mcp.integrations import (
    ApplyProductUseEvidenceInput,
    AssessProductUseEvidenceFitInput,
    BuildProductUseEvidenceFromConsExpoInput,
    BuildProductUseEvidenceFromCosIngInput,
    BuildProductUseEvidenceFromNanoMaterialInput,
    BuildProductUseEvidenceFromSccsInput,
    BuildProductUseEvidenceFromSccsOpinionInput,
    BuildProductUseEvidenceFromSyntheticPolymerMicroparticleInput,
    CompToxChemicalRecord,
    ConsExpoEvidenceRecord,
    CosIngIngredientRecord,
    ExposureWorkflowHook,
    IntegratedExposureWorkflowResult,
    NanoMaterialEvidenceRecord,
    PbpkCompatibilityReport,
    PbpkExternalImportBundle,
    PbpkExternalImportPackage,
    PbpkExternalImportRequest,
    PbpkExternalImportToolCall,
    ProductUseEvidenceFitReport,
    ProductUseEvidenceReconciliationReport,
    ProductUseEvidenceRecord,
    ReconcileProductUseEvidenceInput,
    RunIntegratedExposureWorkflowInput,
    SccsCosmeticsEvidenceRecord,
    SccsOpinionEvidenceRecord,
    SyntheticPolymerMicroparticleEvidenceRecord,
    ToxClawEvidenceBundle,
    ToxClawEvidenceEnvelope,
    ToxClawEvidenceRecord,
    ToxClawExposureRefinementBundle,
    ToxClawExposureRefinementSignal,
    ToxClawPbpkModuleParams,
    ToxClawReportClaim,
    ToxClawReportEvidenceReference,
    ToxClawReportSection,
)
from exposure_scenario_mcp.models import (
    AggregateExposureSummary,
    ArchetypeLibraryManifest,
    ArchetypeLibrarySet,
    ArchetypeLibraryTemplate,
    AssumptionGovernance,
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
    ContractManifest,
    ContractPromptEntry,
    ContractResourceEntry,
    ContractToolEntry,
    DefaultsCurationEntry,
    DefaultsCurationReport,
    DefaultsCurationStatus,
    DependencyDescriptor,
    EnvelopeArchetypeInput,
    EnvelopeArchetypeResult,
    EnvelopeDriverAttribution,
    EnvironmentalReleaseScenario,
    ExecutedValidationCheck,
    ExportPbpkExternalImportBundleRequest,
    ExportPbpkScenarioInputRequest,
    ExportToxClawEvidenceBundleRequest,
    ExportToxClawRefinementBundleRequest,
    ExposureAssumptionRecord,
    ExposureEnvelopeSummary,
    ExposureScenario,
    ExposureScenarioDefinition,
    ExposureScenarioRequest,
    ExternalValidationDataset,
    InhalationResidualAirReentryScenarioRequest,
    InhalationScenarioRequest,
    InhalationTier1ScenarioRequest,
    JurisdictionalComparisonResult,
    MonotonicityCheck,
    ParameterBoundInput,
    ParameterBoundsSummary,
    ParticleMaterialContext,
    PbpkScenarioInput,
    PhyschemContext,
    PopulationProfile,
    ProbabilityBoundDosePoint,
    ProbabilityBoundsDriverProfile,
    ProbabilityBoundsProfileManifest,
    ProbabilityBoundsProfileSummary,
    ProbabilityBoundSupportPointDefinition,
    ProductUseProfile,
    ProvenanceBundle,
    PublicSurfaceSummary,
    ReleaseDistributionArtifact,
    ReleaseMetadataReport,
    ReleaseReadinessCheck,
    ReleaseReadinessReport,
    ReviewedSurfaceIndex,
    RouteDoseEstimate,
    ScenarioComparisonRecord,
    ScenarioPackageProbabilityManifest,
    ScenarioPackageProbabilityPointDefinition,
    ScenarioPackageProbabilityPointResult,
    ScenarioPackageProbabilityProfile,
    ScenarioPackageProbabilitySummary,
    SecurityProvenanceReviewFinding,
    SecurityProvenanceReviewReport,
    SensitivityRankingEntry,
    Tier1AirflowClassProfile,
    Tier1InhalationParameterManifest,
    Tier1InhalationProductProfile,
    Tier1InhalationTemplateParameters,
    Tier1ParticleRegimeProfile,
    TierSemantics,
    TierUpgradeAdvisory,
    TierUpgradeInputRequirement,
    ToolResultMeta,
    UncertaintyRegisterEntry,
    ValidationBenchmarkDomain,
    ValidationCoverageDomainSummary,
    ValidationCoverageReport,
    ValidationDossierReport,
    ValidationGap,
    ValidationReferenceBand,
    ValidationReferenceBandManifest,
    ValidationSummary,
    ValidationTimeSeriesReferenceManifest,
    ValidationTimeSeriesReferencePack,
    ValidationTimeSeriesReferencePoint,
    VerificationCheck,
    VerificationSummaryReport,
    WorkerTaskRoutingDecision,
    WorkerTaskRoutingInput,
)
from exposure_scenario_mcp.package_metadata import (
    CURRENT_RELEASE_NOTES_RELATIVE_PATH,
    CURRENT_RELEASE_TAG,
    CURRENT_VERSION,
    PACKAGE_NAME,
)
from exposure_scenario_mcp.probability_profiles import ProbabilityBoundsProfileRegistry
from exposure_scenario_mcp.release_artifacts import distribution_artifacts_for_release
from exposure_scenario_mcp.scenario_probability_packages import ScenarioProbabilityPackageRegistry
from exposure_scenario_mcp.tier1_inhalation_profiles import Tier1InhalationProfileRegistry
from exposure_scenario_mcp.validation import build_validation_coverage_report
from exposure_scenario_mcp.validation_reference_bands import ValidationReferenceBandRegistry
from exposure_scenario_mcp.validation_time_series import ValidationTimeSeriesReferenceRegistry
from exposure_scenario_mcp.worker_dermal import (
    ExecuteWorkerDermalAbsorbedDoseRequest,
    ExportWorkerDermalAbsorbedDoseBridgeRequest,
    WorkerDermalAbsorbedDoseAdapterIngestResult,
    WorkerDermalAbsorbedDoseAdapterRequest,
    WorkerDermalAbsorbedDoseAdapterToolCall,
    WorkerDermalAbsorbedDoseBridgePackage,
    WorkerDermalAbsorbedDoseExecutionOverrides,
    WorkerDermalAbsorbedDoseExecutionResult,
    WorkerDermalAbsorbedDoseTaskEnvelope,
    WorkerDermalCompatibilityReport,
    WorkerDermalDeterminantTemplateMatch,
    WorkerDermalTaskContext,
)
from exposure_scenario_mcp.worker_tier2 import (
    ExecuteWorkerInhalationTier2Request,
    ExportWorkerArtExecutionPackageRequest,
    ExportWorkerInhalationTier2BridgeRequest,
    ImportWorkerArtExecutionResultRequest,
    WorkerArtDeterminantTemplateMatch,
    WorkerArtExternalArtifact,
    WorkerArtExternalExecutionPackage,
    WorkerArtExternalExecutionResult,
    WorkerArtExternalResultImportToolCall,
    WorkerInhalationArtTaskEnvelope,
    WorkerInhalationTier2AdapterIngestResult,
    WorkerInhalationTier2AdapterRequest,
    WorkerInhalationTier2AdapterToolCall,
    WorkerInhalationTier2BridgePackage,
    WorkerInhalationTier2CompatibilityReport,
    WorkerInhalationTier2ExecutionOverrides,
    WorkerInhalationTier2ExecutionResult,
    WorkerInhalationTier2TaskContext,
)

CheckStatus = Literal["pass", "warning", "blocked"]
ReadinessStatus = Literal["ready", "ready_with_known_limitations", "blocked"]
ReviewStatus = Literal["acceptable", "acceptable_with_warnings", "blocked"]


SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "chemicalIdentity.v1": ChemicalIdentity,
    "productUseProfile.v1": ProductUseProfile,
    "populationProfile.v1": PopulationProfile,
    "exposureScenarioDefinition.v1": ExposureScenarioDefinition,
    "routeDoseEstimate.v1": RouteDoseEstimate,
    "environmentalReleaseScenario.v1": EnvironmentalReleaseScenario,
    "concentrationSurface.v1": ConcentrationSurface,
    "exposureScenarioRequest.v1": ExposureScenarioRequest,
    "inhalationResidualAirReentryScenarioRequest.v1": InhalationResidualAirReentryScenarioRequest,
    "inhalationScenarioRequest.v1": InhalationScenarioRequest,
    "inhalationTier1ScenarioRequest.v1": InhalationTier1ScenarioRequest,
    "tier1AirflowClassProfile.v1": Tier1AirflowClassProfile,
    "tier1ParticleRegimeProfile.v1": Tier1ParticleRegimeProfile,
    "tier1InhalationProductProfile.v1": Tier1InhalationProductProfile,
    "tier1InhalationParameterManifest.v1": Tier1InhalationParameterManifest,
    "tier1InhalationTemplateParameters.v1": Tier1InhalationTemplateParameters,
    "exposureScenario.v1": ExposureScenario,
    "archetypeLibraryTemplate.v1": ArchetypeLibraryTemplate,
    "archetypeLibrarySet.v1": ArchetypeLibrarySet,
    "archetypeLibraryManifest.v1": ArchetypeLibraryManifest,
    "uncertaintyRegisterEntry.v1": UncertaintyRegisterEntry,
    "sensitivityRankingEntry.v1": SensitivityRankingEntry,
    "dependencyDescriptor.v1": DependencyDescriptor,
    "validationBenchmarkDomain.v1": ValidationBenchmarkDomain,
    "validationCoverageDomainSummary.v1": ValidationCoverageDomainSummary,
    "validationCoverageReport.v1": ValidationCoverageReport,
    "externalValidationDataset.v1": ExternalValidationDataset,
    "validationReferenceBand.v1": ValidationReferenceBand,
    "validationReferenceBandManifest.v1": ValidationReferenceBandManifest,
    "validationTimeSeriesReferencePoint.v1": ValidationTimeSeriesReferencePoint,
    "validationTimeSeriesReferencePack.v1": ValidationTimeSeriesReferencePack,
    "validationTimeSeriesReferenceManifest.v1": ValidationTimeSeriesReferenceManifest,
    "validationGap.v1": ValidationGap,
    "executedValidationCheck.v1": ExecutedValidationCheck,
    "defaultsCurationEntry.v1": DefaultsCurationEntry,
    "defaultsCurationReport.v1": DefaultsCurationReport,
    "validationDossierReport.v1": ValidationDossierReport,
    "validationSummary.v1": ValidationSummary,
    "tierUpgradeInputRequirement.v1": TierUpgradeInputRequirement,
    "tierUpgradeAdvisory.v1": TierUpgradeAdvisory,
    "workerTaskRoutingInput.v1": WorkerTaskRoutingInput,
    "workerTaskRoutingDecision.v1": WorkerTaskRoutingDecision,
    "workerInhalationTier2TaskContext.v1": WorkerInhalationTier2TaskContext,
    "workerInhalationTier2CompatibilityReport.v1": WorkerInhalationTier2CompatibilityReport,
    "workerInhalationTier2AdapterRequest.v1": WorkerInhalationTier2AdapterRequest,
    "workerInhalationTier2AdapterToolCall.v1": WorkerInhalationTier2AdapterToolCall,
    "workerInhalationTier2BridgePackage.v1": WorkerInhalationTier2BridgePackage,
    "exportWorkerInhalationTier2BridgeRequest.v1": ExportWorkerInhalationTier2BridgeRequest,
    "workerArtDeterminantTemplateMatch.v1": WorkerArtDeterminantTemplateMatch,
    "workerInhalationArtTaskEnvelope.v1": WorkerInhalationArtTaskEnvelope,
    "workerInhalationTier2AdapterIngestResult.v1": WorkerInhalationTier2AdapterIngestResult,
    "workerInhalationTier2ExecutionOverrides.v1": (WorkerInhalationTier2ExecutionOverrides),
    "executeWorkerInhalationTier2Request.v1": ExecuteWorkerInhalationTier2Request,
    "workerArtExternalArtifact.v1": WorkerArtExternalArtifact,
    "workerArtExternalExecutionResult.v1": WorkerArtExternalExecutionResult,
    "exportWorkerArtExecutionPackageRequest.v1": ExportWorkerArtExecutionPackageRequest,
    "workerArtExternalResultImportToolCall.v1": WorkerArtExternalResultImportToolCall,
    "workerArtExternalExecutionPackage.v1": WorkerArtExternalExecutionPackage,
    "importWorkerArtExecutionResultRequest.v1": ImportWorkerArtExecutionResultRequest,
    "workerInhalationTier2ExecutionResult.v1": WorkerInhalationTier2ExecutionResult,
    "workerDermalTaskContext.v1": WorkerDermalTaskContext,
    "workerDermalCompatibilityReport.v1": WorkerDermalCompatibilityReport,
    "workerDermalAbsorbedDoseAdapterRequest.v1": WorkerDermalAbsorbedDoseAdapterRequest,
    "workerDermalAbsorbedDoseAdapterToolCall.v1": WorkerDermalAbsorbedDoseAdapterToolCall,
    "workerDermalAbsorbedDoseBridgePackage.v1": WorkerDermalAbsorbedDoseBridgePackage,
    "exportWorkerDermalAbsorbedDoseBridgeRequest.v1": (ExportWorkerDermalAbsorbedDoseBridgeRequest),
    "workerDermalDeterminantTemplateMatch.v1": WorkerDermalDeterminantTemplateMatch,
    "workerDermalAbsorbedDoseTaskEnvelope.v1": WorkerDermalAbsorbedDoseTaskEnvelope,
    "workerDermalAbsorbedDoseAdapterIngestResult.v1": (WorkerDermalAbsorbedDoseAdapterIngestResult),
    "workerDermalAbsorbedDoseExecutionOverrides.v1": (WorkerDermalAbsorbedDoseExecutionOverrides),
    "executeWorkerDermalAbsorbedDoseRequest.v1": ExecuteWorkerDermalAbsorbedDoseRequest,
    "workerDermalAbsorbedDoseExecutionResult.v1": WorkerDermalAbsorbedDoseExecutionResult,
    "buildExposureEnvelopeFromLibraryInput.v1": BuildExposureEnvelopeFromLibraryInput,
    "probabilityBoundSupportPointDefinition.v1": ProbabilityBoundSupportPointDefinition,
    "probabilityBoundsDriverProfile.v1": ProbabilityBoundsDriverProfile,
    "probabilityBoundsProfileManifest.v1": ProbabilityBoundsProfileManifest,
    "buildProbabilityBoundsFromProfileInput.v1": BuildProbabilityBoundsFromProfileInput,
    "probabilityBoundDosePoint.v1": ProbabilityBoundDosePoint,
    "probabilityBoundsProfileSummary.v1": ProbabilityBoundsProfileSummary,
    "scenarioPackageProbabilityPointDefinition.v1": ScenarioPackageProbabilityPointDefinition,
    "scenarioPackageProbabilityProfile.v1": ScenarioPackageProbabilityProfile,
    "scenarioPackageProbabilityManifest.v1": ScenarioPackageProbabilityManifest,
    "buildProbabilityBoundsFromScenarioPackageInput.v1": (
        BuildProbabilityBoundsFromScenarioPackageInput
    ),
    "scenarioPackageProbabilityPointResult.v1": ScenarioPackageProbabilityPointResult,
    "scenarioPackageProbabilitySummary.v1": ScenarioPackageProbabilitySummary,
    "parameterBoundInput.v1": ParameterBoundInput,
    "monotonicityCheck.v1": MonotonicityCheck,
    "buildParameterBoundsInput.v1": BuildParameterBoundsInput,
    "parameterBoundsSummary.v1": ParameterBoundsSummary,
    "particleMaterialContext.v1": ParticleMaterialContext,
    "physchemContext.v1": PhyschemContext,
    "aggregateExposureSummary.v1": AggregateExposureSummary,
    "exposureAssumptionRecord.v1": ExposureAssumptionRecord,
    "assumptionGovernance.v1": AssumptionGovernance,
    "pbpkScenarioInput.v1": PbpkScenarioInput,
    "scenarioComparisonRecord.v1": ScenarioComparisonRecord,
    "provenanceBundle.v1": ProvenanceBundle,
    "tierSemantics.v1": TierSemantics,
    "buildExposureEnvelopeInput.v1": BuildExposureEnvelopeInput,
    "envelopeArchetypeInput.v1": EnvelopeArchetypeInput,
    "envelopeArchetypeResult.v1": EnvelopeArchetypeResult,
    "envelopeDriverAttribution.v1": EnvelopeDriverAttribution,
    "exposureEnvelopeSummary.v1": ExposureEnvelopeSummary,
    "buildAggregateExposureScenarioInput.v1": BuildAggregateExposureScenarioInput,
    "exportPbpkScenarioInputRequest.v1": ExportPbpkScenarioInputRequest,
    "exportPbpkExternalImportBundleRequest.v1": ExportPbpkExternalImportBundleRequest,
    "exportToxClawEvidenceBundleRequest.v1": ExportToxClawEvidenceBundleRequest,
    "exportToxClawRefinementBundleRequest.v1": ExportToxClawRefinementBundleRequest,
    "compareExposureScenariosInput.v1": CompareExposureScenariosInput,
    "compareJurisdictionalScenariosInput.v1": CompareJurisdictionalScenariosInput,
    "jurisdictionalComparisonResult.v1": JurisdictionalComparisonResult,
    "compToxChemicalRecord.v1": CompToxChemicalRecord,
    "consExpoEvidenceRecord.v1": ConsExpoEvidenceRecord,
    "sccsCosmeticsEvidenceRecord.v1": SccsCosmeticsEvidenceRecord,
    "sccsOpinionEvidenceRecord.v1": SccsOpinionEvidenceRecord,
    "cosIngIngredientRecord.v1": CosIngIngredientRecord,
    "nanoMaterialEvidenceRecord.v1": NanoMaterialEvidenceRecord,
    "syntheticPolymerMicroparticleEvidenceRecord.v1": (SyntheticPolymerMicroparticleEvidenceRecord),
    "buildProductUseEvidenceFromConsExpoInput.v1": BuildProductUseEvidenceFromConsExpoInput,
    "buildProductUseEvidenceFromSccsInput.v1": BuildProductUseEvidenceFromSccsInput,
    "buildProductUseEvidenceFromSccsOpinionInput.v1": (BuildProductUseEvidenceFromSccsOpinionInput),
    "buildProductUseEvidenceFromCosIngInput.v1": BuildProductUseEvidenceFromCosIngInput,
    "buildProductUseEvidenceFromNanoMaterialInput.v1": (
        BuildProductUseEvidenceFromNanoMaterialInput
    ),
    "buildProductUseEvidenceFromSyntheticPolymerMicroparticleInput.v1": (
        BuildProductUseEvidenceFromSyntheticPolymerMicroparticleInput
    ),
    "productUseEvidenceRecord.v1": ProductUseEvidenceRecord,
    "productUseEvidenceFitReport.v1": ProductUseEvidenceFitReport,
    "assessProductUseEvidenceFitInput.v1": AssessProductUseEvidenceFitInput,
    "applyProductUseEvidenceInput.v1": ApplyProductUseEvidenceInput,
    "productUseEvidenceReconciliationReport.v1": ProductUseEvidenceReconciliationReport,
    "reconcileProductUseEvidenceInput.v1": ReconcileProductUseEvidenceInput,
    "runIntegratedExposureWorkflowInput.v1": RunIntegratedExposureWorkflowInput,
    "integratedExposureWorkflowResult.v1": IntegratedExposureWorkflowResult,
    "toxclawEvidenceEnvelope.v1": ToxClawEvidenceEnvelope,
    "toxclawEvidenceRecord.v1": ToxClawEvidenceRecord,
    "toxclawReportEvidenceReference.v1": ToxClawReportEvidenceReference,
    "toxclawReportClaim.v1": ToxClawReportClaim,
    "toxclawReportSection.v1": ToxClawReportSection,
    "toxclawEvidenceBundle.v1": ToxClawEvidenceBundle,
    "exposureWorkflowHook.v1": ExposureWorkflowHook,
    "toxclawExposureRefinementSignal.v1": ToxClawExposureRefinementSignal,
    "toxclawExposureRefinementBundle.v1": ToxClawExposureRefinementBundle,
    "pbpkCompatibilityReport.v1": PbpkCompatibilityReport,
    "pbpkExternalImportBundle.v1": PbpkExternalImportBundle,
    "pbpkExternalImportRequest.v1": PbpkExternalImportRequest,
    "pbpkExternalImportToolCall.v1": PbpkExternalImportToolCall,
    "pbpkExternalImportPackage.v1": PbpkExternalImportPackage,
    "toxclawPbpkModuleParams.v1": ToxClawPbpkModuleParams,
    "toolResultMeta.v1": ToolResultMeta,
    "verificationCheck.v1": VerificationCheck,
    "verificationSummaryReport.v1": VerificationSummaryReport,
    "releaseMetadataReport.v1": ReleaseMetadataReport,
    "releaseReadinessReport.v1": ReleaseReadinessReport,
    "securityProvenanceReviewReport.v1": SecurityProvenanceReviewReport,
}


def schema_payloads() -> dict[str, dict]:
    return {name: model.model_json_schema() for name, model in SCHEMA_MODELS.items()}


def build_contract_manifest(defaults_registry: DefaultsRegistry) -> ContractManifest:
    examples = build_examples()
    return ContractManifest(
        server_name="exposure_scenario_mcp",
        server_version=CURRENT_VERSION,
        defaults_version=defaults_registry.version,
        tools=[
            ContractToolEntry(
                name="exposure_build_screening_exposure_scenario",
                request_schema="exposureScenarioRequest.v1",
                response_schema="exposureScenario.v1",
                description=(
                    "Build one deterministic dermal or oral external exposure screening scenario."
                ),
            ),
            ContractToolEntry(
                name="exposure_build_exposure_envelope",
                request_schema="buildExposureEnvelopeInput.v1",
                response_schema="exposureEnvelopeSummary.v1",
                description="Build a deterministic Tier B envelope from named scenario archetypes.",
            ),
            ContractToolEntry(
                name="exposure_build_exposure_envelope_from_library",
                request_schema="buildExposureEnvelopeFromLibraryInput.v1",
                response_schema="exposureEnvelopeSummary.v1",
                description=(
                    "Instantiate a packaged Tier B archetype-library set into a deterministic "
                    "envelope."
                ),
            ),
            ContractToolEntry(
                name="exposure_build_parameter_bounds_summary",
                request_schema="buildParameterBoundsInput.v1",
                response_schema="parameterBoundsSummary.v1",
                description=(
                    "Build a deterministic bounds-propagation summary from explicit lower "
                    "and upper parameter values."
                ),
            ),
            ContractToolEntry(
                name="exposure_build_probability_bounds_from_profile",
                request_schema="buildProbabilityBoundsFromProfileInput.v1",
                response_schema="probabilityBoundsProfileSummary.v1",
                description=(
                    "Build a packaged single-driver probability-bounds summary with "
                    "other scenario inputs fixed."
                ),
            ),
            ContractToolEntry(
                name="exposure_build_probability_bounds_from_scenario_package",
                request_schema="buildProbabilityBoundsFromScenarioPackageInput.v1",
                response_schema="scenarioPackageProbabilitySummary.v1",
                description=(
                    "Build a packaged coupled-driver probability-bounds summary from "
                    "scenario packages."
                ),
            ),
            ContractToolEntry(
                name="exposure_build_aggregate_exposure_scenario",
                request_schema="buildAggregateExposureScenarioInput.v1",
                response_schema="aggregateExposureSummary.v1",
                description=(
                    "Combine component scenarios into an external-dose summary or an "
                    "opt-in route-bioavailability-adjusted internal-equivalent screening summary."
                ),
            ),
            ContractToolEntry(
                name="exposure_assess_product_use_evidence_fit",
                request_schema="assessProductUseEvidenceFitInput.v1",
                response_schema="productUseEvidenceFitReport.v1",
                description=(
                    "Assess whether product-use evidence from CompTox or another source fits "
                    "the current scenario request."
                ),
            ),
            ContractToolEntry(
                name="exposure_apply_product_use_evidence",
                request_schema="applyProductUseEvidenceInput.v1",
                response_schema="exposureScenarioRequest.v1",
                description=(
                    "Apply compatible product-use evidence to a request while preserving "
                    "source and applicability metadata."
                ),
            ),
            ContractToolEntry(
                name="exposure_build_product_use_evidence_from_consexpo",
                request_schema="buildProductUseEvidenceFromConsExpoInput.v1",
                response_schema="productUseEvidenceRecord.v1",
                description=(
                    "Map a typed ConsExpo fact-sheet record into the generic product-use "
                    "evidence contract."
                ),
            ),
            ContractToolEntry(
                name="exposure_build_product_use_evidence_from_sccs",
                request_schema="buildProductUseEvidenceFromSccsInput.v1",
                response_schema="productUseEvidenceRecord.v1",
                description=(
                    "Map a typed SCCS cosmetics guidance record into the generic "
                    "product-use evidence contract."
                ),
            ),
            ContractToolEntry(
                name="exposure_build_product_use_evidence_from_sccs_opinion",
                request_schema="buildProductUseEvidenceFromSccsOpinionInput.v1",
                response_schema="productUseEvidenceRecord.v1",
                description=(
                    "Map a typed SCCS opinion record into the generic product-use "
                    "evidence contract."
                ),
            ),
            ContractToolEntry(
                name="exposure_build_product_use_evidence_from_cosing",
                request_schema="buildProductUseEvidenceFromCosIngInput.v1",
                response_schema="productUseEvidenceRecord.v1",
                description=(
                    "Map a typed CosIng ingredient record into the generic product-use "
                    "evidence contract."
                ),
            ),
            ContractToolEntry(
                name="exposure_build_product_use_evidence_from_nanomaterial",
                request_schema="buildProductUseEvidenceFromNanoMaterialInput.v1",
                response_schema="productUseEvidenceRecord.v1",
                description=(
                    "Map a typed nanomaterial guidance record into the generic product-use "
                    "evidence contract."
                ),
            ),
            ContractToolEntry(
                name="exposure_build_product_use_evidence_from_synthetic_polymer_microparticle",
                request_schema="buildProductUseEvidenceFromSyntheticPolymerMicroparticleInput.v1",
                response_schema="productUseEvidenceRecord.v1",
                description=(
                    "Map a typed synthetic polymer microparticle record into the generic "
                    "product-use evidence contract."
                ),
            ),
            ContractToolEntry(
                name="exposure_reconcile_product_use_evidence",
                request_schema="reconcileProductUseEvidenceInput.v1",
                response_schema="productUseEvidenceReconciliationReport.v1",
                description=(
                    "Compare multiple product-use evidence sources, rank their fit, and "
                    "build a merged request preview with explicit field provenance."
                ),
            ),
            ContractToolEntry(
                name="exposure_run_integrated_workflow",
                request_schema="runIntegratedExposureWorkflowInput.v1",
                response_schema="integratedExposureWorkflowResult.v1",
                description=(
                    "Run the local evidence-to-scenario-to-PBPK workflow in one audited response."
                ),
            ),
            ContractToolEntry(
                name="worker_route_task",
                request_schema="workerTaskRoutingInput.v1",
                response_schema="workerTaskRoutingDecision.v1",
                description=(
                    "Route a worker-tagged task to the strongest current MCP tool or a "
                    "future occupational adapter hook."
                ),
            ),
            ContractToolEntry(
                name="exposure_route_worker_task",
                request_schema="workerTaskRoutingInput.v1",
                response_schema="workerTaskRoutingDecision.v1",
                description=(
                    "Legacy compatibility alias for `worker_route_task`; prefer the "
                    "`worker_*` naming surface for worker-specific tools."
                ),
            ),
            ContractToolEntry(
                name="worker_export_inhalation_tier2_bridge",
                request_schema="exportWorkerInhalationTier2BridgeRequest.v1",
                response_schema="workerInhalationTier2BridgePackage.v1",
                description=(
                    "Export a normalized worker inhalation Tier 2 handoff package for a "
                    "future occupational adapter."
                ),
            ),
            ContractToolEntry(
                name="exposure_export_worker_inhalation_tier2_bridge",
                request_schema="exportWorkerInhalationTier2BridgeRequest.v1",
                response_schema="workerInhalationTier2BridgePackage.v1",
                description=(
                    "Legacy compatibility alias for `worker_export_inhalation_tier2_bridge`; "
                    "prefer the `worker_*` naming surface for worker-specific tools."
                ),
            ),
            ContractToolEntry(
                name="worker_ingest_inhalation_tier2_task",
                request_schema="workerInhalationTier2AdapterRequest.v1",
                response_schema="workerInhalationTier2AdapterIngestResult.v1",
                description=(
                    "Ingest a worker Tier 2 adapter request and normalize it into an "
                    "ART-aligned intake envelope."
                ),
            ),
            ContractToolEntry(
                name="worker_execute_inhalation_tier2_task",
                request_schema="executeWorkerInhalationTier2Request.v1",
                response_schema="workerInhalationTier2ExecutionResult.v1",
                description=(
                    "Execute a bounded ART-aligned worker inhalation screening estimate "
                    "from the normalized adapter request."
                ),
            ),
            ContractToolEntry(
                name="worker_export_inhalation_art_execution_package",
                request_schema="exportWorkerArtExecutionPackageRequest.v1",
                response_schema="workerArtExternalExecutionPackage.v1",
                description=(
                    "Export an ART-ready external execution payload plus a normalized "
                    "result-import template."
                ),
            ),
            ContractToolEntry(
                name="worker_import_inhalation_art_execution_result",
                request_schema="importWorkerArtExecutionResultRequest.v1",
                response_schema="workerInhalationTier2ExecutionResult.v1",
                description=(
                    "Import a normalized external ART result into the governed worker "
                    "inhalation execution schema."
                ),
            ),
            ContractToolEntry(
                name="worker_export_dermal_absorbed_dose_bridge",
                request_schema="exportWorkerDermalAbsorbedDoseBridgeRequest.v1",
                response_schema="workerDermalAbsorbedDoseBridgePackage.v1",
                description=(
                    "Export a normalized worker dermal absorbed-dose and PPE handoff package "
                    "for a future occupational dermal adapter."
                ),
            ),
            ContractToolEntry(
                name="exposure_export_worker_dermal_absorbed_dose_bridge",
                request_schema="exportWorkerDermalAbsorbedDoseBridgeRequest.v1",
                response_schema="workerDermalAbsorbedDoseBridgePackage.v1",
                description=(
                    "Legacy compatibility alias for `worker_export_dermal_absorbed_dose_bridge`; "
                    "prefer the `worker_*` naming surface for worker-specific tools."
                ),
            ),
            ContractToolEntry(
                name="worker_ingest_dermal_absorbed_dose_task",
                request_schema="workerDermalAbsorbedDoseAdapterRequest.v1",
                response_schema="workerDermalAbsorbedDoseAdapterIngestResult.v1",
                description=(
                    "Ingest a worker dermal absorbed-dose adapter request and normalize it "
                    "into a PPE-aware intake envelope."
                ),
            ),
            ContractToolEntry(
                name="worker_execute_dermal_absorbed_dose_task",
                request_schema="executeWorkerDermalAbsorbedDoseRequest.v1",
                response_schema="workerDermalAbsorbedDoseExecutionResult.v1",
                description=(
                    "Execute a bounded PPE-aware worker dermal absorbed-dose estimate from "
                    "the normalized adapter request."
                ),
            ),
            ContractToolEntry(
                name="exposure_build_inhalation_screening_scenario",
                request_schema="inhalationScenarioRequest.v1",
                response_schema="exposureScenario.v1",
                description=(
                    "Build a deterministic inhalation screening scenario using room semantics."
                ),
            ),
            ContractToolEntry(
                name="exposure_build_inhalation_residual_air_reentry_scenario",
                request_schema="inhalationResidualAirReentryScenarioRequest.v1",
                response_schema="exposureScenario.v1",
                description=(
                    "Build a deterministic post-application residual-air reentry inhalation "
                    "scenario from a reentry-start concentration anchor."
                ),
            ),
            ContractToolEntry(
                name="exposure_build_inhalation_tier1_screening_scenario",
                request_schema="inhalationTier1ScenarioRequest.v1",
                response_schema="exposureScenario.v1",
                description=(
                    "Build a deterministic Tier 1 near-field/far-field inhalation screening "
                    "scenario for spray events."
                ),
            ),
            ContractToolEntry(
                name="exposure_export_pbpk_scenario_input",
                request_schema="exportPbpkScenarioInputRequest.v1",
                response_schema="pbpkScenarioInput.v1",
                description=(
                    "Export a PBPK-ready handoff object from a source scenario, with an "
                    "optional transient inhalation concentration profile when supported."
                ),
            ),
            ContractToolEntry(
                name="exposure_export_pbpk_external_import_bundle",
                request_schema="exportPbpkExternalImportBundleRequest.v1",
                response_schema="pbpkExternalImportPackage.v1",
                description=(
                    "Export a PBPK MCP external-import payload template plus readiness report."
                ),
            ),
            ContractToolEntry(
                name="exposure_export_toxclaw_evidence_bundle",
                request_schema="exportToxClawEvidenceBundleRequest.v1",
                response_schema="toxclawEvidenceBundle.v1",
                description=(
                    "Export deterministic downstream evidence and report-section primitives."
                ),
            ),
            ContractToolEntry(
                name="exposure_export_toxclaw_refinement_bundle",
                request_schema="exportToxClawRefinementBundleRequest.v1",
                response_schema="toxclawExposureRefinementBundle.v1",
                description=(
                    "Export a downstream evidence-layer exposure refinement delta "
                    "with workflow hooks."
                ),
            ),
            ContractToolEntry(
                name="exposure_compare_exposure_scenarios",
                request_schema="compareExposureScenariosInput.v1",
                response_schema="scenarioComparisonRecord.v1",
                description="Compare two scenarios and surface dose and assumption deltas.",
            ),
            ContractToolEntry(
                name="exposure_compare_jurisdictional_scenarios",
                request_schema="compareJurisdictionalScenariosInput.v1",
                response_schema="jurisdictionalComparisonResult.v1",
                description=(
                    "Compare the same exposure scenario across multiple jurisdictions "
                    "and surface dose variance, key assumption drivers, and "
                    "harmonization opportunities."
                ),
            ),
            ContractToolEntry(
                name="exposure_run_verification_checks",
                request_schema=None,
                response_schema="verificationSummaryReport.v1",
                description=(
                    "Build a deterministic verification summary over the published "
                    "release, validation, benchmark, and trust resources."
                ),
            ),
        ],
        resources=[
            ContractResourceEntry(
                uri="contracts://manifest", description="Machine-readable contract manifest."
            ),
            ContractResourceEntry(
                uri="defaults://manifest", description="Versioned defaults manifest."
            ),
            ContractResourceEntry(
                uri="defaults://curation-report",
                description="Machine-readable parameter-branch curation report for defaults.",
            ),
            ContractResourceEntry(
                uri="tier1-inhalation://manifest",
                description=(
                    "Machine-readable packaged Tier 1 inhalation parameter and "
                    "product-profile manifest."
                ),
            ),
            ContractResourceEntry(
                uri="archetypes://manifest",
                description="Machine-readable packaged Tier B archetype-library manifest.",
            ),
            ContractResourceEntry(
                uri="probability-bounds://manifest",
                description="Machine-readable packaged Tier C single-driver profile manifest.",
            ),
            ContractResourceEntry(
                uri="scenario-probability://manifest",
                description=(
                    "Machine-readable packaged Tier C coupled-driver scenario package manifest."
                ),
            ),
            ContractResourceEntry(
                uri="docs://algorithm-notes",
                description="Algorithm notes for the deterministic engines.",
            ),
            ContractResourceEntry(
                uri="docs://archetype-library-guide",
                description="Guide to the packaged Tier B archetype library and its guardrails.",
            ),
            ContractResourceEntry(
                uri="docs://probability-bounds-guide",
                description="Guide to the packaged Tier C probability-bounds profiles.",
            ),
            ContractResourceEntry(
                uri="docs://tier1-inhalation-parameter-guide",
                description=(
                    "Guide to the packaged Tier 1 inhalation airflow, particle, and "
                    "product-family screening profiles."
                ),
            ),
            ContractResourceEntry(
                uri="docs://defaults-evidence-map",
                description="Source register and interpretation notes for defaults and heuristics.",
            ),
            ContractResourceEntry(
                uri="docs://defaults-curation-report",
                description="Human-readable summary of curated and heuristic defaults branches.",
            ),
            ContractResourceEntry(
                uri="docs://operator-guide",
                description=(
                    "Operator guide for validation, transports, and interpretation boundaries."
                ),
            ),
            ContractResourceEntry(
                uri="docs://deployment-hardening-guide",
                description=(
                    "Guide to hardening remote streamable-http deployments with external "
                    "auth, TLS, origin controls, and logging."
                ),
            ),
            ContractResourceEntry(
                uri="docs://provenance-policy",
                description="Provenance and assumption-emission policy for auditability.",
            ),
            ContractResourceEntry(
                uri="docs://result-status-semantics",
                description=(
                    "Non-breaking result-status conventions carried in "
                    "top-level tool-result metadata."
                ),
            ),
            ContractResourceEntry(
                uri="docs://uncertainty-framework",
                description="Tier A/B/C uncertainty guidance and interpretation boundaries.",
            ),
            ContractResourceEntry(
                uri="docs://inhalation-tier-upgrade-guide",
                description="Guide to Tier 1 inhalation upgrade hooks and current boundaries.",
            ),
            ContractResourceEntry(
                uri="docs://inhalation-residual-air-reentry-guide",
                description="Guide to the post-application residual-air reentry inhalation mode.",
            ),
            ContractResourceEntry(
                uri="docs://validation-framework",
                description="Validation and benchmark-domain posture for current route models.",
            ),
            ContractResourceEntry(
                uri="docs://validation-dossier",
                description="Validation dossier with cited external references and open gaps.",
            ),
            ContractResourceEntry(
                uri="docs://validation-coverage-report",
                description=(
                    "Human-readable validation coverage and trust report by route mechanism."
                ),
            ),
            ContractResourceEntry(
                uri="docs://validation-reference-bands",
                description=(
                    "Human-readable executable validation reference-band guide with "
                    "applicability selectors."
                ),
            ),
            ContractResourceEntry(
                uri="docs://validation-time-series-packs",
                description=(
                    "Human-readable guide to sparse executable validation time-series packs."
                ),
            ),
            ContractResourceEntry(
                uri="docs://verification-summary",
                description=(
                    "Human-readable guide to the consolidated verification summary surface."
                ),
            ),
            ContractResourceEntry(
                uri="docs://goldset-benchmark-guide",
                description="Human-readable guide to the externally anchored showcase goldset.",
            ),
            ContractResourceEntry(
                uri="docs://suite-integration-guide",
                description=(
                    "Boundary and integration guide for CompTox, PBPK, and planned "
                    "downstream orchestration seams."
                ),
            ),
            ContractResourceEntry(
                uri="docs://integrated-exposure-workflow-guide",
                description="Guide to the evidence-to-scenario-to-PBPK workflow tool.",
            ),
            ContractResourceEntry(
                uri="docs://exposure-platform-architecture",
                description=(
                    "Architecture guide for splitting exposure, fate, dietary, and worker "
                    "modeling concerns across cooperating MCPs."
                ),
            ),
            ContractResourceEntry(
                uri="docs://capability-maturity-matrix",
                description="One-page maturity framing for the released MCP surface.",
            ),
            ContractResourceEntry(
                uri="docs://repository-slug-decision",
                description="Decision note for keeping the current repository slug through v0.1.x.",
            ),
            ContractResourceEntry(
                uri="docs://red-team-review-memo",
                description=(
                    "Adversarial review memo describing the strongest credible attacks on "
                    "the MCP and the current mitigation posture."
                ),
            ),
            ContractResourceEntry(
                uri="docs://cross-mcp-contract-guide",
                description=(
                    "Guide to the shared suite-facing contracts published for sibling MCPs."
                ),
            ),
            ContractResourceEntry(
                uri="docs://service-selection-guide",
                description=(
                    "Guide to routing questions and handoffs across Exposure, Fate, Dietary, "
                    "PBPK, and the planned orchestration/reporting layer."
                ),
            ),
            ContractResourceEntry(
                uri="docs://herbal-medicinal-routing-guide",
                description=(
                    "Guide to routing TCM, herbal medicine, and supplement cases cleanly "
                    "across Direct-Use, Dietary, and Fate seams."
                ),
            ),
            ContractResourceEntry(
                uri="docs://toxmcp-suite-index",
                description=(
                    "One-page orientation guide to the current ToxMCP service family and "
                    "its shared boundaries."
                ),
            ),
            ContractResourceEntry(
                uri="docs://worker-routing-guide",
                description="Guide to the worker-task router and occupational escalation hooks.",
            ),
            ContractResourceEntry(
                uri="docs://worker-tier2-bridge-guide",
                description="Guide to the worker inhalation Tier 2 bridge export.",
            ),
            ContractResourceEntry(
                uri="docs://worker-art-adapter-guide",
                description="Guide to the ART-side worker inhalation adapter ingest boundary.",
            ),
            ContractResourceEntry(
                uri="docs://worker-art-execution-guide",
                description="Guide to the executable ART-aligned worker inhalation kernel.",
            ),
            ContractResourceEntry(
                uri="docs://worker-art-external-exchange-guide",
                description=(
                    "Guide to exporting ART-ready external execution packages and importing "
                    "external ART results."
                ),
            ),
            ContractResourceEntry(
                uri="docs://worker-dermal-bridge-guide",
                description="Guide to the worker dermal absorbed-dose bridge export.",
            ),
            ContractResourceEntry(
                uri="docs://worker-dermal-adapter-guide",
                description=("Guide to the dermal absorbed-dose and PPE adapter ingest boundary."),
            ),
            ContractResourceEntry(
                uri="docs://worker-dermal-execution-guide",
                description="Guide to the executable worker dermal absorbed-dose kernel.",
            ),
            ContractResourceEntry(
                uri="docs://troubleshooting",
                description=(
                    "Troubleshooting guide for common scenario, aggregation, and export failures."
                ),
            ),
            ContractResourceEntry(
                uri="docs://release-readiness",
                description="Release-readiness guidance derived from the current contract surface.",
            ),
            ContractResourceEntry(
                uri="docs://release-trust-checklist",
                description=(
                    "Human-readable checklist for public-release trust posture, sign-off, "
                    "and required trust artifacts."
                ),
            ),
            ContractResourceEntry(
                uri="docs://release-notes",
                description=(
                    "Release notes and migration notes for the current published candidate."
                ),
            ),
            ContractResourceEntry(
                uri="docs://conformance-report",
                description=(
                    "Human-readable conformance summary across validation, benchmarks, "
                    "and release checks."
                ),
            ),
            ContractResourceEntry(
                uri="docs://security-provenance-review",
                description=(
                    "Human-readable security and provenance review derived from the current "
                    "tool, resource, and defaults surface."
                ),
            ),
            ContractResourceEntry(
                uri="docs://test-evidence-summary",
                description=(
                    "Human-readable summary of test gates, wheel smoke checks, and release "
                    "artifact verification evidence."
                ),
            ),
            ContractResourceEntry(
                uri="benchmarks://manifest",
                description="Machine-readable benchmark and regression corpus manifest.",
            ),
            ContractResourceEntry(
                uri="benchmarks://goldset",
                description=(
                    "Machine-readable showcase goldset with external source anchors "
                    "and challenge tags."
                ),
            ),
            ContractResourceEntry(
                uri="validation://manifest",
                description="Machine-readable validation and external-reference manifest.",
            ),
            ContractResourceEntry(
                uri="validation://dossier-report",
                description=(
                    "Machine-readable validation dossier with external references and open gaps."
                ),
            ),
            ContractResourceEntry(
                uri="validation://coverage-report",
                description=(
                    "Machine-readable validation coverage report across benchmarks, "
                    "external datasets, reference bands, time-series packs, and goldset links."
                ),
            ),
            ContractResourceEntry(
                uri="validation://reference-bands",
                description=("Machine-readable executable validation reference-band manifest."),
            ),
            ContractResourceEntry(
                uri="validation://time-series-packs",
                description=(
                    "Machine-readable executable validation time-series reference-pack manifest."
                ),
            ),
            ContractResourceEntry(
                uri="verification://summary",
                description=(
                    "Machine-readable consolidated verification summary across release, "
                    "validation, benchmark, and trust resources."
                ),
            ),
            ContractResourceEntry(
                uri="release://readiness-report",
                description=(
                    "Machine-readable release-readiness report with validation and security checks."
                ),
            ),
            ContractResourceEntry(
                uri="release://metadata-report",
                description=(
                    "Machine-readable release metadata with package, benchmark, schema, "
                    "and limitation details."
                ),
            ),
            ContractResourceEntry(
                uri="release://security-provenance-review-report",
                description=(
                    "Machine-readable security and provenance review with pass, warning, "
                    "and blocked findings."
                ),
            ),
            ContractResourceEntry(
                uri="schemas://{schema_name}", description="JSON Schema by schema name."
            ),
            ContractResourceEntry(
                uri="examples://{example_name}", description="Generated example payload by name."
            ),
        ],
        prompts=[
            ContractPromptEntry(
                name="exposure_refinement_playbook",
                description=(
                    "Checklist for refining a screening scenario without collapsing auditability."
                ),
            ),
            ContractPromptEntry(
                name="exposure_pbpk_handoff_checklist",
                description=(
                    "Checklist for validating PBPK handoff readiness from a source scenario."
                ),
            ),
            ContractPromptEntry(
                name="exposure_evidence_reconciliation_brief",
                description=(
                    "Checklist for reconciling reviewed evidence packs into one auditable request."
                ),
            ),
            ContractPromptEntry(
                name="exposure_integrated_workflow_operator",
                description=(
                    "Checklist for running the evidence-to-scenario-to-PBPK workflow safely."
                ),
            ),
            ContractPromptEntry(
                name="exposure_inhalation_tier1_triage",
                description=("Checklist for deciding whether a spray scenario is Tier 1 ready."),
            ),
            ContractPromptEntry(
                name="exposure_worker_bridge_handoff",
                description=(
                    "Checklist for packaging worker bridge exports without losing review context."
                ),
            ),
            ContractPromptEntry(
                name="exposure_jurisdictional_review",
                description=(
                    "Checklist for preserving auditability during jurisdictional comparison."
                ),
            ),
        ],
        schemas={name: f"schemas/{name}.json" for name in SCHEMA_MODELS},
        examples={name: f"schemas/examples/{name}.json" for name in examples},
    )


def algorithm_notes() -> str:
    return """# Direct-Use Exposure MCP Algorithm Notes

## Screening Plugin

- Convert product amount per event into grams.
- Convert grams into chemical mass per event using `concentration_fraction`.
- Emit explicit assumption governance showing evidence grade, applicability status,
  and uncertainty families for every resolved parameter.
- Dermal:
  `external_mass_mg_day = chemical_mass_mg_event * use_events_per_day *
  retention_factor * transfer_efficiency`
- Oral:
  `external_mass_mg_day = chemical_mass_mg_event * use_events_per_day *
  ingestion_fraction`
- Normalize by body weight to emit `mg/kg-day`.
- Attach `tierSemantics` so the result stays bounded as Tier-0 deterministic screening.
- Attach Tier A diagnostics: `uncertaintyRegister`, `sensitivityRanking`,
  `dependencyMetadata`, and `validationSummary`.

## Inhalation Plugin

- Convert product amount per event into chemical mass.
- Apply `aerosolized_fraction` to obtain released mass.
- Compute initial well-mixed room concentration as `released_mass / room_volume`.
- Convert to time-averaged air concentration using a first-order air exchange removal term.
- Compute inhaled mass as
  `average_air_concentration * inhalation_rate * exposure_duration *
  events_per_day`.
- Normalize by body weight to emit `mg/kg-day`.
- Emit Tier-0 caveats that forbid interpreting room-average output as a breathing-zone peak.
- Preserve inhalation-specific uncertainty entries when spray assumptions
  exceed well-mixed validity.

## Tier 1 Inhalation Screening

- Tier 1 NF/FF screening resolves airflow-directionality and particle-regime heuristics from the
  packaged manifest at `tier1-inhalation://manifest`.
- Product-family screening profiles are published alongside those parameter packs so callers can
  anchor Tier 1 geometry and spray inputs to governed use-context templates.
- Tier 1 remains a deterministic screening model and must not be interpreted as CFD,
  deposition, or absorbed-dose simulation.

## Aggregate Summary

- Sum compatible normalized doses across components.
- Preserve route-wise subtotals.
- Emit an explicit limitation when multiple routes are rolled into a single screening summary.
- Attach Tier A aggregate uncertainty notes explaining that co-use dependence is not modeled.

## Deterministic Envelope

- Build named archetype scenarios with the same route, scenario class, chemical, and dose unit.
- Report minimum, median, and maximum deterministic dose across the archetypes.
- Attribute envelope span to explicit assumption differences between the low and high archetypes.
- Label the result as Tier B bounded uncertainty, not as a confidence interval.

## Packaged Archetype Library

- The packaged archetype library publishes governed Tier B screening templates by route and use
  context.
- `exposure_build_exposure_envelope_from_library` injects caller-supplied chemical identity into
  a packaged set and then resolves the same deterministic envelope algorithm.
- Library-backed envelopes keep `archetypeLibrarySetId`, `archetypeLibraryVersion`, template IDs,
  and library limitations visible in the result.

## Single-Driver Probability Bounds

- Packaged Tier C profiles publish cumulative probability bounds for one selected driver at a
  time, with all other scenario inputs fixed at the base request.
- `exposure_build_probability_bounds_from_profile` evaluates each support point deterministically
  and preserves the packaged probability bounds without Monte Carlo sampling.
- Probability-bounds outputs remain screening summaries and must not be interpreted as validated
  population exposure distributions.

## Scenario-Package Probability Bounds

- Packaged Tier C scenario-package profiles publish cumulative probability bounds over coupled
  driver states by referencing archetype-library templates.
- `exposure_build_probability_bounds_from_scenario_package` materializes deterministic scenarios
  for each packaged state and preserves dependence within those states.
- Scenario-package outputs remain screening summaries and must not be interpreted as full joint
  population exposure distributions.

## Comparison

- Compare primary dose values directly.
- Diff assumptions by stable parameter name.
- Report absolute and percent deltas without making risk claims.
"""


def benchmark_manifest() -> dict:
    return load_benchmark_manifest()


def archetype_library_manifest() -> dict:
    return ArchetypeLibraryRegistry.load().manifest().model_dump(mode="json", by_alias=True)


def tier1_inhalation_parameter_manifest() -> dict:
    return (
        Tier1InhalationProfileRegistry.load()
        .manifest()
        .model_dump(
            mode="json",
            by_alias=True,
        )
    )


def probability_bounds_profile_manifest() -> dict:
    return (
        ProbabilityBoundsProfileRegistry.load()
        .manifest()
        .model_dump(
            mode="json",
            by_alias=True,
        )
    )


def scenario_probability_package_manifest() -> dict:
    return (
        ScenarioProbabilityPackageRegistry.load()
        .manifest()
        .model_dump(
            mode="json",
            by_alias=True,
        )
    )


def _project_metadata() -> tuple[str, str]:
    pyproject_path = repo_path("pyproject.toml")
    if pyproject_path is not None and pyproject_path.exists():
        payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        project = payload["project"]
        return str(project["name"]), str(project["version"])
    return PACKAGE_NAME, CURRENT_VERSION


def _distribution_artifacts(package_name: str, version: str) -> list[ReleaseDistributionArtifact]:
    return distribution_artifacts_for_release(package_name, version, repo_path("dist"))


def _review_status(findings: list[SecurityProvenanceReviewFinding]) -> ReviewStatus:
    if any(finding.status == "blocked" for finding in findings):
        return "blocked"
    if any(finding.status == "warning" for finding in findings):
        return "acceptable_with_warnings"
    return "acceptable"


def build_security_provenance_review_report(
    defaults_registry: DefaultsRegistry,
) -> SecurityProvenanceReviewReport:
    manifest = build_contract_manifest(defaults_registry)
    defaults_manifest = defaults_registry.manifest()
    defaults_curation = build_defaults_curation_report(defaults_registry)
    examples = build_examples()
    reviewed_surface = ReviewedSurfaceIndex(
        toolNames=[tool.name for tool in manifest.tools],
        resourceUris=[resource.uri for resource in manifest.resources],
        promptNames=[prompt.name for prompt in manifest.prompts],
    )
    heuristic_entries = [
        entry
        for entry in defaults_curation.entries
        if entry.curation_status == DefaultsCurationStatus.HEURISTIC
    ]
    heuristic_sources = sorted({entry.source_id for entry in heuristic_entries})
    heuristic_visibility_published = {
        "defaults://curation-report",
        "docs://defaults-curation-report",
        "docs://defaults-evidence-map",
        "docs://provenance-policy",
        "docs://validation-dossier",
    } <= set(reviewed_surface.resource_uris)
    provenance_example_names = [
        "screening_dermal_scenario",
        "inhalation_scenario",
        "aggregate_summary",
        "comparison_record",
        "jurisdictional_comparison_result",
        "pbpk_input",
    ]
    provenance_examples_ok = all(
        "provenance" in examples[example_name] for example_name in provenance_example_names
    )
    pbpk_external_import_ok = bool(
        examples["pbpk_external_import_package"]["bundle"].get("supportingHandoffs")
    )
    toxclaw_hashing_ok = all(
        {"evidenceId", "contentHash"} <= set(examples[example_name]["evidenceRecord"])
        for example_name in ["toxclaw_evidence_bundle", "toxclaw_refinement_bundle"]
    )
    http_boundary_controls = streamable_http_boundary_controls_available()
    provenance_status: CheckStatus = (
        "pass"
        if provenance_examples_ok and pbpk_external_import_ok and toxclaw_hashing_ok
        else "blocked"
    )
    findings = [
        SecurityProvenanceReviewFinding(
            findingId="public-surface-indexed",
            category="contract_integrity",
            title="Public tool and resource surface is machine-readable",
            status="pass",
            appliesTo=[*reviewed_surface.tool_names, *reviewed_surface.resource_uris],
            evidence=(
                f"The manifest declares {len(manifest.tools)} tools, "
                f"{len(manifest.resources)} resources, and {len(manifest.prompts)} prompts, "
                "with JSON Schemas published for every declared public schema."
            ),
            references=[
                "contracts://manifest",
                "schemas://{schema_name}",
                "examples://{example_name}",
            ],
        ),
        SecurityProvenanceReviewFinding(
            findingId="defaults-pack-integrity",
            category="defaults_integrity",
            title="Defaults pack integrity is explicit and reviewable",
            status="pass",
            appliesTo=["defaults://manifest", "docs://defaults-evidence-map"],
            evidence=(
                f"Defaults pack `{defaults_manifest['defaults_version']}` carries SHA256 "
                f"`{defaults_manifest['defaults_hash_sha256'][:16]}` with "
                f"{defaults_manifest['source_count']} declared source entries across "
                f"{len(defaults_manifest['supported_regions'])} supported regions."
            ),
            references=["defaults://manifest", "docs://defaults-evidence-map"],
        ),
        SecurityProvenanceReviewFinding(
            findingId="output-auditability",
            category="provenance_auditability",
            title="Public outputs preserve provenance or auditable handoff context",
            status=provenance_status,
            appliesTo=reviewed_surface.tool_names,
            evidence=(
                "Generated scenario, aggregate, both comparison outputs, and PBPK input "
                "examples all carry explicit `provenance`; PBPK external-import output "
                "preserves auditable handoff context through supporting handoffs and "
                "compatibility reporting; downstream evidence/refinement exports carry "
                "deterministic "
                "evidence records."
            ),
            recommendation=(
                None
                if provenance_status == "pass"
                else "Do not release the surface until every public output restores explicit "
                "auditability through provenance or deterministic evidence traces."
            ),
            references=[
                "docs://provenance-policy",
                "docs://suite-integration-guide",
            ],
        ),
        SecurityProvenanceReviewFinding(
            findingId="deterministic-toxclaw-evidence",
            category="deterministic_evidence_hashing",
            title="Downstream evidence exports use deterministic IDs and content hashes",
            status="pass" if toxclaw_hashing_ok else "blocked",
            appliesTo=[
                "exposure_export_toxclaw_evidence_bundle",
                "exposure_export_toxclaw_refinement_bundle",
            ],
            evidence=(
                "Both downstream export example families emit `evidenceId` and `contentHash`, "
                "keeping downstream citation and report linkage stable across reruns."
            ),
            recommendation=(
                None
                if toxclaw_hashing_ok
                else "Restore deterministic hashing before release so evidence and claim "
                "linkage stay stable across repeated scenario exports."
            ),
            references=[
                "docs://provenance-policy",
                "docs://suite-integration-guide",
            ],
        ),
        SecurityProvenanceReviewFinding(
            findingId="heuristic-defaults-visible",
            category="defaults_integrity",
            title="Heuristic screening branches stay explicit and reviewable",
            status="pass" if heuristic_visibility_published else "blocked",
            appliesTo=[
                "exposure_build_screening_exposure_scenario",
                "exposure_build_inhalation_screening_scenario",
                "defaults://manifest",
                "defaults://curation-report",
                "docs://defaults-curation-report",
                "docs://defaults-evidence-map",
            ],
            evidence=(
                "The published defaults curation report currently marks "
                f"{len(heuristic_entries)} parameter branches across "
                f"{len(heuristic_sources)} source families as heuristic: "
                f"{', '.join(f'`{item}`' for item in heuristic_sources)}. "
                "Those branches remain explicit through the defaults curation report, "
                "`heuristic_default_source` runtime quality flags, and the "
                "`heuristic_defaults_active` validation gap."
                if heuristic_sources
                else "No heuristic branches remain in the published defaults curation report."
            ),
            recommendation=(
                None
                if heuristic_visibility_published
                else "Restore the published defaults curation and provenance resources before "
                "treating heuristic branches as reviewable."
            ),
            references=[
                "defaults://curation-report",
                "docs://defaults-curation-report",
                "docs://defaults-evidence-map",
                "docs://provenance-policy",
                "docs://validation-dossier",
            ],
        ),
        SecurityProvenanceReviewFinding(
            findingId="remote-transport-controls-published",
            category="transport_security",
            title="Remote HTTP deployment publishes first-party boundary controls",
            status="pass",
            appliesTo=[
                "docs://operator-guide",
                "docs://deployment-hardening-guide",
                "docs://troubleshooting",
                "streamable-http",
            ],
            evidence=(
                "The published streamable-http surface includes first-party support for "
                f"{', '.join(f'`{item}`' for item in http_boundary_controls)}. Operators can "
                "enable shared bearer-token auth, explicit origin allow-lists, and request-size "
                "limits without relying solely on an external gateway."
            ),
            recommendation=None,
            references=[
                "docs://operator-guide",
                "docs://deployment-hardening-guide",
                "docs://troubleshooting",
            ],
        ),
        SecurityProvenanceReviewFinding(
            findingId="scientific-boundary-explicit",
            category="scientific_boundary",
            title="Scientific ownership boundary remains explicit",
            status="pass",
            appliesTo=reviewed_surface.tool_names,
            evidence=(
                "The published surface keeps ownership at external-dose construction and "
                "explicitly excludes PBPK execution, internal dose estimation, BER, PoD "
                "derivation, and final risk conclusions."
            ),
            references=[
                "docs://operator-guide",
                "docs://suite-integration-guide",
                "docs://release-readiness",
            ],
        ),
    ]
    status: ReviewStatus = _review_status(findings)
    reviewed_at = datetime.now(UTC).isoformat()
    warning_titles = [finding.title.lower() for finding in findings if finding.status == "warning"]
    if status == "blocked":
        summary = (
            "The security and provenance review is blocked because at least one public-surface "
            "auditability check failed."
        )
    elif warning_titles:
        summary = (
            "The security and provenance review is acceptable with warnings. The remaining "
            "cautions are confined to still-heuristic screening factor families."
        )
    else:
        summary = (
            "The security and provenance review found no blocking or warning-level issues "
            "across the current public surface."
        )
    return SecurityProvenanceReviewReport(
        reviewId=f"security-provenance-review-{reviewed_at[:10]}",
        serverName=manifest.server_name,
        serverVersion=manifest.server_version,
        defaultsVersion=manifest.defaults_version,
        reviewedAt=reviewed_at,
        status=status,
        summary=summary,
        reviewedSurface=reviewed_surface,
        findings=findings,
        externalRequirements=[
            (
                "If you expose `streamable-http`, configure the built-in bearer token, origin "
                "allow-list, and request-size limit, and keep TLS or rate limiting at the "
                "gateway layer."
            ),
            (
                "Keep heuristic-default quality flags and validation gaps visible to downstream "
                "users when screening bridge defaults are active."
            ),
        ],
    )


def build_release_metadata_report(defaults_registry: DefaultsRegistry) -> ReleaseMetadataReport:
    manifest = build_contract_manifest(defaults_registry)
    examples = build_examples()
    benchmarks = benchmark_manifest()
    readiness = build_release_readiness_report(defaults_registry)
    security_review = build_security_provenance_review_report(defaults_registry)
    package_name, package_version = _project_metadata()
    benchmark_cases = benchmarks.get("cases", [])
    artifacts = _distribution_artifacts(package_name, package_version)
    return ReleaseMetadataReport(
        releaseVersion=package_version,
        packageName=package_name,
        packageVersion=package_version,
        serverName=manifest.server_name,
        serverVersion=manifest.server_version,
        defaultsVersion=manifest.defaults_version,
        readinessStatus=readiness.status,
        securityReviewStatus=security_review.status,
        benchmarkCaseCount=len(benchmark_cases),
        benchmarkCaseIds=[str(case["id"]) for case in benchmark_cases],
        contractSchemaCount=len(manifest.schemas),
        contractExampleCount=len(examples),
        distributionArtifacts=artifacts,
        publishedDocs=[
            "docs://release-notes",
            "docs://conformance-report",
            "docs://release-readiness",
            "docs://release-trust-checklist",
            "docs://deployment-hardening-guide",
            "docs://security-provenance-review",
            "docs://test-evidence-summary",
            "docs://verification-summary",
            "docs://goldset-benchmark-guide",
            "docs://capability-maturity-matrix",
            "docs://red-team-review-memo",
            "docs://herbal-medicinal-routing-guide",
            "docs://toxmcp-suite-index",
            CURRENT_RELEASE_NOTES_RELATIVE_PATH,
        ],
        validationCommands=readiness.validation_commands,
        migrationNotes=[
            (
                f"{CURRENT_RELEASE_TAG} supersedes the prior public `v0.1.0` baseline; "
                "update any pinned release-note or release-metadata references to the new "
                "versioned docs path."
            ),
            (
                "Jurisdictional comparison clients should preserve the new audit fields "
                "(`provenance`, `limitations`, `qualityFlags`, `fitForPurpose`) and treat "
                "unsupported or duplicate jurisdictions as request-validation errors."
            ),
        ],
        knownLimitations=readiness.known_limitations,
    )


def build_verification_summary_report(
    defaults_registry: DefaultsRegistry,
) -> VerificationSummaryReport:
    manifest = build_contract_manifest(defaults_registry)
    metadata = build_release_metadata_report(defaults_registry)
    readiness = build_release_readiness_report(defaults_registry)
    security_review = build_security_provenance_review_report(defaults_registry)
    coverage = build_validation_coverage_report()
    benchmark_fixture = load_benchmark_manifest()
    goldset_manifest = load_goldset_manifest()
    reference_manifest = ValidationReferenceBandRegistry.load().manifest()
    time_series_manifest = ValidationTimeSeriesReferenceRegistry.load().manifest()
    published_resource_uris = {entry.uri for entry in manifest.resources}
    example_payloads = build_examples()

    benchmark_case_ids = [str(case["id"]) for case in benchmark_fixture.get("cases", [])]
    benchmark_case_count = len(benchmark_case_ids)
    goldset_case_count = len(goldset_manifest.get("cases", []))

    checks: list[VerificationCheck] = []

    contract_surface_aligned = metadata.contract_schema_count == len(
        manifest.schemas
    ) and metadata.contract_example_count == len(example_payloads)
    checks.append(
        VerificationCheck(
            checkId="contract-surface-alignment",
            title="Contract manifest counts match generated schemas and examples",
            status="pass" if contract_surface_aligned else "blocked",
            blocking=not contract_surface_aligned,
            evidence=(
                f"Manifest publishes {len(manifest.tools)} tools, {len(manifest.resources)} "
                f"resources, {len(manifest.prompts)} prompts, {len(manifest.schemas)} schemas, "
                f"and {len(example_payloads)} examples."
            ),
            relatedResources=["contracts://manifest", "release://metadata-report"],
        )
    )

    defaults_aligned = (
        metadata.defaults_version == defaults_registry.version
        and manifest.defaults_version == defaults_registry.version
        and coverage.benchmark_defaults_version == defaults_registry.version
    )
    checks.append(
        VerificationCheck(
            checkId="defaults-version-alignment",
            title="Defaults version stays aligned across manifest, release, and validation",
            status="pass" if defaults_aligned else "blocked",
            blocking=not defaults_aligned,
            evidence=(
                f"Defaults version is `{defaults_registry.version}` across release metadata, "
                "contract manifest, and benchmark coverage."
            ),
            relatedResources=[
                "defaults://manifest",
                "release://metadata-report",
                "validation://coverage-report",
            ],
        )
    )

    benchmark_aligned = (
        metadata.benchmark_case_count == benchmark_case_count
        and coverage.benchmark_case_count == benchmark_case_count
        and metadata.benchmark_case_ids == benchmark_case_ids
    )
    checks.append(
        VerificationCheck(
            checkId="benchmark-corpus-alignment",
            title="Benchmark corpus counts align across release and validation surfaces",
            status="pass" if benchmark_aligned else "blocked",
            blocking=not benchmark_aligned,
            evidence=(
                f"Benchmark corpus contains {benchmark_case_count} deterministic cases, "
                f"{coverage.external_dataset_count} external datasets, "
                f"{coverage.reference_band_count} executable reference bands, and "
                f"{coverage.time_series_pack_count} time-series packs."
            ),
            relatedResources=[
                "benchmarks://manifest",
                "validation://coverage-report",
                "release://metadata-report",
            ],
        )
    )

    expected_verification_resources = {
        "validation://manifest",
        "validation://dossier-report",
        "validation://coverage-report",
        "validation://reference-bands",
        "validation://time-series-packs",
        "verification://summary",
        "docs://validation-framework",
        "docs://validation-dossier",
        "docs://validation-coverage-report",
        "docs://validation-reference-bands",
        "docs://validation-time-series-packs",
        "docs://verification-summary",
    }
    validation_surface_published = (
        expected_verification_resources <= published_resource_uris
        and coverage.reference_band_count == reference_manifest.band_count
        and coverage.time_series_pack_count == time_series_manifest.pack_count
    )
    checks.append(
        VerificationCheck(
            checkId="validation-resource-publication",
            title="Validation and verification resources are published on the MCP surface",
            status="pass" if validation_surface_published else "blocked",
            blocking=not validation_surface_published,
            evidence=(
                f"Published validation resources cover {coverage.domain_count} domains, "
                f"{reference_manifest.band_count} reference bands, and "
                f"{time_series_manifest.pack_count} time-series packs."
            ),
            relatedResources=[
                "validation://coverage-report",
                "validation://reference-bands",
                "validation://time-series-packs",
                "verification://summary",
            ],
        )
    )

    release_status: CheckStatus = (
        "blocked"
        if readiness.status == "blocked"
        else "warning"
        if readiness.status == "ready_with_known_limitations"
        else "pass"
    )
    checks.append(
        VerificationCheck(
            checkId="release-readiness-status",
            title="Release readiness remains within the published acceptable posture",
            status=release_status,
            blocking=release_status == "blocked",
            evidence=(
                f"Release readiness is `{readiness.status}` with "
                f"{len(readiness.checks)} governed checks."
            ),
            recommendation=(
                None
                if release_status == "pass"
                else "Review `release://readiness-report` before broadening claims."
            ),
            relatedResources=["release://readiness-report", "docs://release-readiness"],
        )
    )

    security_status: CheckStatus = (
        "blocked"
        if security_review.status == "blocked"
        else "warning"
        if security_review.status == "acceptable_with_warnings"
        else "pass"
    )
    checks.append(
        VerificationCheck(
            checkId="security-provenance-status",
            title="Security and provenance review remains within the published posture",
            status=security_status,
            blocking=security_status == "blocked",
            evidence=(
                f"Security/provenance review is `{security_review.status}` with "
                f"{len(security_review.findings)} findings across "
                f"{len(security_review.reviewed_surface.tool_names)} tools."
            ),
            recommendation=(
                None
                if security_status == "pass"
                else (
                    "Review `release://security-provenance-review-report` before remote deployment."
                )
            ),
            relatedResources=[
                "release://security-provenance-review-report",
                "docs://security-provenance-review",
            ],
        )
    )

    boundary_guides_published = {
        "docs://cross-mcp-contract-guide",
        "docs://service-selection-guide",
        "docs://herbal-medicinal-routing-guide",
        "docs://suite-integration-guide",
        "docs://toxmcp-suite-index",
    } <= published_resource_uris
    checks.append(
        VerificationCheck(
            checkId="suite-boundary-guides-published",
            title="Cross-MCP boundary and routing guides are published",
            status="pass" if boundary_guides_published else "blocked",
            blocking=not boundary_guides_published,
            evidence=(
                "The published resource surface includes explicit service-selection, "
                "herbal/medicinal routing, cross-contract, suite-integration, and "
                "suite-index guides."
            ),
            relatedResources=[
                "docs://cross-mcp-contract-guide",
                "docs://service-selection-guide",
                "docs://herbal-medicinal-routing-guide",
                "docs://suite-integration-guide",
                "docs://toxmcp-suite-index",
            ],
        )
    )

    checks.append(
        VerificationCheck(
            checkId="goldset-mapping-posture",
            title="Goldset mapping posture is explicit",
            status="warning" if coverage.unmapped_goldset_case_ids else "pass",
            blocking=False,
            evidence=(
                f"Goldset publishes {goldset_case_count} showcase cases; "
                f"{len(coverage.unmapped_goldset_case_ids)} remain challenge or "
                "integration-only and are intentionally unmapped to benchmark domains."
            ),
            recommendation=(
                None
                if not coverage.unmapped_goldset_case_ids
                else (
                    "Promote high-value unmapped goldset cases into executable "
                    "benchmark domains when evidence supports it."
                )
            ),
            relatedResources=["benchmarks://goldset", "validation://coverage-report"],
        )
    )

    status: CheckStatus = (
        "blocked"
        if any(item.status == "blocked" for item in checks)
        else "warning"
        if any(item.status == "warning" for item in checks)
        else "pass"
    )
    summary = (
        f"Verification summary `{status}` for {len(manifest.tools)} tools, "
        f"{len(manifest.resources)} resources, {benchmark_case_count} benchmark cases, "
        f"{coverage.external_dataset_count} external datasets, "
        f"{coverage.reference_band_count} reference bands, and "
        f"{coverage.time_series_pack_count} time-series packs."
    )

    notes = [
        (
            "This report is a deterministic consistency and trust-surface summary over the "
            "published contract, release, benchmark, and validation artifacts."
        ),
        (
            "It does not replace local command execution such as `uv run ruff check .`, "
            "`uv run pytest`, or release artifact verification."
        ),
    ]
    if coverage.unmapped_goldset_case_ids:
        notes.append(
            "Unmapped goldset cases are expected where challenge or integration showcase items "
            "do not yet have executable benchmark-domain coverage."
        )

    return VerificationSummaryReport(
        serverName=manifest.server_name,
        serverVersion=manifest.server_version,
        releaseVersion=metadata.release_version,
        defaultsVersion=defaults_registry.version,
        status=status,
        summary=summary,
        publicSurface=PublicSurfaceSummary(
            toolCount=len(manifest.tools),
            resourceCount=len(manifest.resources),
            promptCount=len(manifest.prompts),
            transports=["stdio", "streamable-http"],
        ),
        releaseReadinessStatus=readiness.status,
        securityReviewStatus=security_review.status,
        validationDomainCount=coverage.domain_count,
        benchmarkCaseCount=benchmark_case_count,
        externalDatasetCount=coverage.external_dataset_count,
        referenceBandCount=coverage.reference_band_count,
        timeSeriesPackCount=coverage.time_series_pack_count,
        goldsetCaseCount=goldset_case_count,
        unmappedGoldsetCaseIds=coverage.unmapped_goldset_case_ids,
        publishedResources=sorted(
            [
                "contracts://manifest",
                "validation://coverage-report",
                "validation://reference-bands",
                "validation://time-series-packs",
                "release://metadata-report",
                "release://readiness-report",
                "release://security-provenance-review-report",
                "verification://summary",
                "docs://verification-summary",
                "docs://release-trust-checklist",
                "docs://deployment-hardening-guide",
                "docs://test-evidence-summary",
            ]
        ),
        validationCommands=metadata.validation_commands,
        checks=checks,
        notes=notes,
    )


def build_release_readiness_report(defaults_registry: DefaultsRegistry) -> ReleaseReadinessReport:
    manifest = build_contract_manifest(defaults_registry)
    defaults_manifest = defaults_registry.manifest()
    security_review = build_security_provenance_review_report(defaults_registry)
    checks = [
        ReleaseReadinessCheck(
            checkId="contract-surface",
            title="Contract surface is published",
            status="pass",
            blocking=False,
            evidence=(
                f"{len(manifest.tools)} tools, {len(manifest.resources)} resources, and "
                f"{len(manifest.prompts)} prompts are declared in the manifest."
            ),
        ),
        ReleaseReadinessCheck(
            checkId="defaults-integrity",
            title="Defaults pack is versioned and hashed",
            status="pass",
            blocking=False,
            evidence=(
                f"Defaults pack `{defaults_manifest['defaults_version']}` is tracked with "
                f"SHA256 `{defaults_manifest['defaults_hash_sha256'][:16]}` and "
                f"{defaults_manifest['source_count']} declared source entries."
            ),
        ),
        ReleaseReadinessCheck(
            checkId="provenance-coverage",
            title="Public outputs preserve provenance or deterministic hashes",
            status="pass",
            blocking=False,
            evidence=(
                "The published security/provenance review confirms that scenario, aggregate, "
                "comparison, and PBPK outputs preserve auditability, and that downstream "
                "evidence exports "
                "retain deterministic evidence IDs and content hashes."
            ),
        ),
        ReleaseReadinessCheck(
            checkId="pbpk-upstream-request-alignment",
            title="PBPK handoff emits the upstream ingest request shape",
            status="pass",
            blocking=False,
            evidence=(
                "PBPK export wrappers now emit top-level `ingest_external_pbpk_bundle` request "
                "arguments directly, and integration coverage validates the generated payload "
                "against the sibling PBPK MCP request model when that repo is present."
            ),
        ),
        ReleaseReadinessCheck(
            checkId="security-provenance-review",
            title="Security and provenance review artifact is published",
            status=(
                "blocked"
                if security_review.status == "blocked"
                else "warning"
                if security_review.status == "acceptable_with_warnings"
                else "pass"
            ),
            blocking=security_review.status == "blocked",
            evidence=(
                f"`{security_review.schema_version}` covers "
                f"{len(security_review.reviewed_surface.tool_names)} tools and "
                f"{len(security_review.reviewed_surface.resource_uris)} resources with "
                f"{len(security_review.findings)} explicit findings."
            ),
            recommendation=(
                None
                if security_review.status == "acceptable"
                else "Review `release://security-provenance-review-report` before publishing a "
                "remote deployment or tightening defaults claims."
            ),
        ),
        ReleaseReadinessCheck(
            checkId="validation-suite",
            title="Local validation gates are defined",
            status="pass",
            blocking=False,
            evidence=(
                "The standard validation path is `uv run ruff check .`, `uv run pytest`, "
                "`uv build`, `uv run generate-exposure-contracts`, and "
                "`uv run check-exposure-release-artifacts`. Clean test runs do not require "
                "prebuilt `dist/` artifacts, while release validation still verifies the "
                "published wheel and sdist after `uv build`."
            ),
        ),
        ReleaseReadinessCheck(
            checkId="result-status-semantics",
            title="Future-safe result metadata is published",
            status="pass",
            blocking=False,
            evidence=(
                "Tool responses retain their existing payload schemas while top-level `_meta` "
                "publishes `toolResultMeta.v1` with sync terminal states reserved for future "
                "async reuse."
            ),
        ),
        ReleaseReadinessCheck(
            checkId="scientific-boundary",
            title="Scope boundary remains explicit",
            status="pass",
            blocking=False,
            evidence=(
                "The public surface states that this MCP owns external-dose construction only "
                "and does not claim PBPK execution, internal exposure, BER, PoD derivation, "
                "or final risk conclusions."
            ),
        ),
    ]
    status: ReadinessStatus = (
        "blocked"
        if any(check.status == "blocked" for check in checks)
        else "ready_with_known_limitations"
        if any(check.status == "warning" for check in checks)
        else "ready"
    )
    return ReleaseReadinessReport(
        releaseCandidate=CURRENT_VERSION,
        serverName=manifest.server_name,
        serverVersion=manifest.server_version,
        defaultsVersion=manifest.defaults_version,
        status=status,
        summary=(
            "The current Direct-Use Exposure MCP build satisfies its contract, regression, and "
            "provenance gates for a deterministic external-dose release candidate while keeping "
            "scientific limitations and deployment boundaries explicit."
        ),
        publicSurface=PublicSurfaceSummary(
            toolCount=len(manifest.tools),
            resourceCount=len(manifest.resources),
            promptCount=len(manifest.prompts),
            transports=["stdio", "streamable-http"],
        ),
        validationCommands=[
            "uv run ruff check .",
            "uv run pytest",
            "uv build",
            "uv run generate-exposure-contracts",
            "uv run validate-evals",
            "uv run check-exposure-release-artifacts",
        ],
        checks=checks,
        knownLimitations=[
            (
                "This is a deterministic-first public server; "
                "no probabilistic population engine is shipped."
            ),
            (
                "The module does not execute PBPK, estimate internal dose, "
                "derive BER or PoD values, or make final risk decisions."
            ),
            (
                "Remote `streamable-http` deployment now supports built-in bearer-token auth, "
                "origin allow-lists, and request-size limits, but still relies on gateway- or "
                "host-layer TLS, rate limiting, and network scoping."
            ),
            (
                "Some screening factors still resolve from heuristic defaults packs and should "
                "be treated as flagged screening-level assumptions until curated replacements "
                "are added."
            ),
            (
                "PBPK request alignment should be re-validated whenever PBPK MCP "
                "changes its published contract version or request model."
            ),
        ],
    )
