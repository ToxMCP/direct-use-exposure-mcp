"""Deterministic Fate soil-contact -> Exposure -> WoE round-trip fixture builder.

This fixture freezes an explicit concentration-to-intake bridge for
environmental agricultural-soil context. It intentionally does not reuse the
direct-use or dietary scenario builders. Instead, it preserves the upstream
Fate concentration surface and exports a bounded oral screening dose with
transparent soil-ingestion assumptions.
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from exposure_scenario_mcp.models import (
    ChemicalIdentity,
    DoseUnit,
    ExposureScenarioDefinition,
    FitForPurpose,
    LimitationNote,
    PopulationProfile,
    ProvenanceBundle,
    QualityFlag,
    Route,
    RouteDoseEstimate,
    ScenarioClass,
    ScenarioDose,
    Severity,
)
from exposure_scenario_mcp.package_metadata import CURRENT_VERSION

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
SOURCE_FIXTURE_PATH = (
    WORKSPACE_ROOT
    / "tests"
    / "fixtures"
    / "cross_suite"
    / "upstream"
    / "fate_exposure_handoff.v1.1.0.json"
)
WOE_ROUNDTRIP_FIXTURE_PATH = (
    WORKSPACE_ROOT
    / "tests"
    / "fixtures"
    / "cross_suite"
    / "woe_ngra"
    / "fate_soil_oral_exposure_handoff.v1.1.0.json"
)
WOE_SYNC_TARGET_PATH = (
    WORKSPACE_ROOT.parent
    / "WoE_NGRA_Synthesis_MCP"
    / "src"
    / "integration"
    / "__fixtures__"
    / "fate-soil-oral-exposure-woe-roundtrip.bundle.json"
)

DETERMINISTIC_GENERATED_AT = "2026-04-21T15:00:00.000Z"
SOURCE_VERSION = "1.1.0"
SCHEMA_VERSION = "1.1.0"
BUNDLE_ID = "fate-soil-oral-exposure-handoff-001"
CREATED_BY = "direct-use-exposure-fate-soil-oral-fixture-builder"
PRODUCER_MODULE = "direct_use_exposure"

SCENARIO_DEFINITION_ID = "exp-fate-soil-definition-001"
ROUTE_DOSE_ARTIFACT_ID = "exp-fate-soil-route-dose-001"
SOURCE_FATE_EVIDENCE_ID = "fate-exp-soil-001"
SOURCE_SURFACE_ARTIFACT_ID = "fate-surface-soil-001"

BODY_WEIGHT_KG = 70.0
SOIL_INGESTION_MG_PER_DAY = 50.0
EVENTS_PER_DAY = 1.0


def _sorted_json(value: Any) -> Any:
    if isinstance(value, list):
        return [_sorted_json(item) for item in value]
    if isinstance(value, dict):
        return {key: _sorted_json(item) for key, item in sorted(value.items())}
    return value


def _stable_json_dumps(value: Any) -> str:
    return json.dumps(_sorted_json(value), indent=2)


def _hash_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _hash_value(value: Any) -> str:
    return _hash_text(_stable_json_dumps(value))


def _source_hash(snapshot: Any) -> list[dict[str, str]]:
    return [{"algorithm": "sha256", "value": _hash_value(snapshot)}]


def _provenance(
    *,
    tool_run_id: str,
    source_hash_value: Any | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "toolRunId": tool_run_id,
        "createdAt": DETERMINISTIC_GENERATED_AT,
        "createdBy": CREATED_BY,
    }
    if source_hash_value is not None:
        payload["sourceHashes"] = _source_hash(source_hash_value)
    return payload


def _typed_ref(
    *,
    object_type_ref: str,
    artifact_id: str,
    retrieval_endpoint: str,
    cached_snapshot: dict[str, Any],
) -> dict[str, Any]:
    return {
        "objectType": "typedHandoffRef",
        "schemaVersion": "1.1.0",
        "objectTypeRef": object_type_ref,
        "retrievalEndpoint": retrieval_endpoint,
        "cachedSnapshot": cached_snapshot,
        "artifactId": artifact_id,
        "producerModule": PRODUCER_MODULE,
        "producerVersion": CURRENT_VERSION,
        "integrityHash": f"sha256:{_hash_value(cached_snapshot)}",
    }


def _load_source_bundle(path: Path = SOURCE_FIXTURE_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_source_evidence(source_bundle: dict[str, Any]) -> dict[str, Any]:
    for evidence in source_bundle.get("evidenceItems", []):
        if evidence.get("originalId") == SOURCE_FATE_EVIDENCE_ID:
            return evidence
    raise KeyError(f"Missing expected Fate evidence item: {SOURCE_FATE_EVIDENCE_ID}")


def _find_source_item(
    source_bundle: dict[str, Any], collection_key: str, object_id: str
) -> dict[str, Any]:
    for item in source_bundle.get(collection_key, []):
        if object_id in item.get("affectedObjectIds", []) or object_id in item.get(
            "evidenceObjectIds", []
        ):
            return item
    raise KeyError(f"Missing expected source item '{object_id}' in '{collection_key}'.")


def _find_source_ref(evidence_item: dict[str, Any], object_type_ref: str) -> dict[str, Any]:
    for ref in evidence_item.get("upstreamArtifactRefs", []):
        if ref.get("objectTypeRef") == object_type_ref:
            return ref
    raise KeyError(f"Missing expected Fate upstreamArtifactRef '{object_type_ref}'.")


def _find_identifier(evidence_item: dict[str, Any], identifier_type: str) -> str | None:
    for identifier in evidence_item.get("studyIdentifiers", []):
        if identifier.get("identifierType") == identifier_type:
            return identifier.get("identifierValue")
    return None


def _build_chemical_identity(source_evidence: dict[str, Any]) -> ChemicalIdentity:
    release_snapshot = _find_source_ref(source_evidence, "EnvironmentalReleaseScenario").get(
        "cachedSnapshot", {}
    )
    preferred_name = release_snapshot.get("preferredName") or "Example Fate Compound"
    return ChemicalIdentity(
        chemicalId="FATE-CROSS-SUITE-EXAMPLE-001",
        preferredName=preferred_name,
        externalIdentifiers={
            "fateScenarioId": str(
                release_snapshot.get("scenarioId") or "fate-environmental-scenario-001"
            ),
        },
        notes=[
            (
                "Fixture-local stable chemical identifier used because the upstream Fate "
                "snapshot does not carry a richer suite identity object."
            )
        ],
    )


def _build_population_profile(source_evidence: dict[str, Any]) -> PopulationProfile:
    source_region = source_evidence.get("region") or "eu_screening_default"
    return PopulationProfile(
        population_group="adult",
        body_weight_kg=BODY_WEIGHT_KG,
        demographic_tags=["general_population", "environmental_screening"],
        region=str(source_region),
    )


def _translation_summary(source_evidence: dict[str, Any]) -> dict[str, float | str]:
    concentration_mg_per_kg = float(source_evidence["doseValue"])
    soil_ingestion_mg_per_day = SOIL_INGESTION_MG_PER_DAY * EVENTS_PER_DAY
    soil_ingestion_kg_per_day = soil_ingestion_mg_per_day / 1_000_000.0
    external_mass_mg_per_day = concentration_mg_per_kg * soil_ingestion_kg_per_day
    external_dose_mg_per_kg_day = external_mass_mg_per_day / BODY_WEIGHT_KG
    return {
        "concentrationMgPerKg": concentration_mg_per_kg,
        "soilIngestionMgPerDay": SOIL_INGESTION_MG_PER_DAY,
        "eventsPerDay": EVENTS_PER_DAY,
        "ingestedSoilMgPerDay": soil_ingestion_mg_per_day,
        "ingestedSoilKgPerDay": soil_ingestion_kg_per_day,
        "externalMassMgPerDay": external_mass_mg_per_day,
        "externalDoseMgPerKgDay": external_dose_mg_per_kg_day,
    }


def _build_fit_for_purpose() -> FitForPurpose:
    return FitForPurpose(
        label="bounded_environmental_soil_oral_translation",
        suitable_for=[
            "Agricultural-soil concentration to soil-contact external-dose screening translation.",
            "Traceable Fate -> Exposure -> IVIVE/WoE integration testing.",
        ],
        not_suitable_for=[
            "Crop-uptake or food-mediated residue interpretation.",
            "Internal dose interpretation without downstream TK/PBPK review.",
            "Individualized soil-contact or child-specific mouthing scenarios.",
        ],
    )


def _build_route_dose_provenance(summary: dict[str, float | str]) -> ProvenanceBundle:
    defaults_hash = _hash_value(
        {
            "body_weight_kg": BODY_WEIGHT_KG,
            "soil_ingestion_mg_per_day": SOIL_INGESTION_MG_PER_DAY,
            "events_per_day": EVENTS_PER_DAY,
        }
    )
    return ProvenanceBundle(
        algorithm_id="concentration_to_intake.soil_contact_screening.v1",
        plugin_id="fate_soil_contact_concentration_to_intake_fixture",
        plugin_version=CURRENT_VERSION,
        defaults_version="cross_suite_fixture_v1",
        defaults_hash_sha256=defaults_hash,
        generated_at=DETERMINISTIC_GENERATED_AT,
        notes=[
            (
                "This deterministic fixture translates agricultural-soil concentration "
                "into a bounded external oral dose using explicit soil-ingestion "
                "screening assumptions."
            ),
            (
                f"Concentration {summary['concentrationMgPerKg']:.15f} mg/kg x soil "
                f"ingestion {summary['soilIngestionMgPerDay']} mg/day / 1,000,000 / "
                f"{BODY_WEIGHT_KG} kg."
            ),
        ],
    )


def _build_scenario_definition(
    chemical_identity: ChemicalIdentity,
    population_profile: PopulationProfile,
) -> ExposureScenarioDefinition:
    return ExposureScenarioDefinition(
        scenarioDefinitionId=SCENARIO_DEFINITION_ID,
        chemicalIdentity=chemical_identity,
        route=Route.ORAL,
        scenarioClass=ScenarioClass.SCREENING,
        pathwaySemantics="concentration_to_intake",
        populationProfile=population_profile,
        sourceConcentrationSurfaceIds=[SOURCE_SURFACE_ARTIFACT_ID],
        assumptionOverrides={
            "bodyWeightKg": BODY_WEIGHT_KG,
            "soilIngestionMgPerDay": SOIL_INGESTION_MG_PER_DAY,
            "eventsPerDay": EVENTS_PER_DAY,
        },
        notes=[
            (
                "Scenario definition is driven by agricultural-soil concentration from "
                "Fate MCP rather than a product-use or food-residue regimen."
            ),
            (
                "The exposure layer resolves only the soil-contact branch of the source "
                "route hint; crop uptake remains out of scope."
            ),
        ],
    )


def _build_route_dose_estimate(
    *,
    chemical_identity: ChemicalIdentity,
    population_profile: PopulationProfile,
    summary: dict[str, float | str],
) -> RouteDoseEstimate:
    return RouteDoseEstimate(
        chemicalIdentity=chemical_identity,
        route=Route.ORAL,
        scenarioClass=ScenarioClass.SCREENING,
        dose=ScenarioDose(
            metric="external_dose_screening",
            value=float(summary["externalDoseMgPerKgDay"]),
            unit=DoseUnit.MG_PER_KG_DAY,
        ),
        sourceScenarioDefinitionId=SCENARIO_DEFINITION_ID,
        sourceConcentrationSurfaceIds=[SOURCE_SURFACE_ARTIFACT_ID],
        populationProfile=population_profile,
        fitForPurpose=_build_fit_for_purpose(),
        provenance=_build_route_dose_provenance(summary),
        limitations=[
            LimitationNote(
                code="soil_contact_screening_translation",
                severity=Severity.WARNING,
                message=(
                    "Route-dose estimate uses explicit screening assumptions for soil ingestion, "
                    "body weight, and daily intake frequency."
                ),
            ),
            LimitationNote(
                code="crop_uptake_not_resolved",
                severity=Severity.WARNING,
                message=(
                    "Agricultural-soil concentration remains environmental-media "
                    "context and does not resolve crop uptake or food-mediated residue "
                    "intake."
                ),
            ),
        ],
        qualityFlags=[
            QualityFlag(
                code="fate_lineage_preserved",
                severity=Severity.INFO,
                message=(
                    "Source concentration surface lineage and route-hint context are "
                    "preserved downstream."
                ),
            )
        ],
        notes=[
            (
                "External dose is bounded screening output only and must not be "
                "interpreted as internal dose."
            ),
            (
                "Crop-uptake and food-mediated environmental oral scenarios remain out "
                "of scope for this soil-contact bridge fixture."
            ),
        ],
    )


def build_fate_soil_oral_woe_roundtrip_bundle() -> dict[str, Any]:
    source_bundle = _load_source_bundle()
    source_evidence = _find_source_evidence(source_bundle)
    source_claim = _find_source_item(source_bundle, "claimItems", SOURCE_FATE_EVIDENCE_ID)
    source_applicability = _find_source_item(
        source_bundle, "applicabilityItems", SOURCE_FATE_EVIDENCE_ID
    )
    source_uncertainty = _find_source_item(
        source_bundle, "uncertaintyItems", SOURCE_FATE_EVIDENCE_ID
    )

    chemical_identity = _build_chemical_identity(source_evidence)
    population_profile = _build_population_profile(source_evidence)
    translation_summary = _translation_summary(source_evidence)
    scenario_definition = _build_scenario_definition(chemical_identity, population_profile)
    route_dose_estimate = _build_route_dose_estimate(
        chemical_identity=chemical_identity,
        population_profile=population_profile,
        summary=translation_summary,
    )

    scenario_definition_snapshot = scenario_definition.model_dump(mode="json", by_alias=True)
    route_dose_snapshot = route_dose_estimate.model_dump(mode="json", by_alias=True)
    source_refs = [*source_evidence.get("upstreamArtifactRefs", [])]
    route_hint = (
        _find_identifier(source_evidence, "route_hint") or "soil_contact_or_crop_uptake_precursor"
    )
    time_window_mode = _find_identifier(source_evidence, "time_window_mode") or "steady_state"
    source_scenario_id = (
        _find_identifier(source_evidence, "scenario_id") or "fate-environmental-scenario-001"
    )

    evidence_item = {
        "originalId": "exp-fate-soil-001",
        "evidenceClass": "exposure",
        "sourceModule": "exposure_ingress_v1",
        "provenance": _provenance(
            tool_run_id="exp-fate-soil-001-run",
            source_hash_value={
                "routeDoseEstimate": route_dose_snapshot,
                "sourceConcentrationEvidence": source_evidence,
            },
        ),
        "endpointFamily": "environmental_oral_external_dose",
        "biologicalLevel": "organism",
        "methodMaturity": "governed_concentration_to_intake_bridge",
        "methodDescription": (
            "Agricultural-soil concentration-to-intake screening bridge derived from Fate governed "
            "handoff output with explicit soil-ingestion assumptions."
        ),
        "studyIdentifiers": [
            {"identifierType": "scenario_definition_id", "identifierValue": SCENARIO_DEFINITION_ID},
            {"identifierType": "route_dose_artifact_id", "identifierValue": ROUTE_DOSE_ARTIFACT_ID},
            {"identifierType": "source_bundle_id", "identifierValue": source_bundle["bundleId"]},
            {"identifierType": "source_scenario_id", "identifierValue": source_scenario_id},
            {
                "identifierType": "source_concentration_surface_id",
                "identifierValue": SOURCE_SURFACE_ARTIFACT_ID,
            },
            {"identifierType": "pathway_semantics", "identifierValue": "concentration_to_intake"},
            {"identifierType": "route_hint", "identifierValue": route_hint},
            {
                "identifierType": "route_mechanism",
                "identifierValue": "soil_contact_concentration_to_intake",
            },
            {"identifierType": "time_window_mode", "identifierValue": time_window_mode},
        ],
        "schemaVersion": SCHEMA_VERSION,
        "exposureMetric": "external_dose_screening",
        "exposureScenario": "environmental_media_oral_screening",
        "aggregateExposure": False,
        "sourceScenarioId": SCENARIO_DEFINITION_ID,
        "route": "oral",
        "productCategory": "environmental_soil_ingestion_screening",
        "populationGroup": population_profile.population_group,
        "region": population_profile.region,
        "intendedUseFamily": "environmental",
        "oralExposureContext": "environmental_media",
        "doseValue": route_dose_estimate.dose.value,
        "doseUnit": route_dose_estimate.dose.unit.value,
        "routeMetricKeys": [
            "soil_ingestion_mg_per_day",
            "events_per_day",
            "external_mass_mg_per_day",
            "agricultural_soil_concentration_mg_per_kg",
            "source_concentration_surface_ids",
        ],
        "upstreamArtifactRefs": [
            _typed_ref(
                object_type_ref="ExposureScenarioDefinition",
                artifact_id=SCENARIO_DEFINITION_ID,
                retrieval_endpoint="exposure-scenario://cross-suite/fate-soil-oral/scenario-definition",
                cached_snapshot=scenario_definition_snapshot,
            ),
            _typed_ref(
                object_type_ref="RouteDoseEstimate",
                artifact_id=ROUTE_DOSE_ARTIFACT_ID,
                retrieval_endpoint="exposure-scenario://cross-suite/fate-soil-oral/route-dose",
                cached_snapshot=route_dose_snapshot,
            ),
            *source_refs,
        ],
    }

    claim_item = {
        "originalId": "exp-fate-soil-claim-001",
        "claimText": (
            "Agricultural-soil concentration-to-intake bridge preserves bounded environmental "
            f"oral context at {route_dose_estimate.dose.value:.15f} mg/kg-day."
        ),
        "claimType": "qualitative",
        "supportStatus": "supports",
        "confidence": "moderate",
        "evidenceObjectIds": [evidence_item["originalId"]],
        "lineOfEvidenceId": "loe-fate-soil-oral-bridge",
        "rationale": (
            f"{source_claim['claimText']} The exposure bridge converts "
            "agricultural-soil concentration into an external oral dose using explicit "
            "soil-ingestion assumptions and preserves the upstream concentration "
            "surface lineage while leaving crop uptake unresolved."
        ),
        "provenance": _provenance(
            tool_run_id="exp-fate-soil-claim-001-run",
            source_hash_value={
                "evidenceObjectId": evidence_item["originalId"],
                "routeDoseValue": route_dose_estimate.dose.value,
            },
        ),
        "applicabilityRecordId": "exp-fate-soil-app-001",
    }

    applicability_item = {
        "originalId": "exp-fate-soil-app-001",
        "evidenceClass": "exposure",
        "intendedUse": "bounded_environmental_oral_screening",
        "dimensionAssessments": [
            {
                "dimension": "exposure_metric",
                "status": "direct",
                "rationale": (
                    "The bridge emits an explicit external dose in mg/kg-day derived from the "
                    "agricultural-soil concentration surface."
                ),
                "evidenceValue": "mg/kg-day",
                "targetValue": "mg/kg-day",
            },
            {
                "dimension": "route",
                "status": "direct",
                "rationale": (
                    "The soil-contact branch of the route hint has been translated "
                    "into an explicit oral screening route."
                ),
                "evidenceValue": "oral",
                "targetValue": "oral",
            },
            {
                "dimension": "matrix",
                "status": "partial",
                "rationale": (
                    "The bridge still represents agricultural-soil environmental "
                    "context and should not be mistaken for crop uptake or "
                    "food-mediated residue intake."
                ),
                "bridgingRationale": source_applicability["dimensionAssessments"][1]["rationale"],
                "evidenceValue": "agricultural_soil",
                "targetValue": "environmental_media_oral_screening",
            },
        ],
        "overallStatus": "partial",
        "materiality": "material",
        "affectedObjectIds": [evidence_item["originalId"]],
        "provenance": _provenance(
            tool_run_id="exp-fate-soil-app-001-run",
            source_hash_value={
                "sourceApplicability": source_applicability,
                "translationSummary": translation_summary,
            },
        ),
    }

    uncertainty_item = {
        "originalId": "exp-fate-soil-unc-001",
        "uncertaintyClass": "comparability_indirectness",
        "burdenLevel": "moderate",
        "affectedObjectIds": [evidence_item["originalId"]],
        "rationale": (
            "External dose depends on explicit screening assumptions for soil ingestion "
            "and body weight, while the upstream agricultural-soil concentration remains "
            "environmental-media context rather than crop uptake or food-mediated intake."
        ),
        "reducibility": "partially_reducible",
        "directionality": "bidirectional",
        "mitigationPath": (
            "Replace screening defaults with population-specific soil-ingestion parameters or "
            "a dedicated crop-uptake / food-residue workflow when available."
        ),
        "provenance": _provenance(
            tool_run_id="exp-fate-soil-unc-001-run",
            source_hash_value={
                "sourceUncertainty": source_uncertainty,
                "translationSummary": translation_summary,
            },
        ),
    }

    link_item = {
        "originalId": "exp-fate-soil-link-001",
        "sourceId": evidence_item["originalId"],
        "sourceType": "evidence",
        "targetId": claim_item["originalId"],
        "targetType": "claim",
        "relationType": "supports",
        "rationale": (
            "The translated soil-contact oral screening dose directly supports the bridge claim."
        ),
        "strength": "direct",
        "bidirectional": False,
        "provenance": _provenance(
            tool_run_id="exp-fate-soil-link-001-run",
            source_hash_value={
                "sourceId": evidence_item["originalId"],
                "targetId": claim_item["originalId"],
            },
        ),
    }

    return {
        "sourceFormat": "structured_json_bundle",
        "sourceVersion": SOURCE_VERSION,
        "bundleId": BUNDLE_ID,
        "schemaVersion": SCHEMA_VERSION,
        "createdAt": DETERMINISTIC_GENERATED_AT,
        "createdBy": CREATED_BY,
        "targetConsumer": "woe_ngra",
        "evidenceItems": [evidence_item],
        "claimItems": [claim_item],
        "linkItems": [link_item],
        "applicabilityItems": [applicability_item],
        "uncertaintyItems": [uncertainty_item],
    }


def write_fate_soil_oral_woe_roundtrip_bundle(
    path: Path = WOE_ROUNDTRIP_FIXTURE_PATH,
) -> dict[str, Any]:
    payload = build_fate_soil_oral_woe_roundtrip_bundle()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8")
    return payload
