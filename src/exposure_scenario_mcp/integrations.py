"""Suite integration helpers for CompTox, ToxClaw, and PBPK-facing flows."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal

from pydantic import Field

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.errors import ensure
from exposure_scenario_mcp.models import (
    AggregateExposureSummary,
    CompareExposureScenariosInput,
    ExportPbpkExternalImportBundleRequest,
    ExportPbpkScenarioInputRequest,
    ExportToxClawEvidenceBundleRequest,
    ExportToxClawRefinementBundleRequest,
    ExposureScenario,
    ExposureScenarioRequest,
    FitForPurpose,
    InhalationScenarioRequest,
    InhalationTier1ScenarioRequest,
    LimitationNote,
    ParticleMaterialContext,
    PbpkScenarioInput,
    PopulationProfile,
    ProductUseProfile,
    ProvenanceBundle,
    QualityFlag,
    Route,
    ScalarValue,
    ScenarioClass,
    ScenarioComparisonRecord,
    Severity,
    StrictModel,
)
from exposure_scenario_mcp.package_metadata import CURRENT_VERSION
from exposure_scenario_mcp.plugins import InhalationScreeningPlugin, ScreeningScenarioPlugin
from exposure_scenario_mcp.plugins.inhalation import build_inhalation_tier_1_screening_scenario
from exposure_scenario_mcp.runtime import (
    PluginRegistry,
    ScenarioEngine,
    compare_scenarios,
    export_pbpk_input,
)
from exposure_scenario_mcp.tier1_inhalation_profiles import Tier1InhalationProfileRegistry
from exposure_scenario_mcp.uncertainty import enrich_scenario_uncertainty


def _sorted_json(value):
    if isinstance(value, list):
        return [_sorted_json(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _sorted_json(item)
            for key, item in sorted(value.items(), key=lambda entry: entry[0])
        }
    return value


def _stable_json_dumps(value: dict) -> str:
    return json.dumps(_sorted_json(value), indent=2)


def _hash_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _hash_value(value: dict) -> str:
    return _hash_text(_stable_json_dumps(value))


def _deterministic_id(prefix: str, parts: list[str]) -> str:
    digest = sha256()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\0")
    return f"{prefix}-{digest.hexdigest()[:16]}"


def _normalize_section_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return normalized or "section"


def _resolved_body_weight_kg(scenario: ExposureScenario) -> float | None:
    if scenario.population_profile.body_weight_kg is not None:
        return scenario.population_profile.body_weight_kg
    for assumption in scenario.assumptions:
        if assumption.name == "body_weight_kg" and assumption.value is not None:
            return float(assumption.value)
    return None


def _scenario_summary(scenario: ExposureScenario) -> str:
    return (
        f"{scenario.route.value} {scenario.scenario_class.value} scenario with "
        f"external dose {scenario.external_dose.value} {scenario.external_dose.unit.value}"
    )


def _scenario_timing_pattern(scenario: ExposureScenario) -> str:
    duration = scenario.product_use_profile.exposure_duration_hours
    if duration is not None:
        return (
            f"{scenario.product_use_profile.use_events_per_day:g} events/day "
            f"for {duration:g} hour(s) per event"
        )
    return f"{scenario.product_use_profile.use_events_per_day:g} events/day"


def _life_stage(population_group: str) -> str:
    normalized = population_group.strip().lower()
    if "infant" in normalized:
        return "infant"
    if "child" in normalized:
        return "child"
    if "adolescent" in normalized or "teen" in normalized:
        return "adolescent"
    if "preg" in normalized:
        return "adult"
    return "adult"


def _chemical_identity_context(scenario: ExposureScenario) -> dict[str, ScalarValue]:
    preferred_name = scenario.chemical_name or scenario.chemical_id
    return {
        "available": scenario.chemical_name is not None,
        "chemicalId": scenario.chemical_id,
        "preferredName": preferred_name,
        "label": preferred_name,
        "sourceModule": "exposure-scenario-mcp",
        "summary": f"Identity context derived from exposure scenario {scenario.scenario_id}.",
    }


def _upstream_uncertainty_summary(scenario: ExposureScenario) -> dict[str, ScalarValue]:
    issue_count = len(scenario.limitations) + len(scenario.quality_flags)
    return {
        "source": "exposure-scenario-mcp",
        "issueCount": issue_count,
        "hasResidualUncertainty": bool(issue_count),
        "summary": (
            "Exposure-scenario assumptions, limitations, and quality flags remain upstream "
            "and must be preserved during PBPK interpretation."
        ),
    }


def _workflow_provenance(
    registry: DefaultsRegistry,
    *,
    generated_at: str | None = None,
) -> ProvenanceBundle:
    return ProvenanceBundle(
        algorithm_id="workflow.integrated_exposure_pbpk.v1",
        plugin_id="integrated_exposure_workflow_service",
        plugin_version=CURRENT_VERSION,
        defaults_version=registry.version,
        defaults_hash_sha256=registry.sha256,
        generated_at=generated_at or datetime.now(UTC).isoformat(),
        notes=[
            "Workflow result preserves evidence reconciliation, scenario construction, and "
            "optional PBPK handoff generation as one auditable response.",
            "CompTox, SCCS, and ConsExpo records are normalized locally into the generic "
            "evidence contract; no external MCP call is executed inside this workflow helper.",
        ],
    )


def _restore_request_contract(
    source_request: ExposureScenarioRequest
    | InhalationScenarioRequest
    | InhalationTier1ScenarioRequest,
    updated_request: ExposureScenarioRequest,
) -> ExposureScenarioRequest | InhalationScenarioRequest | InhalationTier1ScenarioRequest:
    shared_update = {
        "chemical_id": updated_request.chemical_id,
        "chemical_name": updated_request.chemical_name,
        "route": updated_request.route,
        "scenario_class": updated_request.scenario_class,
        "product_use_profile": updated_request.product_use_profile,
        "population_profile": updated_request.population_profile,
        "assumption_overrides": updated_request.assumption_overrides,
    }
    return source_request.model_copy(update=shared_update, deep=True)


def _build_scenario_from_request(
    request: ExposureScenarioRequest | InhalationScenarioRequest | InhalationTier1ScenarioRequest,
    registry: DefaultsRegistry,
    *,
    generated_at: str | None = None,
) -> ExposureScenario:
    plugin_registry = PluginRegistry()
    plugin_registry.register(ScreeningScenarioPlugin())
    plugin_registry.register(InhalationScreeningPlugin())
    engine = ScenarioEngine(registry=plugin_registry, defaults_registry=registry)

    if isinstance(request, InhalationTier1ScenarioRequest):
        scenario = build_inhalation_tier_1_screening_scenario(
            request,
            registry,
            profile_registry=Tier1InhalationProfileRegistry.load(),
            generated_at=generated_at,
        )
        return enrich_scenario_uncertainty(engine, scenario)
    return engine.build(request)


TOXCLAW_REFINE_EXPOSURE_RECOMMENDATION = (
    "Refine exposure characterization before relying on the screening recommendation."
)


def _comparison_delta_direction(
    comparison: ScenarioComparisonRecord,
) -> Literal["increase", "decrease", "no_change"]:
    if comparison.absolute_delta > 0:
        return "increase"
    if comparison.absolute_delta < 0:
        return "decrease"
    return "no_change"


def _comparison_delta_note(comparison: ScenarioComparisonRecord) -> str:
    if comparison.percent_delta is None:
        return "Baseline dose was zero; percentage delta is undefined."
    if comparison.percent_delta > 0:
        return f"Comparison dose increased by {comparison.percent_delta:.2f}% relative to baseline."
    if comparison.percent_delta < 0:
        return (
            f"Comparison dose decreased by {abs(comparison.percent_delta):.2f}% "
            "relative to baseline."
        )
    return "Comparison dose is numerically identical to the baseline."


def _workflow_action_note(
    workflow_action: Literal["scenario_comparison", "route_recalculation", "aggregate_variant"],
) -> str:
    if workflow_action == "route_recalculation":
        return (
            "This comparison represents a route-specific recalculation candidate and should "
            "remain an exposure-context refinement trace only."
        )
    if workflow_action == "aggregate_variant":
        return (
            "This comparison represents an aggregate-variant refinement and should be "
            "interpreted alongside the component scenarios."
        )
    return (
        "This comparison should inform exposure refinement only; ToxClaw remains responsible "
        "for the final recommendation."
    )


def _comparison_summary(
    comparison: ScenarioComparisonRecord,
    workflow_action: Literal["scenario_comparison", "route_recalculation", "aggregate_variant"],
) -> str:
    action_label = workflow_action.replace("_", " ")
    direction = _comparison_delta_direction(comparison)
    if comparison.percent_delta is None:
        return (
            f"Exposure {action_label} recorded absolute delta "
            f"{comparison.absolute_delta} {comparison.baseline_dose.unit.value}."
        )
    if direction == "increase":
        return (
            f"Exposure {action_label} increased external dose by "
            f"{comparison.percent_delta:.2f}% relative to baseline."
        )
    if direction == "decrease":
        return (
            f"Exposure {action_label} decreased external dose by "
            f"{abs(comparison.percent_delta):.2f}% relative to baseline."
        )
    return f"Exposure {action_label} produced no numerical dose change relative to baseline."


def _route_recalculation_tool_name(
    scenario: ExposureScenario,
) -> Literal[
    "exposure_build_screening_exposure_scenario",
    "exposure_build_inhalation_screening_scenario",
]:
    if scenario.route == Route.INHALATION:
        return "exposure_build_inhalation_screening_scenario"
    return "exposure_build_screening_exposure_scenario"


class CompToxChemicalRecord(StrictModel):
    schema_version: Literal["compToxChemicalRecord.v1"] = "compToxChemicalRecord.v1"
    chemical_id: str = Field(..., description="Stable CompTox chemical identifier.")
    preferred_name: str = Field(..., description="Preferred chemical name.")
    casrn: str | None = Field(default=None, description="CAS Registry Number when known.")
    product_use_categories: list[str] = Field(
        default_factory=list,
        description="Relevant product-use categories discovered upstream.",
    )
    physchem_summary: dict[str, ScalarValue] = Field(
        default_factory=dict,
        description="Physicochemical context that can support downstream scenario interpretation.",
    )
    evidence_sources: list[str] = Field(
        default_factory=list,
        description="Upstream evidence or record identifiers backing the CompTox record.",
    )


class ConsExpoEvidenceRecord(StrictModel):
    schema_version: Literal["consExpoEvidenceRecord.v1"] = "consExpoEvidenceRecord.v1"
    chemical_id: str = Field(..., description="Stable chemical identifier shared with the request.")
    preferred_name: str | None = Field(
        default=None,
        description="Preferred chemical name when the ConsExpo source is already tied to identity.",
    )
    casrn: str | None = Field(default=None, description="CAS Registry Number when known.")
    fact_sheet_id: str = Field(..., alias="factSheetId")
    fact_sheet_title: str = Field(..., alias="factSheetTitle")
    fact_sheet_version: str = Field(..., alias="factSheetVersion")
    fact_sheet_locator: str = Field(..., alias="factSheetLocator")
    product_group: str = Field(
        ...,
        alias="productGroup",
        description="ConsExpo product-group family such as cosmetics or pest_control_products.",
    )
    product_subgroup: str | None = Field(
        default=None,
        alias="productSubgroup",
        description="Optional narrower ConsExpo subgroup or scenario label.",
    )
    model_family: str | None = Field(
        default=None,
        alias="modelFamily",
        description="Optional ConsExpo model family such as spray or direct_application.",
    )
    supported_routes: list[Route] = Field(
        default_factory=list,
        alias="supportedRoutes",
        description="Routes explicitly supported by the cited ConsExpo source.",
    )
    physical_forms: list[str] = Field(
        default_factory=list,
        description="Physical forms supported by the ConsExpo source.",
    )
    application_methods: list[str] = Field(
        default_factory=list,
        description="Application methods supported by the ConsExpo source.",
    )
    retention_types: list[str] = Field(
        default_factory=list,
        description="Retention or contact semantics supported by the ConsExpo source.",
    )
    region_scopes: list[str] = Field(
        default_factory=lambda: ["EU"],
        description="Regions where the ConsExpo evidence is considered applicable.",
    )
    jurisdictions: list[str] = Field(
        default_factory=lambda: ["EU"],
        description="Jurisdictions or programs where the ConsExpo evidence is relevant.",
    )
    physchem_summary: dict[str, ScalarValue] = Field(
        default_factory=dict,
        description="Optional physicochemical context preserved from the ConsExpo source.",
    )
    evidence_sources: list[str] = Field(
        default_factory=list,
        description="Stable upstream evidence references backing the ConsExpo record.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Additional notes preserved from the ConsExpo source.",
    )


class SccsCosmeticsEvidenceRecord(StrictModel):
    schema_version: Literal["sccsCosmeticsEvidenceRecord.v1"] = "sccsCosmeticsEvidenceRecord.v1"
    chemical_id: str = Field(..., description="Stable chemical identifier shared with the request.")
    preferred_name: str | None = Field(
        default=None,
        description="Preferred chemical name when the SCCS source is already tied to identity.",
    )
    casrn: str | None = Field(default=None, description="CAS Registry Number when known.")
    guidance_id: str = Field(..., alias="guidanceId")
    guidance_title: str = Field(..., alias="guidanceTitle")
    guidance_version: str = Field(..., alias="guidanceVersion")
    guidance_locator: str = Field(..., alias="guidanceLocator")
    cosmetic_product_type: str = Field(
        ...,
        alias="cosmeticProductType",
        description="Cosmetic product type label from SCCS guidance, for example face cream.",
    )
    product_family: str | None = Field(
        default=None,
        alias="productFamily",
        description="Optional broader SCCS product family such as skin_care or hair_care.",
    )
    table_references: list[str] = Field(
        default_factory=list,
        alias="tableReferences",
        description="Notes of Guidance table or section references backing the record.",
    )
    supported_routes: list[Route] = Field(
        default_factory=lambda: [Route.DERMAL],
        alias="supportedRoutes",
        description="Routes explicitly supported by the cited SCCS guidance context.",
    )
    physical_forms: list[str] = Field(
        default_factory=list,
        description="Physical forms supported by the SCCS source.",
    )
    application_methods: list[str] = Field(
        default_factory=list,
        description="Application methods supported by the SCCS source.",
    )
    retention_types: list[str] = Field(
        default_factory=list,
        description="Retention or contact semantics supported by the SCCS source.",
    )
    product_use_profile_overrides: dict[str, ScalarValue] = Field(
        default_factory=dict,
        alias="productUseProfileOverrides",
        description=(
            "Reviewed product-use profile fields such as use_amount_per_event, "
            "use_amount_unit, or use_events_per_day."
        ),
    )
    population_profile_overrides: dict[str, ScalarValue] = Field(
        default_factory=dict,
        alias="populationProfileOverrides",
        description=(
            "Reviewed population-profile fields such as exposed_surface_area_cm2 or body_weight_kg."
        ),
    )
    region_scopes: list[str] = Field(
        default_factory=lambda: ["EU"],
        description="Regions where the SCCS evidence is considered applicable.",
    )
    jurisdictions: list[str] = Field(
        default_factory=lambda: ["EU", "SCCS"],
        description="Jurisdictions or programs where the SCCS evidence is relevant.",
    )
    evidence_sources: list[str] = Field(
        default_factory=list,
        description="Stable upstream evidence references backing the SCCS record.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Additional notes preserved from the SCCS source.",
    )


class SccsOpinionEvidenceRecord(StrictModel):
    schema_version: Literal["sccsOpinionEvidenceRecord.v1"] = "sccsOpinionEvidenceRecord.v1"
    chemical_id: str = Field(..., description="Stable chemical identifier shared with the request.")
    preferred_name: str | None = Field(default=None, description="Preferred chemical name.")
    casrn: str | None = Field(default=None, description="CAS Registry Number when known.")
    opinion_id: str = Field(..., alias="opinionId")
    opinion_title: str = Field(..., alias="opinionTitle")
    opinion_version: str = Field(..., alias="opinionVersion")
    opinion_locator: str = Field(..., alias="opinionLocator")
    cosmetic_product_types: list[str] = Field(
        default_factory=list,
        alias="cosmeticProductTypes",
        description="Cosmetic product types or families referenced in the opinion.",
    )
    supported_routes: list[Route] = Field(
        default_factory=list, alias="supportedRoutes", description="Opinion-relevant routes."
    )
    physical_forms: list[str] = Field(default_factory=list)
    application_methods: list[str] = Field(default_factory=list)
    retention_types: list[str] = Field(default_factory=list)
    particle_material_context: ParticleMaterialContext | None = Field(
        default=None,
        alias="particleMaterialContext",
        description="Optional particle-aware context preserved from the SCCS opinion.",
    )
    region_scopes: list[str] = Field(default_factory=lambda: ["EU"])
    jurisdictions: list[str] = Field(default_factory=lambda: ["EU", "SCCS"])
    evidence_sources: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CosIngIngredientRecord(StrictModel):
    schema_version: Literal["cosIngIngredientRecord.v1"] = "cosIngIngredientRecord.v1"
    chemical_id: str = Field(..., description="Stable chemical identifier shared with the request.")
    preferred_name: str | None = Field(default=None, description="Preferred chemical name.")
    inci_name: str | None = Field(default=None, alias="inciName")
    casrn: str | None = Field(default=None, description="CAS Registry Number when known.")
    ec_number: str | None = Field(default=None, alias="ecNumber")
    cosing_locator: str = Field(..., alias="cosingLocator")
    functions: list[str] = Field(
        default_factory=list, description="Cosmetic ingredient functions listed in CosIng."
    )
    annex_references: list[str] = Field(
        default_factory=list,
        alias="annexReferences",
        description="EU Cosmetics Regulation annex references when listed in CosIng.",
    )
    nanomaterial_flag: bool | None = Field(
        default=None,
        alias="nanomaterialFlag",
        description="Whether the CosIng context indicates a nanomaterial-relevant entry.",
    )
    particle_material_context: ParticleMaterialContext | None = Field(
        default=None,
        alias="particleMaterialContext",
        description="Optional particle-aware context preserved from CosIng metadata.",
    )
    region_scopes: list[str] = Field(default_factory=lambda: ["EU"])
    jurisdictions: list[str] = Field(default_factory=lambda: ["EU", "CosIng"])
    evidence_sources: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class NanoMaterialEvidenceRecord(StrictModel):
    schema_version: Literal["nanoMaterialEvidenceRecord.v1"] = "nanoMaterialEvidenceRecord.v1"
    chemical_id: str = Field(..., description="Stable chemical identifier shared with the request.")
    preferred_name: str | None = Field(default=None, description="Preferred chemical name.")
    casrn: str | None = Field(default=None, description="CAS Registry Number when known.")
    source_record_id: str = Field(..., alias="sourceRecordId")
    source_title: str = Field(..., alias="sourceTitle")
    source_version: str = Field(..., alias="sourceVersion")
    source_locator: str = Field(..., alias="sourceLocator")
    source_program: str = Field(
        ..., alias="sourceProgram", description="Source program such as SCCS or CPNP/EC catalogue."
    )
    cosmetic_product_types: list[str] = Field(
        default_factory=list,
        alias="cosmeticProductTypes",
        description="Cosmetic product types or families linked to the nanomaterial context.",
    )
    supported_routes: list[Route] = Field(
        default_factory=list,
        alias="supportedRoutes",
        description="Routes relevant to this nano context.",
    )
    physical_forms: list[str] = Field(default_factory=list)
    application_methods: list[str] = Field(default_factory=list)
    retention_types: list[str] = Field(default_factory=list)
    particle_material_context: ParticleMaterialContext = Field(
        ...,
        alias="particleMaterialContext",
        description="Structured particle-aware material context.",
    )
    region_scopes: list[str] = Field(default_factory=lambda: ["EU"])
    jurisdictions: list[str] = Field(default_factory=lambda: ["EU"])
    evidence_sources: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SyntheticPolymerMicroparticleEvidenceRecord(StrictModel):
    schema_version: Literal["syntheticPolymerMicroparticleEvidenceRecord.v1"] = (
        "syntheticPolymerMicroparticleEvidenceRecord.v1"
    )
    chemical_id: str = Field(..., description="Stable chemical identifier shared with the request.")
    preferred_name: str | None = Field(default=None, description="Preferred chemical name.")
    casrn: str | None = Field(default=None, description="CAS Registry Number when known.")
    source_record_id: str = Field(..., alias="sourceRecordId")
    source_title: str = Field(..., alias="sourceTitle")
    source_version: str = Field(..., alias="sourceVersion")
    source_locator: str = Field(..., alias="sourceLocator")
    restriction_scope: str = Field(
        ..., alias="restrictionScope", description="Restriction or reporting scope description."
    )
    product_use_categories: list[str] = Field(
        default_factory=lambda: ["personal_care"],
        alias="productUseCategories",
        description="Direct-use categories linked to the synthetic polymer microparticle context.",
    )
    supported_routes: list[Route] = Field(default_factory=list, alias="supportedRoutes")
    physical_forms: list[str] = Field(default_factory=list)
    application_methods: list[str] = Field(default_factory=list)
    retention_types: list[str] = Field(default_factory=list)
    particle_material_context: ParticleMaterialContext = Field(
        ...,
        alias="particleMaterialContext",
        description="Structured particle-aware material context.",
    )
    region_scopes: list[str] = Field(default_factory=lambda: ["EU"])
    jurisdictions: list[str] = Field(default_factory=lambda: ["EU", "ECHA", "REACH"])
    evidence_sources: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ProductUseEvidenceRecord(StrictModel):
    schema_version: Literal["productUseEvidenceRecord.v1"] = "productUseEvidenceRecord.v1"
    chemical_id: str = Field(..., description="Stable chemical identifier shared with the request.")
    preferred_name: str | None = Field(
        default=None,
        description="Preferred chemical name when the evidence source also carries identity data.",
    )
    casrn: str | None = Field(default=None, description="CAS Registry Number when known.")
    source_name: str = Field(..., description="Human-readable evidence-source label.")
    source_kind: Literal[
        "comptox",
        "consexpo",
        "sccs",
        "cosing",
        "nanomaterial_guidance",
        "microplastics_regulatory",
        "regulatory_dossier",
        "literature_pack",
        "user_upload",
        "other",
    ] = Field(
        default="other",
        description="What kind of upstream source produced the product-use evidence.",
    )
    review_status: Literal["reviewed", "provisional", "unreviewed"] = Field(
        default="provisional",
        description="Whether the evidence has been reviewed for downstream use.",
    )
    source_record_id: str | None = Field(
        default=None,
        description="Optional upstream record identifier such as a dossier or registry ID.",
    )
    source_locator: str | None = Field(
        default=None,
        description="Optional URL or logical locator for the upstream record.",
    )
    product_name: str | None = Field(
        default=None,
        description="Optional product label or family name carried by the evidence source.",
    )
    product_subtype: str | None = Field(
        default=None,
        description="Optional narrower product-use subtype carried by the evidence source.",
    )
    product_use_categories: list[str] = Field(
        default_factory=list,
        description="Candidate product-use categories supported by the evidence source.",
    )
    physical_forms: list[str] = Field(
        default_factory=list,
        description="Physical forms supported by the evidence source.",
    )
    application_methods: list[str] = Field(
        default_factory=list,
        description="Application methods supported by the evidence source.",
    )
    retention_types: list[str] = Field(
        default_factory=list,
        description="Retention or contact semantics supported by the evidence source.",
    )
    region_scopes: list[str] = Field(
        default_factory=list,
        description="Regions where the product-use evidence is considered applicable.",
    )
    jurisdictions: list[str] = Field(
        default_factory=list,
        description="Jurisdictions or regulatory programs that back the evidence source.",
    )
    physchem_summary: dict[str, ScalarValue] = Field(
        default_factory=dict,
        description="Optional physicochemical context preserved for downstream review.",
    )
    particle_material_context: ParticleMaterialContext | None = Field(
        default=None,
        alias="particleMaterialContext",
        description="Optional structured particle-aware material context.",
    )
    product_use_profile_overrides: dict[str, ScalarValue] = Field(
        default_factory=dict,
        alias="productUseProfileOverrides",
        description=("Reviewed product-use profile fields suggested by the evidence source."),
    )
    population_profile_overrides: dict[str, ScalarValue] = Field(
        default_factory=dict,
        alias="populationProfileOverrides",
        description=("Reviewed population-profile fields suggested by the evidence source."),
    )
    evidence_sources: list[str] = Field(
        default_factory=list,
        description="Stable upstream evidence references backing the record.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Additional applicability or review notes preserved verbatim.",
    )


class ProductUseEvidenceFitReport(StrictModel):
    schema_version: Literal["productUseEvidenceFitReport.v1"] = "productUseEvidenceFitReport.v1"
    chemical_id: str = Field(..., description="Chemical identifier shared by the request and fit.")
    evidence_source_name: str = Field(..., description="Human-readable evidence-source label.")
    evidence_source_kind: str = Field(..., description="Evidence-source kind copied into the fit.")
    request_region: str = Field(..., description="Region declared on the scenario request.")
    compatible: bool = Field(..., description="Whether the evidence can be used at all.")
    auto_apply_safe: bool = Field(
        ...,
        description="Whether the evidence can be applied without human review warnings.",
    )
    recommendation: Literal["accept", "accept_with_review", "manual_review", "reject"] = Field(
        ...,
        description="High-level recommendation for orchestrators.",
    )
    matched_fields: list[str] = Field(
        default_factory=list,
        description="Request fields already aligned with the evidence record.",
    )
    suggested_updates: list[str] = Field(
        default_factory=list,
        description="Request fields the evidence record would update or annotate.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-blocking reasons to review the evidence before using it.",
    )
    blocking_issues: list[str] = Field(
        default_factory=list,
        description="Reasons the evidence should not be applied automatically.",
    )
    suggested_request: ExposureScenarioRequest = Field(
        ...,
        description="Request preview after applying additive evidence-driven enrichment.",
    )


class AssessProductUseEvidenceFitInput(StrictModel):
    schema_version: Literal["assessProductUseEvidenceFitInput.v1"] = (
        "assessProductUseEvidenceFitInput.v1"
    )
    request: ExposureScenarioRequest = Field(..., description="Scenario request to assess.")
    evidence: ProductUseEvidenceRecord = Field(
        ...,
        description="Generic product-use evidence supplied by CompTox or another source.",
    )


class ApplyProductUseEvidenceInput(StrictModel):
    schema_version: Literal["applyProductUseEvidenceInput.v1"] = "applyProductUseEvidenceInput.v1"
    request: ExposureScenarioRequest = Field(..., description="Scenario request to enrich.")
    evidence: ProductUseEvidenceRecord = Field(
        ...,
        description="Generic product-use evidence supplied by CompTox or another source.",
    )
    require_auto_apply_safe: bool = Field(
        default=False,
        alias="requireAutoApplySafe",
        description=(
            "When true, reject evidence records that need human review even if they are "
            "otherwise compatible."
        ),
    )


class BuildProductUseEvidenceFromConsExpoInput(StrictModel):
    schema_version: Literal["buildProductUseEvidenceFromConsExpoInput.v1"] = (
        "buildProductUseEvidenceFromConsExpoInput.v1"
    )
    evidence: ConsExpoEvidenceRecord = Field(
        ...,
        description="Typed ConsExpo evidence record to map into the generic evidence contract.",
    )


class BuildProductUseEvidenceFromSccsInput(StrictModel):
    schema_version: Literal["buildProductUseEvidenceFromSccsInput.v1"] = (
        "buildProductUseEvidenceFromSccsInput.v1"
    )
    evidence: SccsCosmeticsEvidenceRecord = Field(
        ...,
        description=(
            "Typed SCCS cosmetics evidence record to map into the generic evidence contract."
        ),
    )


class BuildProductUseEvidenceFromSccsOpinionInput(StrictModel):
    schema_version: Literal["buildProductUseEvidenceFromSccsOpinionInput.v1"] = (
        "buildProductUseEvidenceFromSccsOpinionInput.v1"
    )
    evidence: SccsOpinionEvidenceRecord = Field(
        ...,
        description="Typed SCCS opinion record to map into the generic evidence contract.",
    )


class BuildProductUseEvidenceFromCosIngInput(StrictModel):
    schema_version: Literal["buildProductUseEvidenceFromCosIngInput.v1"] = (
        "buildProductUseEvidenceFromCosIngInput.v1"
    )
    evidence: CosIngIngredientRecord = Field(
        ...,
        description="Typed CosIng ingredient record to map into the generic evidence contract.",
    )


class BuildProductUseEvidenceFromNanoMaterialInput(StrictModel):
    schema_version: Literal["buildProductUseEvidenceFromNanoMaterialInput.v1"] = (
        "buildProductUseEvidenceFromNanoMaterialInput.v1"
    )
    evidence: NanoMaterialEvidenceRecord = Field(
        ...,
        description="Typed nanomaterial evidence record to map into the generic evidence contract.",
    )


class BuildProductUseEvidenceFromSyntheticPolymerMicroparticleInput(StrictModel):
    schema_version: Literal["buildProductUseEvidenceFromSyntheticPolymerMicroparticleInput.v1"] = (
        "buildProductUseEvidenceFromSyntheticPolymerMicroparticleInput.v1"
    )
    evidence: SyntheticPolymerMicroparticleEvidenceRecord = Field(
        ...,
        description=(
            "Typed synthetic polymer microparticle evidence record to map into the generic "
            "evidence contract."
        ),
    )


class ProductUseEvidenceReconciliationReport(StrictModel):
    schema_version: Literal["productUseEvidenceReconciliationReport.v1"] = (
        "productUseEvidenceReconciliationReport.v1"
    )
    chemical_id: str = Field(
        ...,
        description="Chemical identifier shared by the request and evidence.",
    )
    request_region: str = Field(
        ...,
        description="Region declared on the original scenario request.",
    )
    considered_sources: list[str] = Field(
        default_factory=list,
        description="All evidence sources considered during reconciliation.",
        alias="consideredSources",
    )
    compatible_sources: list[str] = Field(
        default_factory=list,
        description="Compatible evidence sources after fit assessment.",
        alias="compatibleSources",
    )
    recommended_source_name: str | None = Field(
        default=None,
        description="Primary evidence source selected for the merged request preview.",
        alias="recommendedSourceName",
    )
    recommended_source_kind: str | None = Field(
        default=None,
        description="Kind of the primary evidence source selected for the merged request preview.",
        alias="recommendedSourceKind",
    )
    recommendation: Literal["apply", "apply_with_review", "manual_review", "reject"] = Field(
        ...,
        description="High-level reconciliation recommendation for orchestrators.",
    )
    manual_review_required: bool = Field(
        ...,
        description="Whether a human should review the reconciliation result before use.",
        alias="manualReviewRequired",
    )
    conflicts: list[str] = Field(
        default_factory=list,
        description="Cross-source conflicts that remain after compatibility filtering.",
    )
    rationale: list[str] = Field(
        default_factory=list,
        description="Short explanation of why the primary source was selected.",
    )
    field_sources: dict[str, str] = Field(
        default_factory=dict,
        description="Which source supplied each additive field in the merged request preview.",
        alias="fieldSources",
    )
    fit_reports: list[ProductUseEvidenceFitReport] = Field(
        default_factory=list,
        description="Per-source fit reports against the original request.",
        alias="fitReports",
    )
    merged_request: ExposureScenarioRequest | None = Field(
        default=None,
        description="Merged request preview using the selected evidence strategy.",
        alias="mergedRequest",
    )


class ReconcileProductUseEvidenceInput(StrictModel):
    schema_version: Literal["reconcileProductUseEvidenceInput.v1"] = (
        "reconcileProductUseEvidenceInput.v1"
    )
    request: ExposureScenarioRequest = Field(..., description="Scenario request to reconcile.")
    evidence_records: list[ProductUseEvidenceRecord] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Evidence records to compare and reconcile.",
        alias="evidenceRecords",
    )
    require_auto_apply_safe: bool = Field(
        default=False,
        alias="requireAutoApplySafe",
        description=(
            "When true, any review-needed primary recommendation is surfaced as manual review "
            "instead of apply-with-review."
        ),
    )


class ToxClawEvidenceEnvelope(StrictModel):
    schema_version: Literal["toxclawEvidenceEnvelope.v1"] = "toxclawEvidenceEnvelope.v1"
    source_module: Literal["exposure_scenario_mcp"] = "exposure_scenario_mcp"
    record_kind: str = Field(..., description="Scenario, aggregate summary, or comparison record.")
    chemical_id: str = Field(..., description="Shared chemical identifier.")
    context_of_use: str = Field(..., description="Why the evidence is being emitted.")
    route: str | None = Field(default=None, description="Primary route when applicable.")
    scenario_class: str | None = Field(
        default=None, description="Primary scenario class when applicable."
    )
    summary: str = Field(..., description="One-line evidence summary for orchestration.")
    fit_for_purpose: FitForPurpose | None = Field(
        default=None,
        description="Fit-for-purpose metadata if the wrapped record has it.",
    )
    limitations: list[LimitationNote] = Field(
        default_factory=list,
        description="Limitations preserved from the wrapped record.",
    )
    quality_flags: list[QualityFlag] = Field(
        default_factory=list,
        description="Quality flags preserved from the wrapped record.",
    )
    provenance: ProvenanceBundle = Field(..., description="Provenance of the wrapped record.")
    payload: dict = Field(..., description="Wrapped record payload.")


class ToxClawEvidenceRecord(StrictModel):
    schema_version: Literal["toxclawEvidenceRecord.v1"] = Field(
        default="toxclawEvidenceRecord.v1", alias="schemaVersion"
    )
    case_id: str = Field(..., alias="caseId")
    content_hash: str = Field(..., alias="contentHash")
    data_classification: Literal["public", "internal", "restricted", "regulated"] = Field(
        ..., alias="dataClassification"
    )
    evidence_id: str = Field(..., alias="evidenceId")
    quality_flag: str | None = Field(default=None, alias="qualityFlag")
    raw_pointer: str | None = Field(default=None, alias="rawPointer")
    redaction_status: str | None = Field(default=None, alias="redactionStatus")
    retrieved_at: str = Field(..., alias="retrievedAt")
    run_id: str | None = Field(default=None, alias="runId")
    source: str = Field(..., description="ToxClaw evidence source string.")
    source_ref: str = Field(..., alias="sourceRef")
    summary: str = Field(..., description="Human-readable evidence summary.")
    tags: list[str] = Field(default_factory=list)
    trust_label: Literal["module-output", "untrusted-document", "untrusted-external-data"] = Field(
        ..., alias="trustLabel"
    )
    type: str = Field(..., description="ToxClaw evidence type label.")


class ToxClawReportEvidenceReference(StrictModel):
    schema_version: Literal["toxclawReportEvidenceReference.v1"] = Field(
        default="toxclawReportEvidenceReference.v1", alias="schemaVersion"
    )
    content_hash: str = Field(..., alias="contentHash")
    evidence_id: str = Field(..., alias="evidenceId")
    quality_flag: str | None = Field(default=None, alias="qualityFlag")
    raw_pointer: str | None = Field(default=None, alias="rawPointer")
    redaction_status: str | None = Field(default=None, alias="redactionStatus")
    retrieved_at: str = Field(..., alias="retrievedAt")
    source: str
    source_ref: str = Field(..., alias="sourceRef")
    summary: str
    tags: list[str] = Field(default_factory=list)
    trust_label: Literal["module-output", "untrusted-document", "untrusted-external-data"] = Field(
        ..., alias="trustLabel"
    )
    type: str


class ToxClawReportClaim(StrictModel):
    schema_version: Literal["toxclawReportClaim.v1"] = Field(
        default="toxclawReportClaim.v1", alias="schemaVersion"
    )
    claim_id: str = Field(..., alias="claimId")
    confidence: Literal["heuristic", "provisional", "supported", "unverified"]
    evidence_ids: list[str] = Field(default_factory=list, alias="evidenceIds")
    text: str


class ToxClawReportSection(StrictModel):
    schema_version: Literal["toxclawReportSection.v1"] = Field(
        default="toxclawReportSection.v1", alias="schemaVersion"
    )
    body: str
    claims: list[ToxClawReportClaim] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list, alias="evidenceIds")
    section_key: str = Field(..., alias="sectionKey")
    title: str


class ToxClawEvidenceBundle(StrictModel):
    schema_version: Literal["toxclawEvidenceBundle.v1"] = Field(
        default="toxclawEvidenceBundle.v1", alias="schemaVersion"
    )
    case_id: str = Field(..., alias="caseId")
    report_id: str = Field(..., alias="reportId")
    context_of_use: str = Field(..., alias="contextOfUse")
    source_module: Literal["exposure-scenario-mcp"] = Field(
        default="exposure-scenario-mcp", alias="sourceModule"
    )
    summary: str
    evidence_record: ToxClawEvidenceRecord = Field(..., alias="evidenceRecord")
    report_evidence_reference: ToxClawReportEvidenceReference = Field(
        ..., alias="reportEvidenceReference"
    )
    report_section: ToxClawReportSection = Field(..., alias="reportSection")


class ExposureWorkflowHook(StrictModel):
    schema_version: Literal["exposureWorkflowHook.v1"] = Field(
        default="exposureWorkflowHook.v1", alias="schemaVersion"
    )
    action: Literal[
        "scenario_comparison", "route_recalculation", "aggregate_variant", "pbpk_export"
    ]
    tool_name: Literal[
        "exposure_compare_exposure_scenarios",
        "exposure_compare_jurisdictional_scenarios",
        "exposure_build_screening_exposure_scenario",
        "exposure_build_inhalation_screening_scenario",
        "exposure_build_aggregate_exposure_scenario",
        "exposure_export_pbpk_external_import_bundle",
    ] = Field(..., alias="toolName")
    when_to_use: str = Field(..., alias="whenToUse")
    required_inputs: list[str] = Field(default_factory=list, alias="requiredInputs")


class ToxClawExposureRefinementSignal(StrictModel):
    schema_version: Literal["toxclawExposureRefinementSignal.v1"] = Field(
        default="toxclawExposureRefinementSignal.v1", alias="schemaVersion"
    )
    recommendation: Literal["refine_exposure"] = "refine_exposure"
    refinement_recommendation: str = Field(
        default=TOXCLAW_REFINE_EXPOSURE_RECOMMENDATION,
        alias="refinementRecommendation",
    )
    loe_candidate_keys: list[str] = Field(
        default_factory=lambda: ["exposure_context"],
        alias="loeCandidateKeys",
    )
    workflow_action: Literal["scenario_comparison", "route_recalculation", "aggregate_variant"] = (
        Field(..., alias="workflowAction")
    )
    route_changed: bool = Field(..., alias="routeChanged")
    changed_assumption_names: list[str] = Field(
        default_factory=list, alias="changedAssumptionNames"
    )
    changed_assumption_count: int = Field(..., alias="changedAssumptionCount")
    dose_delta_direction: Literal["increase", "decrease", "no_change"] = Field(
        ..., alias="doseDeltaDirection"
    )
    percent_delta: float | None = Field(default=None, alias="percentDelta")
    material_change: bool = Field(..., alias="materialChange")
    boundary_note: str = Field(..., alias="boundaryNote")
    workflow_hooks: list[ExposureWorkflowHook] = Field(default_factory=list, alias="workflowHooks")


class ToxClawExposureRefinementBundle(StrictModel):
    schema_version: Literal["toxclawExposureRefinementBundle.v1"] = Field(
        default="toxclawExposureRefinementBundle.v1", alias="schemaVersion"
    )
    case_id: str = Field(..., alias="caseId")
    report_id: str = Field(..., alias="reportId")
    context_of_use: str = Field(..., alias="contextOfUse")
    source_module: Literal["exposure-scenario-mcp"] = Field(
        default="exposure-scenario-mcp", alias="sourceModule"
    )
    workflow_action: Literal["scenario_comparison", "route_recalculation", "aggregate_variant"] = (
        Field(..., alias="workflowAction")
    )
    summary: str
    baseline_scenario: ExposureScenario = Field(..., alias="baselineScenario")
    comparison_scenario: ExposureScenario = Field(..., alias="comparisonScenario")
    comparison_record: ScenarioComparisonRecord = Field(..., alias="comparisonRecord")
    evidence_record: ToxClawEvidenceRecord = Field(..., alias="evidenceRecord")
    report_evidence_reference: ToxClawReportEvidenceReference = Field(
        ..., alias="reportEvidenceReference"
    )
    report_section: ToxClawReportSection = Field(..., alias="reportSection")
    refinement_signal: ToxClawExposureRefinementSignal = Field(..., alias="refinementSignal")


class PbpkExternalArtifact(StrictModel):
    type: str = Field(..., min_length=1)
    path: str = Field(..., min_length=1)
    checksum: str | None = None
    title: str | None = None


class PbpkExternalImportBundle(StrictModel):
    schema_version: Literal["pbpkExternalImportBundle.v1"] = Field(
        default="pbpkExternalImportBundle.v1", alias="schemaVersion"
    )
    source_platform: str = Field(..., alias="sourcePlatform")
    source_version: str | None = Field(default=None, alias="sourceVersion")
    model_name: str | None = Field(default=None, alias="modelName")
    model_type: str = Field(..., alias="modelType")
    execution_date: str | None = Field(default=None, alias="executionDate")
    run_id: str | None = Field(default=None, alias="runId")
    operator: str | None = None
    sponsor: str | None = None
    raw_artifacts: list[PbpkExternalArtifact] = Field(default_factory=list, alias="rawArtifacts")
    assessment_context: dict = Field(default_factory=dict, alias="assessmentContext")
    chemical_identity: dict = Field(default_factory=dict, alias="chemicalIdentity")
    supporting_handoffs: dict = Field(default_factory=dict, alias="supportingHandoffs")
    internal_exposure: dict = Field(default_factory=dict, alias="internalExposure")
    qualification: dict = Field(default_factory=dict)
    uncertainty: dict = Field(default_factory=dict)
    uncertainty_register: dict = Field(default_factory=dict, alias="uncertaintyRegister")
    pod: dict = Field(default_factory=dict)
    true_dose_adjustment: dict = Field(default_factory=dict, alias="trueDoseAdjustment")
    comparison_metric: str = Field(default="cmax", alias="comparisonMetric")


class PbpkExternalImportRequest(StrictModel):
    source_platform: str = Field(..., alias="sourcePlatform")
    source_version: str | None = Field(default=None, alias="sourceVersion")
    model_name: str | None = Field(default=None, alias="modelName")
    model_type: str = Field(..., alias="modelType")
    execution_date: str | None = Field(default=None, alias="executionDate")
    run_id: str | None = Field(default=None, alias="runId")
    operator: str | None = None
    sponsor: str | None = None
    raw_artifacts: list[PbpkExternalArtifact] = Field(default_factory=list, alias="rawArtifacts")
    assessment_context: dict = Field(default_factory=dict, alias="assessmentContext")
    internal_exposure: dict = Field(default_factory=dict, alias="internalExposure")
    qualification: dict = Field(default_factory=dict)
    uncertainty: dict = Field(default_factory=dict)
    uncertainty_register: dict = Field(default_factory=dict, alias="uncertaintyRegister")
    pod: dict = Field(default_factory=dict)
    true_dose_adjustment: dict = Field(default_factory=dict, alias="trueDoseAdjustment")
    comparison_metric: str = Field(default="cmax", alias="comparisonMetric")


class PbpkExternalImportToolCall(StrictModel):
    schema_version: Literal["pbpkExternalImportToolCall.v1"] = Field(
        default="pbpkExternalImportToolCall.v1", alias="schemaVersion"
    )
    tool_name: Literal["ingest_external_pbpk_bundle"] = Field(
        default="ingest_external_pbpk_bundle", alias="toolName"
    )
    arguments: PbpkExternalImportRequest


class ToxClawPbpkModuleParams(StrictModel):
    schema_version: Literal["toxclawPbpkModuleParams.v1"] = Field(
        default="toxclawPbpkModuleParams.v1", alias="schemaVersion"
    )
    ingest_tool_name: Literal["ingest_external_pbpk_bundle"] = Field(
        default="ingest_external_pbpk_bundle", alias="ingestToolName"
    )
    arguments: PbpkExternalImportRequest
    chemical_identity: dict = Field(default_factory=dict, alias="chemicalIdentity")
    supporting_handoffs: dict = Field(default_factory=dict, alias="supportingHandoffs")


class PbpkCompatibilityReport(StrictModel):
    schema_version: Literal["pbpkCompatibilityReport.v1"] = "pbpkCompatibilityReport.v1"
    source_scenario_id: str = Field(..., description="Source scenario identifier.")
    compatible: bool = Field(..., description="Whether the object is PBPK-compatible.")
    target_tool: Literal["ingest_external_pbpk_bundle"] = Field(
        default="ingest_external_pbpk_bundle",
        description="PBPK MCP tool evaluated for downstream readiness.",
    )
    checked_route: Route = Field(..., description="Route checked for compatibility.")
    checked_dose_unit: str = Field(..., description="Dose unit checked for compatibility.")
    ready_for_external_pbpk_import: bool = Field(
        ...,
        description=(
            "Whether the scenario alone contains enough data to populate the PBPK external-import "
            "path without additional PBPK execution outputs."
        ),
    )
    supported_pbpk_objects: list[str] = Field(
        default_factory=list,
        description="Published PBPK object families this scenario can prefill or support.",
    )
    missing_external_bundle_fields: list[str] = Field(
        default_factory=list,
        description="PBPK external-import fields still missing for a richer downstream handoff.",
    )
    checked_fields: list[str] = Field(
        default_factory=list,
        description="Fields explicitly checked during compatibility validation.",
    )
    issues: list[LimitationNote] = Field(
        default_factory=list,
        description="Compatibility issues or warnings.",
    )
    recommended_next_steps: list[str] = Field(
        default_factory=list,
        description="Concrete actions to strengthen the PBPK handoff.",
    )


class PbpkExternalImportPackage(StrictModel):
    schema_version: Literal["pbpkExternalImportPackage.v1"] = Field(
        default="pbpkExternalImportPackage.v1", alias="schemaVersion"
    )
    ingest_tool_name: Literal["ingest_external_pbpk_bundle"] = Field(
        default="ingest_external_pbpk_bundle", alias="ingestToolName"
    )
    bundle: PbpkExternalImportBundle
    request_payload: PbpkExternalImportRequest = Field(..., alias="requestPayload")
    tool_call: PbpkExternalImportToolCall = Field(..., alias="toolCall")
    toxclaw_module_params: ToxClawPbpkModuleParams = Field(..., alias="toxclawModuleParams")
    compatibility_report: PbpkCompatibilityReport = Field(..., alias="compatibilityReport")


class RunIntegratedExposureWorkflowInput(StrictModel):
    schema_version: Literal["runIntegratedExposureWorkflowInput.v1"] = (
        "runIntegratedExposureWorkflowInput.v1"
    )
    request: (
        ExposureScenarioRequest | InhalationScenarioRequest | InhalationTier1ScenarioRequest
    ) = Field(..., description="Scenario request to enrich, build, and optionally export.")
    comp_tox_record: CompToxChemicalRecord | None = Field(
        default=None,
        alias="compToxRecord",
        description="Optional normalized CompTox record to convert into product-use evidence.",
    )
    cons_expo_records: list[ConsExpoEvidenceRecord] = Field(
        default_factory=list,
        alias="consExpoRecords",
        description="Optional ConsExpo records to normalize into product-use evidence.",
    )
    sccs_records: list[SccsCosmeticsEvidenceRecord] = Field(
        default_factory=list,
        alias="sccsRecords",
        description="Optional SCCS cosmetics records to normalize into product-use evidence.",
    )
    sccs_opinion_records: list[SccsOpinionEvidenceRecord] = Field(
        default_factory=list,
        alias="sccsOpinionRecords",
        description="Optional SCCS opinion records to normalize into product-use evidence.",
    )
    cosing_records: list[CosIngIngredientRecord] = Field(
        default_factory=list,
        alias="cosingRecords",
        description="Optional CosIng ingredient records to normalize into product-use evidence.",
    )
    nanomaterial_records: list[NanoMaterialEvidenceRecord] = Field(
        default_factory=list,
        alias="nanomaterialRecords",
        description=(
            "Optional nanomaterial evidence records to normalize into product-use evidence."
        ),
    )
    synthetic_polymer_microparticle_records: list[SyntheticPolymerMicroparticleEvidenceRecord] = (
        Field(
            default_factory=list,
            alias="syntheticPolymerMicroparticleRecords",
            description=(
                "Optional synthetic polymer microparticle records to normalize into product-use "
                "evidence."
            ),
        )
    )
    evidence_records: list[ProductUseEvidenceRecord] = Field(
        default_factory=list,
        alias="evidenceRecords",
        description="Additional evidence records such as user uploads or dossiers.",
    )
    require_auto_apply_safe: bool = Field(
        default=False,
        alias="requireAutoApplySafe",
        description=(
            "When true, only evidence that is safe to auto-apply can modify the effective "
            "request. Otherwise, review-needed evidence can still be applied with traceable "
            "warnings."
        ),
    )
    continue_on_evidence_reject: bool = Field(
        default=True,
        alias="continueOnEvidenceReject",
        description=(
            "When true, build the scenario from the source request if all evidence is rejected."
        ),
    )
    export_pbpk_scenario_input: bool = Field(
        default=True,
        alias="exportPbpkScenarioInput",
        description="Whether to export the normalized PBPK scenario input object.",
    )
    export_pbpk_external_import_bundle: bool = Field(
        default=True,
        alias="exportPbpkExternalImportBundle",
        description="Whether to export the PBPK external-import bundle package.",
    )
    pbpk_regimen_name: str | None = Field(
        default=None,
        alias="pbpkRegimenName",
        description="Optional regimen label for the PBPK scenario-input export.",
    )
    pbpk_context_of_use: str = Field(
        default="screening-brief",
        alias="pbpkContextOfUse",
        description="Context label for the PBPK external-import bundle.",
    )
    pbpk_requested_output: str | None = Field(
        default=None,
        alias="pbpkRequestedOutput",
        description="Optional target PBPK output label for the external-import bundle.",
    )
    pbpk_scientific_purpose: str = Field(
        default="external exposure scenario translation for PBPK",
        alias="pbpkScientificPurpose",
        description="Scientific purpose text preserved in the PBPK external-import bundle.",
    )
    pbpk_decision_context: str = Field(
        default="upstream external exposure context only",
        alias="pbpkDecisionContext",
        description="Decision-context text preserved in the PBPK external-import bundle.",
    )


class IntegratedExposureWorkflowResult(StrictModel):
    schema_version: Literal["integratedExposureWorkflowResult.v1"] = (
        "integratedExposureWorkflowResult.v1"
    )
    chemical_id: str = Field(..., alias="chemicalId")
    source_request: (
        ExposureScenarioRequest | InhalationScenarioRequest | InhalationTier1ScenarioRequest
    ) = Field(
        ...,
        alias="sourceRequest",
    )
    effective_request: (
        ExposureScenarioRequest | InhalationScenarioRequest | InhalationTier1ScenarioRequest
    ) = Field(
        ...,
        alias="effectiveRequest",
    )
    evidence_strategy: Literal[
        "source_request_only",
        "reconciled_evidence_applied",
        "reconciled_evidence_applied_with_review",
        "evidence_rejected_source_request_retained",
    ] = Field(..., alias="evidenceStrategy")
    normalized_evidence_records: list[ProductUseEvidenceRecord] = Field(
        default_factory=list,
        alias="normalizedEvidenceRecords",
    )
    reconciliation_report: ProductUseEvidenceReconciliationReport | None = Field(
        default=None,
        alias="reconciliationReport",
    )
    selected_evidence_source_name: str | None = Field(
        default=None,
        alias="selectedEvidenceSourceName",
    )
    selected_evidence_source_kind: str | None = Field(
        default=None,
        alias="selectedEvidenceSourceKind",
    )
    manual_review_required: bool = Field(..., alias="manualReviewRequired")
    scenario: ExposureScenario
    pbpk_compatibility_report: PbpkCompatibilityReport = Field(
        ...,
        alias="pbpkCompatibilityReport",
    )
    pbpk_scenario_input: PbpkScenarioInput | None = Field(
        default=None,
        alias="pbpkScenarioInput",
    )
    pbpk_external_import_package: PbpkExternalImportPackage | None = Field(
        default=None,
        alias="pbpkExternalImportPackage",
    )
    workflow_notes: list[str] = Field(default_factory=list, alias="workflowNotes")
    quality_flags: list[QualityFlag] = Field(default_factory=list, alias="qualityFlags")
    limitations: list[LimitationNote] = Field(default_factory=list)
    provenance: ProvenanceBundle


def apply_comptox_enrichment(
    request: ExposureScenarioRequest,
    record: CompToxChemicalRecord,
) -> ExposureScenarioRequest:
    """Merge CompTox identity and discovery context into a scenario request."""

    enriched = apply_product_use_evidence(
        request,
        build_product_use_evidence_from_comptox(record),
    )
    overrides = dict(enriched.assumption_overrides)
    if record.casrn:
        overrides["comptox_casrn"] = record.casrn
    if record.evidence_sources:
        overrides["comptox_primary_evidence"] = record.evidence_sources[0]
    return enriched.model_copy(update={"assumption_overrides": overrides})


def build_product_use_evidence_from_comptox(
    record: CompToxChemicalRecord,
    *,
    region_scopes: list[str] | None = None,
    jurisdictions: list[str] | None = None,
    review_status: Literal["reviewed", "provisional", "unreviewed"] = "reviewed",
) -> ProductUseEvidenceRecord:
    """Map the compact CompTox enrichment record into the generic evidence contract."""

    return ProductUseEvidenceRecord(
        chemical_id=record.chemical_id,
        preferred_name=record.preferred_name,
        casrn=record.casrn,
        source_name="EPA CompTox",
        source_kind="comptox",
        review_status=review_status,
        product_use_categories=list(record.product_use_categories),
        region_scopes=list(region_scopes or []),
        jurisdictions=list(jurisdictions or ["US"]),
        physchem_summary=dict(record.physchem_summary),
        evidence_sources=list(record.evidence_sources),
        notes=[
            "Derived from the compact CompTox identity/use-context enrichment record.",
        ],
    )


def _normalize_tokens(values: list[str]) -> set[str]:
    return {value.strip().lower() for value in values if value and value.strip()}


def _normalize_product_group(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _normalize_product_subtype_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _map_consexpo_product_subtype(record: ConsExpoEvidenceRecord) -> str | None:
    subgroup = (record.product_subgroup or "").strip()
    if not subgroup:
        return None

    normalized_group = _normalize_product_group(record.product_group)
    normalized_subgroup = _normalize_product_subtype_token(subgroup)

    if normalized_group in {"pest_control_products", "pest_control"}:
        if (
            ("air" in normalized_subgroup and "space" in normalized_subgroup)
            or "airspace" in normalized_subgroup
            or "space_spray" in normalized_subgroup
            or "space_aerosol" in normalized_subgroup
        ):
            return "air_space_insecticide"
        if "crack" in normalized_subgroup and "crevice" in normalized_subgroup:
            return "crack_and_crevice_insecticide"
        if "spot" in normalized_subgroup or "targeted" in normalized_subgroup:
            return "targeted_spot_insecticide"
        if "trigger" in normalized_subgroup and (
            "indoor" in normalized_subgroup
            or "surface" in normalized_subgroup
            or "insect" in normalized_subgroup
        ):
            return "indoor_surface_insecticide"

    if (
        normalized_group in {"disinfecting_products", "disinfectants"}
        and "trigger" in normalized_subgroup
        and "surface" in normalized_subgroup
    ):
        return "surface_trigger_spray_disinfectant"

    return None


CONSEXPO_PRODUCT_GROUP_CATEGORY_MAP: dict[str, list[str]] = {
    "cosmetics": ["personal_care"],
    "cosmetic_products": ["personal_care"],
    "cleaning_products": ["household_cleaner"],
    "disinfecting_products": ["disinfectant", "household_cleaner", "biocide"],
    "disinfectants": ["disinfectant", "household_cleaner", "biocide"],
    "paint_products": ["paint_coating", "do_it_yourself"],
    "paints": ["paint_coating", "do_it_yourself"],
    "do_it_yourself_products": ["do_it_yourself"],
    "diy": ["do_it_yourself"],
    "pest_control_products": ["pest_control", "pesticide", "biocide"],
    "pest_control": ["pest_control", "pesticide", "biocide"],
}

SCCS_PRODUCT_TYPE_CATEGORY_MAP: dict[str, list[str]] = {
    "face_cream": ["personal_care"],
    "face_moisturizer": ["personal_care"],
    "body_lotion": ["personal_care"],
    "body_cream": ["personal_care"],
    "hand_cream": ["personal_care"],
    "deodorant_spray": ["personal_care"],
    "pump_spray_hair_product": ["personal_care"],
}


def _normalize_sccs_product_type(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def build_product_use_evidence_from_consexpo(
    record: ConsExpoEvidenceRecord,
) -> ProductUseEvidenceRecord:
    """Map a ConsExpo fact-sheet record into the generic product-use evidence contract."""

    normalized_group = _normalize_product_group(record.product_group)
    mapped_categories = list(
        CONSEXPO_PRODUCT_GROUP_CATEGORY_MAP.get(normalized_group, [normalized_group])
    )
    notes = list(record.notes)
    notes.append(
        "Mapped from ConsExpo product_group "
        f"`{record.product_group}` to internal categories {mapped_categories}."
    )
    if record.product_subgroup:
        notes.append(f"ConsExpo product_subgroup: {record.product_subgroup}.")
    mapped_subtype = _map_consexpo_product_subtype(record)
    if mapped_subtype:
        notes.append(f"Mapped ConsExpo product_subgroup to internal subtype `{mapped_subtype}`.")
    elif record.product_subgroup:
        notes.append(
            "No internal product_subtype mapping was registered for the ConsExpo subgroup; "
            "the subgroup label is preserved in product_name only."
        )
    if record.model_family:
        notes.append(f"ConsExpo model_family: {record.model_family}.")
    if record.supported_routes:
        notes.append(
            "ConsExpo supported routes: "
            + ", ".join(route.value for route in record.supported_routes)
            + "."
        )

    evidence_sources = list(record.evidence_sources)
    if not evidence_sources:
        evidence_sources = [f"ConsExpo:{record.fact_sheet_id}"]

    return ProductUseEvidenceRecord(
        chemical_id=record.chemical_id,
        preferred_name=record.preferred_name,
        casrn=record.casrn,
        source_name="RIVM ConsExpo",
        source_kind="consexpo",
        review_status="reviewed",
        source_record_id=record.fact_sheet_id,
        source_locator=record.fact_sheet_locator,
        product_name=record.product_subgroup,
        product_subtype=mapped_subtype,
        product_use_categories=mapped_categories,
        physical_forms=list(record.physical_forms),
        application_methods=list(record.application_methods),
        retention_types=list(record.retention_types),
        region_scopes=list(record.region_scopes),
        jurisdictions=list(record.jurisdictions),
        physchem_summary=dict(record.physchem_summary),
        evidence_sources=evidence_sources,
        notes=notes,
    )


def build_product_use_evidence_from_sccs(
    record: SccsCosmeticsEvidenceRecord,
) -> ProductUseEvidenceRecord:
    """Map an SCCS cosmetics guidance record into the generic product-use evidence contract."""

    normalized_type = _normalize_sccs_product_type(record.cosmetic_product_type)
    mapped_categories = list(SCCS_PRODUCT_TYPE_CATEGORY_MAP.get(normalized_type, ["personal_care"]))
    notes = list(record.notes)
    notes.append(
        "Mapped from SCCS cosmetics guidance product type "
        f"`{record.cosmetic_product_type}` to internal categories {mapped_categories}."
    )
    if record.product_family:
        notes.append(f"SCCS product_family: {record.product_family}.")
    if record.table_references:
        notes.append("SCCS table references: " + ", ".join(record.table_references) + ".")
    if record.supported_routes:
        notes.append(
            "SCCS supported routes: "
            + ", ".join(route.value for route in record.supported_routes)
            + "."
        )

    evidence_sources = list(record.evidence_sources)
    if not evidence_sources:
        evidence_sources = [f"SCCS:{record.guidance_id}"]

    product_use_profile_overrides = _coerce_supported_profile_overrides(
        record.product_use_profile_overrides,
        _PRODUCT_USE_OVERRIDE_FIELDS,
    )
    population_profile_overrides = _coerce_supported_profile_overrides(
        record.population_profile_overrides,
        _POPULATION_OVERRIDE_FIELDS,
    )

    return ProductUseEvidenceRecord(
        chemical_id=record.chemical_id,
        preferred_name=record.preferred_name,
        casrn=record.casrn,
        source_name="EU SCCS",
        source_kind="sccs",
        review_status="reviewed",
        source_record_id=record.guidance_id,
        source_locator=record.guidance_locator,
        product_name=record.cosmetic_product_type,
        product_subtype=normalized_type or None,
        product_use_categories=mapped_categories,
        physical_forms=list(record.physical_forms),
        application_methods=list(record.application_methods),
        retention_types=list(record.retention_types),
        region_scopes=list(record.region_scopes),
        jurisdictions=list(record.jurisdictions),
        productUseProfileOverrides=product_use_profile_overrides,
        populationProfileOverrides=population_profile_overrides,
        evidence_sources=evidence_sources,
        notes=notes,
    )


def build_product_use_evidence_from_sccs_opinion(
    record: SccsOpinionEvidenceRecord,
) -> ProductUseEvidenceRecord:
    """Map an SCCS opinion record into the generic product-use evidence contract."""

    notes = list(record.notes)
    notes.append(f"SCCS opinion title: {record.opinion_title}.")
    if record.cosmetic_product_types:
        notes.append(
            "SCCS opinion cosmetic product types: " + ", ".join(record.cosmetic_product_types) + "."
        )
    evidence_sources = list(record.evidence_sources) or [f"SCCS:{record.opinion_id}"]

    product_name = record.cosmetic_product_types[0] if record.cosmetic_product_types else None
    product_subtype = (
        _normalize_sccs_product_type(product_name) if isinstance(product_name, str) else None
    )

    return ProductUseEvidenceRecord(
        chemical_id=record.chemical_id,
        preferred_name=record.preferred_name,
        casrn=record.casrn,
        source_name="EU SCCS Opinion",
        source_kind="sccs",
        review_status="reviewed",
        source_record_id=record.opinion_id,
        source_locator=record.opinion_locator,
        product_name=product_name,
        product_subtype=product_subtype,
        product_use_categories=["personal_care"],
        physical_forms=list(record.physical_forms),
        application_methods=list(record.application_methods),
        retention_types=list(record.retention_types),
        region_scopes=list(record.region_scopes),
        jurisdictions=list(record.jurisdictions),
        particleMaterialContext=record.particle_material_context,
        evidence_sources=evidence_sources,
        notes=notes,
    )


def build_product_use_evidence_from_cosing(
    record: CosIngIngredientRecord,
) -> ProductUseEvidenceRecord:
    """Map a CosIng ingredient record into the generic product-use evidence contract."""

    notes = list(record.notes)
    if record.inci_name:
        notes.append(f"CosIng INCI name: {record.inci_name}.")
    if record.functions:
        notes.append("CosIng functions: " + ", ".join(record.functions) + ".")
    if record.annex_references:
        notes.append("CosIng annex references: " + ", ".join(record.annex_references) + ".")
    if record.nanomaterial_flag is not None:
        notes.append(f"CosIng nanomaterial flag: {record.nanomaterial_flag}.")
    evidence_sources = list(record.evidence_sources) or [
        f"CosIng:{record.inci_name or record.chemical_id}"
    ]

    return ProductUseEvidenceRecord(
        chemical_id=record.chemical_id,
        preferred_name=record.preferred_name or record.inci_name,
        casrn=record.casrn,
        source_name="EU CosIng",
        source_kind="cosing",
        review_status="reviewed",
        source_record_id=record.inci_name or record.chemical_id,
        source_locator=record.cosing_locator,
        product_use_categories=["personal_care"],
        region_scopes=list(record.region_scopes),
        jurisdictions=list(record.jurisdictions),
        particleMaterialContext=record.particle_material_context,
        evidence_sources=evidence_sources,
        notes=notes,
    )


def build_product_use_evidence_from_nanomaterial(
    record: NanoMaterialEvidenceRecord,
) -> ProductUseEvidenceRecord:
    """Map a nanomaterial guidance record into the generic product-use evidence contract."""

    notes = list(record.notes)
    notes.append(f"Nanomaterial source program: {record.source_program}.")
    if record.cosmetic_product_types:
        notes.append(
            "Nanomaterial cosmetic product types: " + ", ".join(record.cosmetic_product_types) + "."
        )
    evidence_sources = list(record.evidence_sources) or [
        f"{record.source_program}:{record.source_record_id}"
    ]

    product_name = record.cosmetic_product_types[0] if record.cosmetic_product_types else None
    product_subtype = (
        _normalize_sccs_product_type(product_name) if isinstance(product_name, str) else None
    )

    return ProductUseEvidenceRecord(
        chemical_id=record.chemical_id,
        preferred_name=record.preferred_name,
        casrn=record.casrn,
        source_name="EU Nanomaterial Guidance",
        source_kind="nanomaterial_guidance",
        review_status="reviewed",
        source_record_id=record.source_record_id,
        source_locator=record.source_locator,
        product_name=product_name,
        product_subtype=product_subtype,
        product_use_categories=["personal_care"],
        physical_forms=list(record.physical_forms),
        application_methods=list(record.application_methods),
        retention_types=list(record.retention_types),
        region_scopes=list(record.region_scopes),
        jurisdictions=list(record.jurisdictions),
        particleMaterialContext=record.particle_material_context,
        evidence_sources=evidence_sources,
        notes=notes,
    )


def build_product_use_evidence_from_synthetic_polymer_microparticle(
    record: SyntheticPolymerMicroparticleEvidenceRecord,
) -> ProductUseEvidenceRecord:
    """Map a synthetic polymer microparticle record into the generic evidence contract."""

    notes = list(record.notes)
    notes.append(f"Synthetic polymer microparticle scope: {record.restriction_scope}.")
    evidence_sources = list(record.evidence_sources) or [f"ECHA:{record.source_record_id}"]

    return ProductUseEvidenceRecord(
        chemical_id=record.chemical_id,
        preferred_name=record.preferred_name,
        casrn=record.casrn,
        source_name="ECHA Microplastics",
        source_kind="microplastics_regulatory",
        review_status="reviewed",
        source_record_id=record.source_record_id,
        source_locator=record.source_locator,
        product_use_categories=list(record.product_use_categories),
        physical_forms=list(record.physical_forms),
        application_methods=list(record.application_methods),
        retention_types=list(record.retention_types),
        region_scopes=list(record.region_scopes),
        jurisdictions=list(record.jurisdictions),
        particleMaterialContext=record.particle_material_context,
        evidence_sources=evidence_sources,
        notes=notes,
    )


def _coerce_base_request(request: ExposureScenarioRequest) -> ExposureScenarioRequest:
    """Drop request-subclass-only fields so enrichment outputs stay on the base contract."""

    payload = request.model_dump(
        mode="json",
        by_alias=True,
        include=set(ExposureScenarioRequest.model_fields),
    )
    payload["schema_version"] = "exposureScenarioRequest.v1"
    return ExposureScenarioRequest.model_validate(payload)


def _region_match_score(request_region: str, evidence: ProductUseEvidenceRecord) -> int:
    request_region_token = request_region.strip().lower()
    evidence_regions = _normalize_tokens(evidence.region_scopes)
    evidence_jurisdictions = _normalize_tokens(evidence.jurisdictions)
    if request_region_token in evidence_regions:
        return 3
    if "global" in evidence_regions:
        return 2
    if request_region_token in evidence_jurisdictions:
        return 1
    return 0


def _review_status_rank(review_status: Literal["reviewed", "provisional", "unreviewed"]) -> int:
    return {
        "reviewed": 2,
        "provisional": 1,
        "unreviewed": 0,
    }[review_status]


def _source_kind_rank(
    source_kind: Literal[
        "comptox",
        "consexpo",
        "sccs",
        "cosing",
        "nanomaterial_guidance",
        "microplastics_regulatory",
        "regulatory_dossier",
        "literature_pack",
        "user_upload",
        "other",
    ],
) -> int:
    return {
        "regulatory_dossier": 4,
        "sccs": 4,
        "nanomaterial_guidance": 4,
        "consexpo": 3,
        "microplastics_regulatory": 3,
        "cosing": 2,
        "literature_pack": 2,
        "user_upload": 2,
        "comptox": 1,
        "other": 0,
    }[source_kind]


def _fit_rank_key(
    request: ExposureScenarioRequest,
    evidence: ProductUseEvidenceRecord,
    report: ProductUseEvidenceFitReport,
) -> tuple[int, int, int, int, int, int, int, int]:
    return (
        int(report.compatible),
        _region_match_score(request.population_profile.region, evidence),
        _review_status_rank(evidence.review_status),
        _source_kind_rank(evidence.source_kind),
        int(report.auto_apply_safe),
        len(report.matched_fields),
        -len(report.warnings),
        len(evidence.evidence_sources),
    )


def _normalized_conflict_value(values: list[str]) -> str | None:
    normalized = sorted(_normalize_tokens(values))
    if not normalized:
        return None
    return ",".join(normalized)


_PRODUCT_USE_OVERRIDE_FIELDS = set(ProductUseProfile.model_fields) - {"schema_version"}
_POPULATION_OVERRIDE_FIELDS = set(PopulationProfile.model_fields) - {"schema_version"}


def _validated_product_use_profile_update(
    profile: ProductUseProfile,
    updates: dict[str, ScalarValue],
) -> ProductUseProfile:
    payload = profile.model_dump(mode="json", by_alias=False)
    payload.update(updates)
    return ProductUseProfile.model_validate(payload)


def _validated_population_profile_update(
    profile: PopulationProfile,
    updates: dict[str, ScalarValue],
) -> PopulationProfile:
    payload = profile.model_dump(mode="json", by_alias=False)
    payload.update(updates)
    return PopulationProfile.model_validate(payload)


def _normalized_scalar_conflict_value(value: ScalarValue) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip().lower()
    return json.dumps(value, sort_keys=True)


def _coerce_supported_profile_overrides(
    overrides: dict[str, ScalarValue],
    supported_fields: set[str],
) -> dict[str, ScalarValue]:
    return {key: value for key, value in overrides.items() if key in supported_fields}


def _build_product_use_conflicts(
    compatible_pairs: list[tuple[ProductUseEvidenceRecord, ProductUseEvidenceFitReport]],
) -> list[str]:
    conflicts: list[str] = []
    if len(compatible_pairs) < 2:
        return conflicts

    category_values = {
        value
        for evidence, _ in compatible_pairs
        if (value := _normalized_conflict_value(evidence.product_use_categories)) is not None
    }
    if len(category_values) > 1:
        conflicts.append(
            "Compatible evidence sources disagree on product_use_categories: "
            + "; ".join(
                f"{evidence.source_name}={_normalized_conflict_value(evidence.product_use_categories)}"
                for evidence, _ in compatible_pairs
                if evidence.product_use_categories
            )
        )

    product_names = {
        evidence.product_name.strip(): evidence.source_name
        for evidence, _ in compatible_pairs
        if evidence.product_name and evidence.product_name.strip()
    }
    if len(product_names) > 1:
        conflicts.append(
            "Compatible evidence sources disagree on product_name: "
            + "; ".join(
                f"{source_name}={product_name}"
                for product_name, source_name in sorted(product_names.items())
            )
        )
    product_subtypes = {
        evidence.product_subtype.strip(): evidence.source_name
        for evidence, _ in compatible_pairs
        if evidence.product_subtype and evidence.product_subtype.strip()
    }
    if len(product_subtypes) > 1:
        conflicts.append(
            "Compatible evidence sources disagree on product_subtype: "
            + "; ".join(
                f"{source_name}={product_subtype}"
                for product_subtype, source_name in sorted(product_subtypes.items())
            )
        )

    density_values = {
        float(density): evidence.source_name
        for evidence, _ in compatible_pairs
        if isinstance(
            (density := evidence.physchem_summary.get("density_g_per_ml")),
            int | float,
        )
        and not isinstance(density, bool)
    }
    if len(density_values) > 1:
        conflicts.append(
            "Compatible evidence sources disagree on density_g_per_ml: "
            + "; ".join(
                f"{source_name}={density:g}"
                for density, source_name in sorted(density_values.items())
            )
        )

    particle_context_values = {
        json.dumps(
            evidence.particle_material_context.model_dump(mode="json", by_alias=True),
            sort_keys=True,
        ): evidence.source_name
        for evidence, _ in compatible_pairs
        if evidence.particle_material_context is not None
    }
    if len(particle_context_values) > 1:
        conflicts.append(
            "Compatible evidence sources disagree on particle_material_context: "
            + "; ".join(
                f"{source_name}={value}"
                for value, source_name in sorted(particle_context_values.items())
            )
        )

    for field_name in sorted(_PRODUCT_USE_OVERRIDE_FIELDS):
        override_values = {
            normalized: evidence.source_name
            for evidence, _ in compatible_pairs
            if field_name in evidence.product_use_profile_overrides
            and (
                normalized := _normalized_scalar_conflict_value(
                    evidence.product_use_profile_overrides[field_name]
                )
            )
            is not None
        }
        if len(override_values) > 1:
            conflicts.append(
                "Compatible evidence sources disagree on "
                f"product_use_profile.{field_name}: "
                + "; ".join(
                    f"{source_name}={value}"
                    for value, source_name in sorted(override_values.items())
                )
            )

    for field_name in sorted(_POPULATION_OVERRIDE_FIELDS):
        override_values = {
            normalized: evidence.source_name
            for evidence, _ in compatible_pairs
            if field_name in evidence.population_profile_overrides
            and (
                normalized := _normalized_scalar_conflict_value(
                    evidence.population_profile_overrides[field_name]
                )
            )
            is not None
        }
        if len(override_values) > 1:
            conflicts.append(
                "Compatible evidence sources disagree on "
                f"population_profile.{field_name}: "
                + "; ".join(
                    f"{source_name}={value}"
                    for value, source_name in sorted(override_values.items())
                )
            )

    return conflicts


def assess_product_use_evidence_fit(
    request: ExposureScenarioRequest,
    evidence: ProductUseEvidenceRecord,
) -> ProductUseEvidenceFitReport:
    """Assess whether external product-use evidence fits the current request."""

    matched_fields: list[str] = []
    suggested_updates: list[str] = []
    warnings: list[str] = []
    blocking_issues: list[str] = []

    if request.chemical_id != evidence.chemical_id:
        blocking_issues.append(
            "chemical_id does not match between the request and the product-use evidence record."
        )

    updated_product_profile = request.product_use_profile
    updated_population_profile = request.population_profile
    updated_request_name = request.chemical_name

    request_region = request.population_profile.region
    request_region_token = request_region.strip().lower()
    evidence_regions = _normalize_tokens(evidence.region_scopes)
    evidence_jurisdictions = _normalize_tokens(evidence.jurisdictions)

    if evidence_regions:
        if request_region_token in evidence_regions or "global" in evidence_regions:
            matched_fields.append("region")
        else:
            warnings.append(
                "Evidence region_scopes do not include the request region "
                f"`{request.population_profile.region}`."
            )
    elif evidence_jurisdictions and request_region_token not in evidence_jurisdictions:
        warnings.append(
            "Evidence jurisdictions "
            f"{sorted(evidence.jurisdictions)} may not match request region "
            f"`{request.population_profile.region}`."
        )

    evidence_categories = list(evidence.product_use_categories)
    if evidence_categories:
        if updated_product_profile.product_category in evidence_categories:
            matched_fields.append("product_category")
        else:
            updated_product_profile = updated_product_profile.model_copy(
                update={"product_category": evidence_categories[0]}
            )
            suggested_updates.append("product_use_profile.product_category")
            warnings.append(
                "Request product_category "
                f"`{request.product_use_profile.product_category}` is not listed in the "
                f"evidence categories {evidence.product_use_categories}; the first evidence "
                "category is suggested instead."
            )

    evidence_forms = _normalize_tokens(evidence.physical_forms)
    if evidence_forms:
        if updated_product_profile.physical_form.lower() in evidence_forms:
            matched_fields.append("physical_form")
        else:
            blocking_issues.append(
                "Request physical_form "
                f"`{request.product_use_profile.physical_form}` is outside the evidence-backed "
                f"forms {sorted(evidence.physical_forms)}."
            )

    evidence_methods = _normalize_tokens(evidence.application_methods)
    if evidence_methods:
        if updated_product_profile.application_method.lower() in evidence_methods:
            matched_fields.append("application_method")
        else:
            blocking_issues.append(
                "Request application_method "
                f"`{request.product_use_profile.application_method}` is outside the "
                f"evidence-backed methods {sorted(evidence.application_methods)}."
            )

    evidence_retention_types = _normalize_tokens(evidence.retention_types)
    if evidence_retention_types:
        if updated_product_profile.retention_type.lower() in evidence_retention_types:
            matched_fields.append("retention_type")
        else:
            warnings.append(
                "Request retention_type "
                f"`{request.product_use_profile.retention_type}` is not listed in the "
                f"evidence-backed retention types {sorted(evidence.retention_types)}."
            )

    if evidence.product_subtype:
        request_subtype = (updated_product_profile.product_subtype or "").strip().lower()
        evidence_subtype = evidence.product_subtype.strip().lower()
        if request_subtype:
            if request_subtype == evidence_subtype:
                matched_fields.append("product_subtype")
            else:
                blocking_issues.append(
                    "Request product_subtype "
                    f"`{request.product_use_profile.product_subtype}` is outside the "
                    f"evidence-backed subtype `{evidence.product_subtype}`."
                )
        else:
            updated_product_profile = updated_product_profile.model_copy(
                update={"product_subtype": evidence.product_subtype}
            )
            suggested_updates.append("product_use_profile.product_subtype")

    if evidence.product_name and not updated_product_profile.product_name:
        updated_product_profile = updated_product_profile.model_copy(
            update={"product_name": evidence.product_name}
        )
        suggested_updates.append("product_use_profile.product_name")

    evidence_density = evidence.physchem_summary.get("density_g_per_ml")
    if isinstance(evidence_density, int | float) and not isinstance(evidence_density, bool):
        resolved_density = float(evidence_density)
        if updated_product_profile.density_g_per_ml is None:
            updated_product_profile = updated_product_profile.model_copy(
                update={"density_g_per_ml": resolved_density}
            )
            suggested_updates.append("product_use_profile.density_g_per_ml")
        elif abs(updated_product_profile.density_g_per_ml - resolved_density) < 1e-12:
            matched_fields.append("density_g_per_ml")
        else:
            warnings.append(
                "Request density_g_per_ml "
                f"`{updated_product_profile.density_g_per_ml}` differs from the "
                f"evidence-backed value `{resolved_density}`; keeping the explicit request "
                "value."
            )

    if evidence.particle_material_context is not None:
        current_particle_context = updated_product_profile.particle_material_context
        if current_particle_context is None:
            updated_product_profile = updated_product_profile.model_copy(
                update={"particle_material_context": evidence.particle_material_context}
            )
            suggested_updates.append("product_use_profile.particle_material_context")
        elif current_particle_context == evidence.particle_material_context:
            matched_fields.append("particle_material_context")
        else:
            warnings.append(
                "Request particle_material_context differs from the evidence-backed context; "
                "keeping the explicit request value."
            )

    if evidence.preferred_name and not updated_request_name:
        updated_request_name = evidence.preferred_name
        suggested_updates.append("chemical_name")

    for field_name, override_value in sorted(evidence.product_use_profile_overrides.items()):
        current_value = getattr(updated_product_profile, field_name)
        if current_value == override_value:
            matched_fields.append(f"product_use_profile.{field_name}")
            continue
        updated_product_profile = _validated_product_use_profile_update(
            updated_product_profile,
            {field_name: override_value},
        )
        suggested_updates.append(f"product_use_profile.{field_name}")
        if current_value is not None:
            warnings.append(
                "Reviewed evidence suggests product_use_profile."
                f"{field_name}={override_value!r} instead of the current request value "
                f"{current_value!r}."
            )

    for field_name, override_value in sorted(evidence.population_profile_overrides.items()):
        current_value = getattr(updated_population_profile, field_name)
        if current_value == override_value:
            matched_fields.append(f"population_profile.{field_name}")
            continue
        updated_population_profile = _validated_population_profile_update(
            updated_population_profile,
            {field_name: override_value},
        )
        suggested_updates.append(f"population_profile.{field_name}")
        if current_value is not None:
            warnings.append(
                "Reviewed evidence suggests population_profile."
                f"{field_name}={override_value!r} instead of the current request value "
                f"{current_value!r}."
            )

    overrides = dict(request.assumption_overrides)
    overrides["external_product_use_source_name"] = evidence.source_name
    overrides["external_product_use_source_kind"] = evidence.source_kind
    overrides["external_product_use_review_status"] = evidence.review_status
    suggested_updates.append("assumption_overrides.external_product_use_source_name")
    if evidence.source_record_id:
        overrides["external_product_use_source_record_id"] = evidence.source_record_id
    if evidence.source_locator:
        overrides["external_product_use_source_locator"] = evidence.source_locator
    if evidence.casrn:
        overrides["external_product_use_casrn"] = evidence.casrn
    if evidence.evidence_sources:
        overrides["external_product_use_primary_evidence"] = evidence.evidence_sources[0]
    if evidence.region_scopes:
        overrides["external_product_use_region_scopes"] = ",".join(evidence.region_scopes)
    if evidence.jurisdictions:
        overrides["external_product_use_jurisdictions"] = ",".join(evidence.jurisdictions)
    if evidence.product_use_categories:
        overrides["external_product_use_categories"] = ",".join(evidence.product_use_categories)
    if evidence.product_subtype:
        overrides["external_product_use_subtype"] = evidence.product_subtype
    for key, value in sorted(evidence.physchem_summary.items()):
        overrides[f"external_product_use_physchem_{key}"] = value
    if evidence.particle_material_context is not None:
        particle_payload = evidence.particle_material_context.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
        )
        for key, value in sorted(particle_payload.items()):
            if isinstance(value, (str, float, int, bool)):
                overrides[f"external_product_use_particle_material_context_{key}"] = value
    for key, value in sorted(evidence.product_use_profile_overrides.items()):
        overrides[f"external_product_use_override_product_{key}"] = value
    for key, value in sorted(evidence.population_profile_overrides.items()):
        overrides[f"external_product_use_override_population_{key}"] = value

    suggested_request = _coerce_base_request(
        request.model_copy(
            update={
                "chemical_name": updated_request_name,
                "product_use_profile": updated_product_profile,
                "population_profile": updated_population_profile,
                "assumption_overrides": overrides,
            }
        )
    )

    compatible = not blocking_issues
    auto_apply_safe = compatible and not warnings
    if blocking_issues:
        recommendation: Literal["accept", "accept_with_review", "manual_review", "reject"] = (
            "reject"
        )
    elif warnings:
        recommendation = "accept_with_review"
    elif suggested_updates:
        recommendation = "accept"
    else:
        recommendation = "accept"

    return ProductUseEvidenceFitReport(
        chemical_id=request.chemical_id,
        evidence_source_name=evidence.source_name,
        evidence_source_kind=evidence.source_kind,
        request_region=request.population_profile.region,
        compatible=compatible,
        auto_apply_safe=auto_apply_safe,
        recommendation=recommendation,
        matched_fields=matched_fields,
        suggested_updates=sorted(set(suggested_updates)),
        warnings=warnings,
        blocking_issues=blocking_issues,
        suggested_request=suggested_request,
    )


def apply_product_use_evidence(
    request: ExposureScenarioRequest,
    evidence: ProductUseEvidenceRecord,
    *,
    require_auto_apply_safe: bool = False,
) -> ExposureScenarioRequest:
    """Apply generic product-use evidence to a request when the fit is acceptable."""

    report = assess_product_use_evidence_fit(request, evidence)
    ensure(
        report.compatible,
        "product_use_evidence_incompatible",
        "External product-use evidence is not compatible with the current request.",
        suggestion="Review the blocking issues and revise the request or evidence record.",
        blocking_issues=report.blocking_issues,
        warnings=report.warnings,
        evidence_source_name=evidence.source_name,
    )
    if require_auto_apply_safe:
        ensure(
            report.auto_apply_safe,
            "product_use_evidence_requires_review",
            "External product-use evidence requires human review before auto-application.",
            suggestion="Review the warnings or call the fit-assessment tool before applying.",
            warnings=report.warnings,
            evidence_source_name=evidence.source_name,
        )
    return report.suggested_request


def _assess_model_compatibility(
    request: ExposureScenarioRequest,
    evidence: ProductUseEvidenceRecord,
) -> tuple[str, list[str]]:
    """Assess whether the physics/model assumed by the evidence source matches the request.

    Returns a compatibility level ("HIGH", "MEDIUM", "LOW", "BLOCKING") and a list of
    specific concerns.
    """
    concerns: list[str] = []
    source_kind = evidence.source_kind
    route = request.route

    # Sources that provide no quantitative exposure model should not drive dose estimates
    if source_kind in {"cosing", "nanomaterial_guidance", "microplastics_regulatory"}:
        if route in {Route.DERMAL, Route.ORAL, Route.INHALATION}:
            concerns.append(
                f"{evidence.source_name} provides identity/context data, not a quantitative "
                f"exposure model. Applying its overrides to a {route.value} dose estimate "
                "may silently substitute context for physics."
            )
        return ("LOW", concerns) if concerns else ("HIGH", concerns)

    # ConsExpo uses well-mixed room models; mismatches with spatial inhalation models
    if (
        source_kind == "consexpo"
        and route == Route.INHALATION
        and request.scenario_class == ScenarioClass.INHALATION
    ):
        concerns.append(
            "ConsExpo evidence assumes well-mixed room inhalation physics, but the "
            "request uses the direct inhalation scenario class. Near-field/far-field "
            "or source-geometry terms may be inconsistent."
        )
        return "LOW", concerns

    # SCCS is primarily dermal/oral guidance
    if source_kind in {"sccs", "sccs_opinion"} and route == Route.INHALATION:
        concerns.append(
            "SCCS evidence is oriented toward dermal and oral cosmetics guidance. "
            "Inhalation-specific parameters (airborne fraction, room volume, deposition) "
            "are outside its scope."
        )
        return "LOW", concerns

    if source_kind in {"sccs", "sccs_opinion"} and route == Route.DERMAL:
        app_method = request.product_use_profile.application_method
        if app_method not in {"hand_application", "direct_application", "rinse_off", "leave_on"}:
            concerns.append(
                f"SCCS assumptions are strongest for standard cosmetic application methods. "
                f"The request uses '{app_method}', which may not align with SCCS defaults."
            )
            return "MEDIUM", concerns

    return "HIGH", concerns


def reconcile_product_use_evidence(
    request: ExposureScenarioRequest,
    evidence_records: list[ProductUseEvidenceRecord],
    *,
    require_auto_apply_safe: bool = False,
) -> ProductUseEvidenceReconciliationReport:
    """Reconcile multiple evidence records into one merged request preview."""

    ensure(
        bool(evidence_records),
        "product_use_evidence_missing",
        "At least one product-use evidence record is required for reconciliation.",
    )

    fit_pairs = [
        (evidence, assess_product_use_evidence_fit(request, evidence))
        for evidence in evidence_records
    ]
    compatible_pairs = [(evidence, report) for evidence, report in fit_pairs if report.compatible]
    considered_sources = [evidence.source_name for evidence, _ in fit_pairs]
    compatible_sources = [evidence.source_name for evidence, _ in compatible_pairs]

    if not compatible_pairs:
        return ProductUseEvidenceReconciliationReport(
            chemical_id=request.chemical_id,
            request_region=request.population_profile.region,
            consideredSources=considered_sources,
            compatibleSources=[],
            recommendedSourceName=None,
            recommendedSourceKind=None,
            recommendation="reject",
            manualReviewRequired=True,
            conflicts=[],
            rationale=[
                "No supplied evidence record was compatible with the current request.",
            ],
            fieldSources={},
            fitReports=[report for _, report in fit_pairs],
            mergedRequest=None,
        )

    ranked_pairs = sorted(
        compatible_pairs,
        key=lambda pair: _fit_rank_key(request, pair[0], pair[1]),
        reverse=True,
    )
    primary_evidence, primary_report = ranked_pairs[0]
    merged_request = primary_report.suggested_request
    updated_product_profile = merged_request.product_use_profile
    updated_population_profile = merged_request.population_profile
    updated_request_name = merged_request.chemical_name
    field_sources: dict[str, str] = {}

    if updated_request_name != request.chemical_name and updated_request_name is not None:
        field_sources["chemical_name"] = primary_evidence.source_name
    if updated_product_profile.product_category != request.product_use_profile.product_category:
        field_sources["product_use_profile.product_category"] = primary_evidence.source_name
    if (
        updated_product_profile.product_subtype != request.product_use_profile.product_subtype
        and updated_product_profile.product_subtype is not None
    ):
        field_sources["product_use_profile.product_subtype"] = primary_evidence.source_name
    if (
        updated_product_profile.product_name != request.product_use_profile.product_name
        and updated_product_profile.product_name is not None
    ):
        field_sources["product_use_profile.product_name"] = primary_evidence.source_name
    if (
        request.product_use_profile.density_g_per_ml is None
        and updated_product_profile.density_g_per_ml is not None
    ):
        field_sources["product_use_profile.density_g_per_ml"] = primary_evidence.source_name
    if (
        request.product_use_profile.particle_material_context is None
        and updated_product_profile.particle_material_context is not None
    ):
        field_sources["product_use_profile.particle_material_context"] = (
            primary_evidence.source_name
        )
    for field_name, override_value in sorted(
        primary_evidence.product_use_profile_overrides.items()
    ):
        if getattr(request.product_use_profile, field_name) != override_value:
            field_sources[f"product_use_profile.{field_name}"] = primary_evidence.source_name
    for field_name, override_value in sorted(primary_evidence.population_profile_overrides.items()):
        if getattr(request.population_profile, field_name) != override_value:
            field_sources[f"population_profile.{field_name}"] = primary_evidence.source_name

    secondary_sources: list[str] = []
    for evidence, _report in ranked_pairs[1:]:
        contributed = False
        if updated_request_name is None and evidence.preferred_name:
            updated_request_name = evidence.preferred_name
            field_sources["chemical_name"] = evidence.source_name
            contributed = True
        if updated_product_profile.product_subtype is None and evidence.product_subtype:
            updated_product_profile = updated_product_profile.model_copy(
                update={"product_subtype": evidence.product_subtype}
            )
            field_sources["product_use_profile.product_subtype"] = evidence.source_name
            contributed = True
        if updated_product_profile.product_name is None and evidence.product_name:
            updated_product_profile = updated_product_profile.model_copy(
                update={"product_name": evidence.product_name}
            )
            field_sources["product_use_profile.product_name"] = evidence.source_name
            contributed = True
        evidence_density = evidence.physchem_summary.get("density_g_per_ml")
        if (
            updated_product_profile.density_g_per_ml is None
            and isinstance(evidence_density, int | float)
            and not isinstance(evidence_density, bool)
        ):
            updated_product_profile = updated_product_profile.model_copy(
                update={"density_g_per_ml": float(evidence_density)}
            )
            field_sources["product_use_profile.density_g_per_ml"] = evidence.source_name
            contributed = True
        if (
            updated_product_profile.particle_material_context is None
            and evidence.particle_material_context is not None
        ):
            updated_product_profile = updated_product_profile.model_copy(
                update={"particle_material_context": evidence.particle_material_context}
            )
            field_sources["product_use_profile.particle_material_context"] = evidence.source_name
            contributed = True
        for field_name, override_value in sorted(evidence.product_use_profile_overrides.items()):
            if getattr(updated_product_profile, field_name) is None:
                updated_product_profile = _validated_product_use_profile_update(
                    updated_product_profile,
                    {field_name: override_value},
                )
                field_sources[f"product_use_profile.{field_name}"] = evidence.source_name
                contributed = True
        for field_name, override_value in sorted(evidence.population_profile_overrides.items()):
            if getattr(updated_population_profile, field_name) is None:
                updated_population_profile = _validated_population_profile_update(
                    updated_population_profile,
                    {field_name: override_value},
                )
                field_sources[f"population_profile.{field_name}"] = evidence.source_name
                contributed = True
        if contributed:
            secondary_sources.append(evidence.source_name)

    overrides = dict(merged_request.assumption_overrides)
    overrides["external_product_use_primary_source_name"] = primary_evidence.source_name
    overrides["external_product_use_considered_sources"] = ",".join(considered_sources)
    overrides["external_product_use_compatible_sources"] = ",".join(compatible_sources)
    if secondary_sources:
        overrides["external_product_use_secondary_sources"] = ",".join(secondary_sources)
    for field_name, source_name in sorted(field_sources.items()):
        overrides[f"external_product_use_field_source_{field_name.replace('.', '_')}"] = source_name

    merged_request = _coerce_base_request(
        merged_request.model_copy(
            update={
                "chemical_name": updated_request_name,
                "product_use_profile": updated_product_profile,
                "population_profile": updated_population_profile,
                "assumption_overrides": overrides,
            }
        )
    )

    conflicts = _build_product_use_conflicts(compatible_pairs)

    # Model-compatibility guard against silent semantic mismatches
    compatibility_level, compatibility_concerns = _assess_model_compatibility(
        request, primary_evidence
    )
    if compatibility_level in {"LOW", "BLOCKING"}:
        manual_review_required = True
    else:
        manual_review_required = (not primary_report.auto_apply_safe) or bool(conflicts)

    if require_auto_apply_safe and manual_review_required:
        recommendation: Literal["apply", "apply_with_review", "manual_review", "reject"] = (
            "manual_review"
        )
    elif manual_review_required:
        recommendation = "apply_with_review"
    else:
        recommendation = "apply"

    rationale = [
        f"Selected `{primary_evidence.source_name}` as the primary evidence source.",
    ]
    if _region_match_score(request.population_profile.region, primary_evidence):
        rationale.append("Primary source matches the request region or jurisdiction context.")
    if primary_evidence.review_status == "reviewed":
        rationale.append("Primary source is marked as reviewed.")
    if secondary_sources:
        rationale.append("Secondary compatible sources only filled missing additive fields.")
    if compatibility_concerns:
        rationale.append(
            f"Model-compatibility assessment for {primary_evidence.source_name} "
            f"is `{compatibility_level}`."
        )
        rationale.extend(compatibility_concerns)
    else:
        rationale.append(
            "Model-compatibility assessment found no obvious physics mismatch "
            "between the primary evidence source and the request."
        )

    return ProductUseEvidenceReconciliationReport(
        chemical_id=request.chemical_id,
        request_region=request.population_profile.region,
        consideredSources=considered_sources,
        compatibleSources=compatible_sources,
        recommendedSourceName=primary_evidence.source_name,
        recommendedSourceKind=primary_evidence.source_kind,
        recommendation=recommendation,
        manualReviewRequired=manual_review_required,
        conflicts=conflicts,
        rationale=rationale,
        fieldSources=field_sources,
        fitReports=[report for _, report in fit_pairs],
        mergedRequest=merged_request,
    )


def build_toxclaw_evidence_envelope(
    payload: ExposureScenario | AggregateExposureSummary | ScenarioComparisonRecord,
    context_of_use: str,
) -> ToxClawEvidenceEnvelope:
    """Wrap exposure outputs in a ToxClaw-friendly evidence envelope."""

    if isinstance(payload, ExposureScenario):
        summary = (
            f"{payload.route.value} {payload.scenario_class.value} scenario "
            f"with external dose {payload.external_dose.value} {payload.external_dose.unit.value}"
        )
        return ToxClawEvidenceEnvelope(
            record_kind="exposureScenario",
            chemical_id=payload.chemical_id,
            context_of_use=context_of_use,
            route=payload.route.value,
            scenario_class=payload.scenario_class.value,
            summary=summary,
            fit_for_purpose=payload.fit_for_purpose,
            limitations=payload.limitations,
            quality_flags=payload.quality_flags,
            provenance=payload.provenance,
            payload=payload.model_dump(mode="json"),
        )

    if isinstance(payload, AggregateExposureSummary):
        summary = (
            f"aggregate screening summary across {len(payload.component_scenarios)} "
            "component scenarios"
        )
        return ToxClawEvidenceEnvelope(
            record_kind="aggregateExposureSummary",
            chemical_id=payload.chemical_id,
            context_of_use=context_of_use,
            route=None,
            scenario_class=payload.scenario_class,
            summary=summary,
            fit_for_purpose=None,
            limitations=payload.limitations,
            quality_flags=payload.quality_flags,
            provenance=payload.provenance,
            payload=payload.model_dump(mode="json"),
        )

    summary = (
        f"scenario comparison with absolute delta {payload.absolute_delta} "
        f"{payload.baseline_dose.unit.value}"
    )
    return ToxClawEvidenceEnvelope(
        record_kind="scenarioComparisonRecord",
        chemical_id=payload.chemical_id,
        context_of_use=context_of_use,
        route=None,
        scenario_class=None,
        summary=summary,
        fit_for_purpose=None,
        limitations=[],
        quality_flags=[],
        provenance=payload.provenance,
        payload=payload.model_dump(mode="json"),
    )


def build_toxclaw_evidence_bundle(
    params: ExportToxClawEvidenceBundleRequest,
) -> ToxClawEvidenceBundle:
    """Export a deterministic ToxClaw-ready evidence record and report section."""

    scenario = params.scenario
    evidence_payload = scenario.model_dump(mode="json", by_alias=True)
    content_hash = _hash_value(evidence_payload)
    summary = _scenario_summary(scenario)
    evidence_id = _deterministic_id(
        "evidence",
        [
            params.case_id,
            "exposure-scenario-mcp",
            scenario.scenario_id,
            scenario.provenance.generated_at,
            content_hash,
        ],
    )
    tags = sorted(
        {
            "exposure-scenario",
            scenario.route.value,
            scenario.scenario_class.value,
            scenario.product_use_profile.product_category,
            scenario.population_profile.population_group,
        }
    )
    evidence_record = ToxClawEvidenceRecord(
        caseId=params.case_id,
        contentHash=content_hash,
        dataClassification=params.data_classification,
        evidenceId=evidence_id,
        qualityFlag=scenario.quality_flags[0].code if scenario.quality_flags else None,
        retrievedAt=scenario.provenance.generated_at,
        runId=params.run_id,
        source="exposure-scenario-mcp",
        sourceRef=scenario.scenario_id,
        summary=summary,
        tags=tags,
        trustLabel=params.trust_label,
        type="exposure-scenario",
    )
    evidence_reference = ToxClawReportEvidenceReference(
        contentHash=evidence_record.content_hash,
        evidenceId=evidence_record.evidence_id,
        qualityFlag=evidence_record.quality_flag,
        rawPointer=evidence_record.raw_pointer,
        redactionStatus=evidence_record.redaction_status,
        retrievedAt=evidence_record.retrieved_at,
        source=evidence_record.source,
        sourceRef=evidence_record.source_ref,
        summary=evidence_record.summary,
        tags=evidence_record.tags,
        trustLabel=evidence_record.trust_label,
        type=evidence_record.type,
    )

    claim_texts = [
        (
            f"The {scenario.route.value} {scenario.scenario_class.value} scenario estimates "
            f"{scenario.external_dose.value} {scenario.external_dose.unit.value} external dose."
        ),
        (
            f"The scenario represents {scenario.population_profile.population_group} use of "
            f"{scenario.product_use_profile.product_category} with "
            f"{scenario.product_use_profile.use_events_per_day:g} event(s) per day."
        ),
    ]
    if scenario.limitations:
        claim_texts.append(
            f"The scenario includes {len(scenario.limitations)} explicit limitation(s) "
            "that require review."
        )
    else:
        claim_texts.append(
            f"The scenario is labeled {scenario.fit_for_purpose.label} for "
            "external-dose screening use."
        )

    section_key = _normalize_section_key(params.section_key)
    claims = [
        ToxClawReportClaim(
            claimId=_deterministic_id(
                "claim",
                [params.report_id, section_key, str(index), _hash_text(text)],
            ),
            confidence="supported",
            evidenceIds=[evidence_id],
            text=text,
        )
        for index, text in enumerate(claim_texts, start=1)
    ]
    report_section = ToxClawReportSection(
        body="\n".join(f"- {text}" for text in claim_texts),
        claims=claims,
        evidenceIds=[evidence_id],
        sectionKey=section_key,
        title=params.section_title,
    )
    return ToxClawEvidenceBundle(
        caseId=params.case_id,
        reportId=params.report_id,
        contextOfUse=params.context_of_use,
        summary=summary,
        evidenceRecord=evidence_record,
        reportEvidenceReference=evidence_reference,
        reportSection=report_section,
    )


def build_toxclaw_refinement_bundle(
    params: ExportToxClawRefinementBundleRequest,
    *,
    generated_at: str | None = None,
) -> ToxClawExposureRefinementBundle:
    """Export a ToxClaw-facing refinement delta with evidence and workflow hooks."""

    comparison = compare_scenarios(
        CompareExposureScenariosInput(
            baseline=params.baseline,
            comparison=params.comparison,
        ),
        DefaultsRegistry.load(),
        generated_at=generated_at,
    )
    changed_assumption_names = [item.name for item in comparison.changed_assumptions]
    summary = _comparison_summary(comparison, params.workflow_action)
    evidence_payload = {
        "workflowAction": params.workflow_action,
        "baselineScenario": params.baseline.model_dump(mode="json", by_alias=True),
        "comparisonScenario": params.comparison.model_dump(mode="json", by_alias=True),
        "comparisonRecord": comparison.model_dump(mode="json", by_alias=True),
    }
    content_hash = _hash_value(evidence_payload)
    evidence_id = _deterministic_id(
        "evidence",
        [
            params.case_id,
            "exposure-scenario-mcp",
            params.baseline.scenario_id,
            params.comparison.scenario_id,
            content_hash,
        ],
    )
    tags = sorted(
        {
            "exposure-refinement",
            "refinement",
            "scenario-comparison",
            params.workflow_action,
            params.baseline.route.value,
            params.comparison.route.value,
            params.baseline.product_use_profile.product_category,
            params.comparison.product_use_profile.product_category,
            *(["route-changed"] if params.baseline.route != params.comparison.route else []),
        }
    )
    source_ref = f"{params.baseline.scenario_id}::{params.comparison.scenario_id}"
    evidence_record = ToxClawEvidenceRecord(
        caseId=params.case_id,
        contentHash=content_hash,
        dataClassification=params.data_classification,
        evidenceId=evidence_id,
        qualityFlag=None,
        retrievedAt=comparison.provenance.generated_at,
        runId=params.run_id,
        source="exposure-scenario-mcp",
        sourceRef=source_ref,
        summary=summary,
        tags=tags,
        trustLabel=params.trust_label,
        type="exposure-refinement",
    )
    evidence_reference = ToxClawReportEvidenceReference(
        contentHash=evidence_record.content_hash,
        evidenceId=evidence_record.evidence_id,
        qualityFlag=evidence_record.quality_flag,
        rawPointer=evidence_record.raw_pointer,
        redactionStatus=evidence_record.redaction_status,
        retrievedAt=evidence_record.retrieved_at,
        source=evidence_record.source,
        sourceRef=evidence_record.source_ref,
        summary=evidence_record.summary,
        tags=evidence_record.tags,
        trustLabel=evidence_record.trust_label,
        type=evidence_record.type,
    )
    claim_texts = [
        (
            f"Baseline scenario {comparison.baseline_scenario_id} estimates "
            f"{comparison.baseline_dose.value} {comparison.baseline_dose.unit.value}; "
            f"comparison scenario {comparison.comparison_scenario_id} estimates "
            f"{comparison.comparison_dose.value} {comparison.comparison_dose.unit.value}."
        ),
        _comparison_delta_note(comparison),
        (
            f"Changed assumptions: {', '.join(changed_assumption_names)}."
            if changed_assumption_names
            else "No assumption deltas were detected between the compared scenarios."
        ),
        _workflow_action_note(params.workflow_action),
    ]
    if params.baseline.route != params.comparison.route:
        claim_texts.append(
            "Routes differ between scenarios; interpret the delta as an audit trace, not a "
            "like-for-like route refinement."
        )

    section_key = _normalize_section_key(params.section_key)
    claims = [
        ToxClawReportClaim(
            claimId=_deterministic_id(
                "claim",
                [params.report_id, section_key, str(index), _hash_text(text)],
            ),
            confidence="supported",
            evidenceIds=[evidence_id],
            text=text,
        )
        for index, text in enumerate(claim_texts, start=1)
    ]
    report_section = ToxClawReportSection(
        body="\n".join(f"- {text}" for text in claim_texts),
        claims=claims,
        evidenceIds=[evidence_id],
        sectionKey=section_key,
        title=params.section_title,
    )
    workflow_hooks = [
        ExposureWorkflowHook(
            action="scenario_comparison",
            toolName="exposure_compare_exposure_scenarios",
            whenToUse=(
                "Use after generating a revised scenario to quantify the external-dose delta "
                "without making risk or PBPK claims."
            ),
            requiredInputs=["baseline scenario", "comparison scenario"],
        ),
        ExposureWorkflowHook(
            action="route_recalculation",
            toolName=_route_recalculation_tool_name(params.comparison),
            whenToUse=(
                "Use when ToxClaw needs a route-specific recomputation of the candidate "
                "scenario before comparing it against the current screening baseline."
            ),
            requiredInputs=[
                "chemical_id",
                "route-specific product_use_profile",
                "population_profile",
            ],
        ),
        ExposureWorkflowHook(
            action="aggregate_variant",
            toolName="exposure_build_aggregate_exposure_scenario",
            whenToUse=(
                "Use when the refinement question depends on a combined multi-component "
                "or multi-route screening variant."
            ),
            requiredInputs=["shared chemical_id", "component scenarios", "aggregate label"],
        ),
        ExposureWorkflowHook(
            action="pbpk_export",
            toolName="exposure_export_pbpk_external_import_bundle",
            whenToUse=(
                "Use only after selecting the scenario that should advance from external-dose "
                "refinement into PBPK translation."
            ),
            requiredInputs=["selected source scenario"],
        ),
    ]
    refinement_signal = ToxClawExposureRefinementSignal(
        workflowAction=params.workflow_action,
        routeChanged=params.baseline.route != params.comparison.route,
        changedAssumptionNames=changed_assumption_names,
        changedAssumptionCount=len(changed_assumption_names),
        doseDeltaDirection=_comparison_delta_direction(comparison),
        percentDelta=comparison.percent_delta,
        materialChange=bool(
            comparison.absolute_delta
            or changed_assumption_names
            or params.baseline.route != params.comparison.route
        ),
        boundaryNote=(
            "This bundle supports exposure-context refinement only. ToxClaw still owns "
            "line-of-evidence synthesis and the final recommendation."
        ),
        workflowHooks=workflow_hooks,
    )
    return ToxClawExposureRefinementBundle(
        caseId=params.case_id,
        reportId=params.report_id,
        contextOfUse=params.context_of_use,
        workflowAction=params.workflow_action,
        summary=summary,
        baselineScenario=params.baseline,
        comparisonScenario=params.comparison,
        comparisonRecord=comparison,
        evidenceRecord=evidence_record,
        reportEvidenceReference=evidence_reference,
        reportSection=report_section,
        refinementSignal=refinement_signal,
    )


def check_pbpk_compatibility(scenario: ExposureScenario) -> PbpkCompatibilityReport:
    """Check whether a source exposure scenario is mechanically ready for PBPK export."""

    issues: list[LimitationNote] = []
    missing_fields: list[str] = []
    if scenario.external_dose.unit.value not in {"mg/kg-day", "mg/day", "mg/event"}:
        issues.append(
            LimitationNote(
                code="pbpk_unit_unsupported",
                severity=Severity.ERROR,
                message=(
                    "PBPK handoff requires canonical external dose units of "
                    "mg/kg-day, mg/day, or mg/event."
                ),
            )
        )
    if scenario.product_use_profile.use_events_per_day <= 0:
        issues.append(
            LimitationNote(
                code="pbpk_events_invalid",
                severity=Severity.ERROR,
                message="PBPK handoff requires a positive use_events_per_day value.",
            )
        )
    if _resolved_body_weight_kg(scenario) is None:
        missing_fields.append("assessmentContext.doseScenario.bodyWeightKg")
        issues.append(
            LimitationNote(
                code="pbpk_body_weight_missing",
                severity=Severity.ERROR,
                message=(
                    "PBPK handoff requires a resolved body_weight_kg in the population profile."
                ),
            )
        )
    if (
        scenario.route == Route.INHALATION
        and scenario.product_use_profile.exposure_duration_hours is None
    ):
        missing_fields.append("assessmentContext.doseScenario.eventDurationHours")
        issues.append(
            LimitationNote(
                code="pbpk_inhalation_duration_missing",
                severity=Severity.ERROR,
                message=(
                    "Inhalation PBPK bundle export requires an explicit exposure_duration_hours "
                    "value to preserve event timing semantics."
                ),
            )
        )
    if not scenario.chemical_name:
        issues.append(
            LimitationNote(
                code="pbpk_identity_name_missing",
                severity=Severity.WARNING,
                message=(
                    "PBPK bundle export is stronger when a human-readable chemical_name is "
                    "available for auditability."
                ),
            )
        )
    issues.append(
        LimitationNote(
            code="pbpk_downstream_review_required",
            severity=Severity.WARNING,
            message=(
                "This bundle is an upstream external-exposure handoff only. PBPK execution, "
                "internal dose estimation, and qualification review remain downstream "
                "responsibilities."
            ),
        )
    )
    compatible = not any(item.severity == Severity.ERROR for item in issues)
    ready_for_external_import = compatible

    return PbpkCompatibilityReport(
        source_scenario_id=scenario.scenario_id,
        compatible=compatible,
        checked_route=scenario.route,
        checked_dose_unit=scenario.external_dose.unit.value,
        ready_for_external_pbpk_import=ready_for_external_import,
        supported_pbpk_objects=[
            "ingest_external_pbpk_bundle.arguments",
            "pbpk-mcp.ngraObjects.assessmentContext.v1",
            "pbpk-mcp.ngraObjects.pbpkQualificationSummary.v1",
            "pbpk-mcp.ngraObjects.uncertaintySummary.v1",
            "pbpk-mcp.ngraObjects.uncertaintyHandoff.v1",
            "pbpk-mcp.ngraObjects.internalExposureEstimate.v1",
            "pbpk-mcp.ngraObjects.pointOfDepartureReference.v1",
            "pbpk-mcp.ngraObjects.berInputBundle.v1",
        ],
        missing_external_bundle_fields=missing_fields,
        checked_fields=[
            "toolCall.arguments.assessmentContext.domain.route",
            "toolCall.arguments.assessmentContext.doseScenario.externalDose.unit",
            "toolCall.arguments.assessmentContext.doseScenario.eventsPerDay",
            "toolCall.arguments.assessmentContext.doseScenario.bodyWeightKg",
            "toolCall.arguments.assessmentContext.doseScenario.eventDurationHours",
            "toolCall.arguments.assessmentContext.domain.compound",
        ],
        issues=issues,
        recommended_next_steps=[
            "Call PBPK MCP `ingest_external_pbpk_bundle` with `toolCall.arguments`.",
            "Preserve `bundle.supportingHandoffs` and `toxclawModuleParams` as additive "
            "exposure-side context outside the exact PBPK request payload.",
            "Review returned internalExposureEstimate and pbpkQualificationSummary before "
            "downstream interpretation.",
        ],
    )


def build_pbpk_external_import_package(
    params: ExportPbpkExternalImportBundleRequest,
    *,
    generated_at: str | None = None,
) -> PbpkExternalImportPackage:
    """Build a PBPK MCP external-import payload template from an exposure scenario."""

    scenario = params.scenario
    body_weight_kg = _resolved_body_weight_kg(scenario)
    pbpk_input = export_pbpk_input(
        ExportPbpkScenarioInputRequest(scenario=scenario),
        DefaultsRegistry.load(),
        generated_at=generated_at,
    )
    uncertainty_summary = _upstream_uncertainty_summary(scenario)
    assessment_context = {
        "contextOfUse": params.context_of_use,
        "scientificPurpose": params.scientific_purpose,
        "decisionContext": params.decision_context,
        "decisionOwner": "external-orchestrator",
        "handoffTarget": "pbpk-mcp",
        "requestedSubject": scenario.chemical_name or scenario.chemical_id,
        "sourceScenarioId": scenario.scenario_id,
        "domain": {
            "species": "human",
            "route": scenario.route.value,
            "lifeStage": _life_stage(scenario.population_profile.population_group),
            "population": scenario.population_profile.population_group,
            "compound": scenario.chemical_name or scenario.chemical_id,
            "region": scenario.population_profile.region,
        },
        "doseScenario": {
            "scenarioId": scenario.scenario_id,
            "externalDose": {
                "metric": scenario.external_dose.metric,
                "value": scenario.external_dose.value,
                "unit": scenario.external_dose.unit.value,
            },
            "eventsPerDay": scenario.product_use_profile.use_events_per_day,
            "eventDurationHours": scenario.product_use_profile.exposure_duration_hours,
            "timingPattern": _scenario_timing_pattern(scenario),
            "productCategory": scenario.product_use_profile.product_category,
            "applicationMethod": scenario.product_use_profile.application_method,
            "retentionType": scenario.product_use_profile.retention_type,
            "bodyWeightKg": body_weight_kg,
        },
        "targetOutput": params.requested_output or scenario.external_dose.metric,
    }
    bundle = PbpkExternalImportBundle(
        sourcePlatform=params.source_platform,
        sourceVersion=params.source_version,
        modelName=params.model_name or f"{scenario.scenario_id}-upstream-context",
        modelType="exposure-scenario-context",
        executionDate=scenario.provenance.generated_at,
        runId=f"{scenario.scenario_id}-external-context",
        operator=params.operator,
        sponsor=params.sponsor,
        rawArtifacts=[],
        assessmentContext=assessment_context,
        chemicalIdentity=_chemical_identity_context(scenario),
        supportingHandoffs={
            "exposureScenario": scenario.model_dump(mode="json", by_alias=True),
            "pbpkScenarioInput": pbpk_input.model_dump(mode="json", by_alias=True),
            "upstreamUncertaintySummary": uncertainty_summary,
        },
        internalExposure={},
        qualification={
            "summary": (
                "Imported upstream external-exposure context only; PBPK execution and "
                "qualification outputs are expected downstream from PBPK MCP."
            ),
            "evidenceLevel": "upstream-context-only",
            "verificationStatus": "awaiting-pbpk-execution",
            "performanceEvidenceBoundary": "pbpk-results-not-yet-produced",
            "contextOfUse": params.context_of_use,
            "scientificPurpose": params.scientific_purpose,
            "missingEvidenceCount": 0,
        },
        uncertainty={
            "status": "declared",
            **uncertainty_summary,
            "sources": sorted({item.source.title for item in scenario.assumptions}),
            "residualUncertainty": "upstream-exposure-scenario-assumptions",
            "bundleMetadata": {"sourceScenarioId": scenario.scenario_id},
        },
        uncertaintyRegister={
            "source": "Direct-Use Exposure MCP",
            "scope": "upstream-external-exposure-context",
            "summary": (
                "Exposure-scenario limitations remain upstream and must be synthesized with "
                "PBPK and NAM uncertainty downstream."
            ),
        },
        pod={},
        trueDoseAdjustment={
            "applied": False,
            "summary": "Not applicable at the upstream external-exposure stage.",
        },
        comparisonMetric=params.comparison_metric,
    )
    request_payload = PbpkExternalImportRequest(
        sourcePlatform=bundle.source_platform,
        sourceVersion=bundle.source_version,
        modelName=bundle.model_name,
        modelType=bundle.model_type,
        executionDate=bundle.execution_date,
        runId=bundle.run_id,
        operator=bundle.operator,
        sponsor=bundle.sponsor,
        rawArtifacts=bundle.raw_artifacts,
        assessmentContext=bundle.assessment_context,
        internalExposure=bundle.internal_exposure,
        qualification=bundle.qualification,
        uncertainty=bundle.uncertainty,
        uncertaintyRegister=bundle.uncertainty_register,
        pod=bundle.pod,
        trueDoseAdjustment=bundle.true_dose_adjustment,
        comparisonMetric=bundle.comparison_metric,
    )
    tool_call = PbpkExternalImportToolCall(arguments=request_payload)
    toxclaw_module_params = ToxClawPbpkModuleParams(
        arguments=request_payload,
        chemicalIdentity=bundle.chemical_identity,
        supportingHandoffs=bundle.supporting_handoffs,
    )
    return PbpkExternalImportPackage(
        bundle=bundle,
        requestPayload=request_payload,
        toolCall=tool_call,
        toxclawModuleParams=toxclaw_module_params,
        compatibilityReport=check_pbpk_compatibility(scenario),
    )


def run_integrated_exposure_workflow(
    params: RunIntegratedExposureWorkflowInput,
    *,
    registry: DefaultsRegistry | None = None,
    generated_at: str | None = None,
) -> IntegratedExposureWorkflowResult:
    """Run the local end-to-end evidence -> exposure -> PBPK handoff workflow."""

    registry = registry or DefaultsRegistry.load()
    source_request = params.request
    quality_flags: list[QualityFlag] = []
    limitations: list[LimitationNote] = []
    workflow_notes: list[str] = []

    normalized_evidence_records: list[ProductUseEvidenceRecord] = []
    if params.comp_tox_record is not None:
        normalized_evidence_records.append(
            build_product_use_evidence_from_comptox(params.comp_tox_record)
        )
        quality_flags.append(
            QualityFlag(
                code="integrated_workflow_comptox_normalized",
                severity=Severity.INFO,
                message="CompTox record was normalized into the generic evidence contract.",
            )
        )
    if params.cons_expo_records:
        normalized_evidence_records.extend(
            build_product_use_evidence_from_consexpo(record) for record in params.cons_expo_records
        )
        quality_flags.append(
            QualityFlag(
                code="integrated_workflow_consexpo_normalized",
                severity=Severity.INFO,
                message=(
                    f"Normalized {len(params.cons_expo_records)} ConsExpo record(s) into the "
                    "generic evidence contract."
                ),
            )
        )
    if params.sccs_records:
        normalized_evidence_records.extend(
            build_product_use_evidence_from_sccs(record) for record in params.sccs_records
        )
        quality_flags.append(
            QualityFlag(
                code="integrated_workflow_sccs_normalized",
                severity=Severity.INFO,
                message=(
                    f"Normalized {len(params.sccs_records)} SCCS record(s) into the "
                    "generic evidence contract."
                ),
            )
        )
    if params.sccs_opinion_records:
        normalized_evidence_records.extend(
            build_product_use_evidence_from_sccs_opinion(record)
            for record in params.sccs_opinion_records
        )
        quality_flags.append(
            QualityFlag(
                code="integrated_workflow_sccs_opinion_normalized",
                severity=Severity.INFO,
                message=(
                    f"Normalized {len(params.sccs_opinion_records)} SCCS opinion record(s) "
                    "into the generic evidence contract."
                ),
            )
        )
    if params.cosing_records:
        normalized_evidence_records.extend(
            build_product_use_evidence_from_cosing(record) for record in params.cosing_records
        )
        quality_flags.append(
            QualityFlag(
                code="integrated_workflow_cosing_normalized",
                severity=Severity.INFO,
                message=(
                    f"Normalized {len(params.cosing_records)} CosIng record(s) into the "
                    "generic evidence contract."
                ),
            )
        )
    if params.nanomaterial_records:
        normalized_evidence_records.extend(
            build_product_use_evidence_from_nanomaterial(record)
            for record in params.nanomaterial_records
        )
        quality_flags.append(
            QualityFlag(
                code="integrated_workflow_nanomaterial_normalized",
                severity=Severity.INFO,
                message=(
                    f"Normalized {len(params.nanomaterial_records)} nanomaterial record(s) "
                    "into the generic evidence contract."
                ),
            )
        )
    if params.synthetic_polymer_microparticle_records:
        normalized_evidence_records.extend(
            build_product_use_evidence_from_synthetic_polymer_microparticle(record)
            for record in params.synthetic_polymer_microparticle_records
        )
        quality_flags.append(
            QualityFlag(
                code="integrated_workflow_microplastics_normalized",
                severity=Severity.INFO,
                message=(
                    "Normalized "
                    f"{len(params.synthetic_polymer_microparticle_records)} synthetic polymer "
                    "microparticle record(s) into the generic evidence contract."
                ),
            )
        )
    if params.evidence_records:
        normalized_evidence_records.extend(params.evidence_records)
        quality_flags.append(
            QualityFlag(
                code="integrated_workflow_user_evidence_attached",
                severity=Severity.INFO,
                message=(
                    f"Attached {len(params.evidence_records)} additional evidence record(s) "
                    "to the integrated workflow."
                ),
            )
        )

    reconciliation_report: ProductUseEvidenceReconciliationReport | None = None
    effective_request = source_request
    evidence_strategy: Literal[
        "source_request_only",
        "reconciled_evidence_applied",
        "reconciled_evidence_applied_with_review",
        "evidence_rejected_source_request_retained",
    ] = "source_request_only"
    manual_review_required = False
    selected_evidence_source_name: str | None = None
    selected_evidence_source_kind: str | None = None

    if normalized_evidence_records:
        reconciliation_report = reconcile_product_use_evidence(
            source_request,
            normalized_evidence_records,
            require_auto_apply_safe=params.require_auto_apply_safe,
        )
        selected_evidence_source_name = reconciliation_report.recommended_source_name
        selected_evidence_source_kind = reconciliation_report.recommended_source_kind
        manual_review_required = reconciliation_report.manual_review_required

        if reconciliation_report.merged_request is not None:
            effective_request = _restore_request_contract(
                source_request,
                reconciliation_report.merged_request,
            )
            if reconciliation_report.recommendation == "apply":
                evidence_strategy = "reconciled_evidence_applied"
                workflow_notes.append(
                    "Built the effective request from reconciled evidence without review-only "
                    "conflicts."
                )
            else:
                evidence_strategy = "reconciled_evidence_applied_with_review"
                workflow_notes.append(
                    "Built the effective request from reconciled evidence, but manual review "
                    "is still required."
                )
                quality_flags.append(
                    QualityFlag(
                        code="integrated_workflow_evidence_review_required",
                        severity=Severity.WARNING,
                        message=(
                            "Evidence reconciliation selected a usable source, but the merged "
                            "request still requires human review."
                        ),
                    )
                )
        else:
            ensure(
                params.continue_on_evidence_reject,
                "integrated_workflow_evidence_rejected",
                "No compatible evidence could be applied in the integrated workflow.",
                suggestion=(
                    "Revise the evidence records or rerun with continueOnEvidenceReject=true "
                    "to keep the original request."
                ),
                considered_sources=reconciliation_report.considered_sources,
            )
            evidence_strategy = "evidence_rejected_source_request_retained"
            manual_review_required = True
            workflow_notes.append(
                "All supplied evidence was rejected, so the workflow retained the source request."
            )
            quality_flags.append(
                QualityFlag(
                    code="integrated_workflow_evidence_rejected_source_request_retained",
                    severity=Severity.WARNING,
                    message=(
                        "No compatible evidence was available; the workflow retained the "
                        "source request."
                    ),
                )
            )
            limitations.append(
                LimitationNote(
                    code="integrated_workflow_no_compatible_evidence",
                    severity=Severity.WARNING,
                    message=(
                        "The scenario was built from the source request because all supplied "
                        "evidence records were incompatible."
                    ),
                )
            )
    else:
        workflow_notes.append(
            "No external evidence records were supplied, so the source request was built as-is."
        )
        quality_flags.append(
            QualityFlag(
                code="integrated_workflow_source_request_only",
                severity=Severity.INFO,
                message="The integrated workflow proceeded without external evidence records.",
            )
        )

    scenario = _build_scenario_from_request(
        effective_request,
        registry,
        generated_at=generated_at,
    )
    quality_flags.append(
        QualityFlag(
            code="integrated_workflow_scenario_built",
            severity=Severity.INFO,
            message=(
                f"Built scenario `{scenario.scenario_id}` from the effective reconciled request."
            ),
        )
    )

    pbpk_compatibility_report = check_pbpk_compatibility(scenario)
    if any(item.severity == Severity.ERROR for item in pbpk_compatibility_report.issues):
        manual_review_required = True
        quality_flags.append(
            QualityFlag(
                code="integrated_workflow_pbpk_not_ready",
                severity=Severity.WARNING,
                message=(
                    "PBPK compatibility checks found blocking issues for the current scenario."
                ),
            )
        )

    pbpk_scenario_input: PbpkScenarioInput | None = None
    if params.export_pbpk_scenario_input:
        pbpk_scenario_input = export_pbpk_input(
            ExportPbpkScenarioInputRequest(
                scenario=scenario,
                regimen_name=params.pbpk_regimen_name,
            ),
            registry,
            generated_at=generated_at,
        )
        quality_flags.append(
            QualityFlag(
                code="integrated_workflow_pbpk_scenario_input_exported",
                severity=Severity.INFO,
                message="Exported the normalized PBPK scenario input object.",
            )
        )

    pbpk_external_import_package: PbpkExternalImportPackage | None = None
    if params.export_pbpk_external_import_bundle:
        pbpk_external_import_package = build_pbpk_external_import_package(
            ExportPbpkExternalImportBundleRequest(
                scenario=scenario,
                context_of_use=params.pbpk_context_of_use,
                scientific_purpose=params.pbpk_scientific_purpose,
                decision_context=params.pbpk_decision_context,
                requested_output=params.pbpk_requested_output,
            ),
            generated_at=generated_at,
        )
        quality_flags.append(
            QualityFlag(
                code="integrated_workflow_pbpk_external_import_bundle_exported",
                severity=Severity.INFO,
                message="Exported the PBPK external-import bundle package.",
            )
        )

    return IntegratedExposureWorkflowResult(
        chemicalId=scenario.chemical_id,
        sourceRequest=source_request,
        effectiveRequest=effective_request,
        evidenceStrategy=evidence_strategy,
        normalizedEvidenceRecords=normalized_evidence_records,
        reconciliationReport=reconciliation_report,
        selectedEvidenceSourceName=selected_evidence_source_name,
        selectedEvidenceSourceKind=selected_evidence_source_kind,
        manualReviewRequired=manual_review_required,
        scenario=scenario,
        pbpkCompatibilityReport=pbpk_compatibility_report,
        pbpkScenarioInput=pbpk_scenario_input,
        pbpkExternalImportPackage=pbpk_external_import_package,
        workflowNotes=workflow_notes,
        qualityFlags=quality_flags,
        limitations=limitations,
        provenance=_workflow_provenance(registry, generated_at=generated_at),
    )


def suite_integration_guide() -> str:
    return """# Direct-Use Exposure MCP Suite Integration Guide

## Boundary

- Direct-Use Exposure MCP owns external dose construction only.
- Direct-use oral and incidental oral stay inside Direct-Use Exposure MCP.
- Diet-mediated oral belongs in a sibling Dietary MCP.
- Environmental release and multimedia concentration generation belong in a sibling Fate MCP.
- PBPK MCP owns internal exposure and toxicokinetics.
- ToxClaw owns orchestration, line-of-evidence handling, refinement policy,
  and final interpretation.

## Shared Contracts

- `chemicalIdentity.v1` for suite-stable chemical identity handoff
- `productUseEvidenceRecord.v1` for reviewed product-use evidence
- `exposureScenarioDefinition.v1` for direct-use or concentration-to-dose scenario definitions
- `routeDoseEstimate.v1` for compact downstream dose handoff
- `environmentalReleaseScenario.v1` for future Fate MCP release ingress
- `concentrationSurface.v1` for future Fate MCP concentration outputs
- `pbpkExternalImportBundle.v1` for PBPK MCP external-dose bundle handoff

## CompTox Integration

- Use CompTox identity records to enrich `chemical_name`, CASRN context,
  and upstream product-use discovery.
- Do not make CompTox enrichment mandatory for scenario construction.
- Preserve CompTox references in `assumption_overrides` or envelope metadata
  rather than hiding them.

## ToxClaw Integration

- Wrap `exposureScenario.v1`, `aggregateExposureSummary.v1`, and `scenarioComparisonRecord.v1`
  as evidence envelopes so ToxClaw can preserve context of use, fit-for-purpose, limitations,
  and provenance without custom glue logic.
- `build_toxclaw_evidence_bundle` emits deterministic ToxClaw-compatible evidence and report
  primitives: an evidence record, a report evidence reference, and a claim-linked report section.
- `build_toxclaw_refinement_bundle` emits an exposure-refinement delta package with an explicit
  `refine_exposure` signal for `exposure_context`, a preserved comparison ledger, and workflow hooks
  for compare, route recalculation, aggregate variants, and PBPK export.
- Treat comparison outputs as evidence about refinement deltas, not as final decisions.

## PBPK Integration

- Export only route, dose magnitude, timing pattern, duration, and population context.
- Do not leak product narratives, use-category prose, or refinement
  commentary into the PBPK contract.
- `build_pbpk_external_import_package` maps upstream exposure context into PBPK MCP's
  `ingest_external_pbpk_bundle` request shape and now emits exact top-level
  `toolCall.arguments` for direct invocation plus ToxClaw-ready module params with additive
  exposure-side handoffs kept outside the strict PBPK request payload.
- Treat `ready_for_external_pbpk_import=true` as "safe to invoke the PBPK MCP ingest tool",
  not as "PBPK outputs already exist."
"""
