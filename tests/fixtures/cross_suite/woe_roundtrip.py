"""Deterministic Direct-Use Exposure -> WoE round-trip fixture builder."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.integrations import build_pbpk_external_import_package
from exposure_scenario_mcp.models import (
    ExportPbpkExternalImportBundleRequest,
    ExportPbpkScenarioInputRequest,
    ExposureScenario,
    ExposureScenarioRequest,
)
from exposure_scenario_mcp.package_metadata import CURRENT_VERSION
from exposure_scenario_mcp.plugins import InhalationScreeningPlugin, ScreeningScenarioPlugin
from exposure_scenario_mcp.runtime import PluginRegistry, ScenarioEngine, export_pbpk_input

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
BENCHMARK_FIXTURE_PATH = WORKSPACE_ROOT / "tests" / "fixtures" / "benchmark_cases.json"
WOE_ROUNDTRIP_FIXTURE_PATH = (
    WORKSPACE_ROOT
    / "tests"
    / "fixtures"
    / "cross_suite"
    / "woe_ngra"
    / "direct_use_exposure_handoff.v1.1.0.json"
)
WOE_SYNC_TARGET_PATH = (
    WORKSPACE_ROOT.parent
    / "WoE_NGRA_Synthesis_MCP"
    / "src"
    / "integration"
    / "__fixtures__"
    / "direct-use-exposure-woe-roundtrip.bundle.json"
)

DETERMINISTIC_GENERATED_AT = "2026-04-21T12:00:00.000Z"
SOURCE_VERSION = "1.1.0"
SCHEMA_VERSION = "1.1.0"
BUNDLE_ID = "direct-use-exposure-handoff-001"
CREATED_BY = "direct-use-exposure-cross-suite-fixture-builder"
PRODUCER_MODULE = "direct_use_exposure"

CASE_CONFIGS = (
    {
        "case_id": "oral_tcm_medicinal_direct_use_screening",
        "evidence_id": "exp-direct-use-medicinal-001",
        "claim_id": "exp-direct-use-medicinal-claim-001",
        "link_id": "exp-direct-use-medicinal-link-001",
        "applicability_id": "exp-direct-use-medicinal-app-001",
        "uncertainty_id": "exp-direct-use-medicinal-unc-001",
        "scenario_id": "exp-direct-use-medicinal-scenario-001",
        "line_of_evidence_id": "loe-direct-use-medicinal",
        "summary_label": "direct_use_medicinal",
    },
    {
        "case_id": "oral_botanical_supplement_direct_use_screening",
        "evidence_id": "exp-direct-use-supplement-001",
        "claim_id": "exp-direct-use-supplement-claim-001",
        "link_id": "exp-direct-use-supplement-link-001",
        "applicability_id": "exp-direct-use-supplement-app-001",
        "uncertainty_id": "exp-direct-use-supplement-unc-001",
        "scenario_id": "exp-direct-use-supplement-scenario-001",
        "line_of_evidence_id": "loe-direct-use-supplement",
        "summary_label": "direct_use_supplement",
    },
)


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


def _build_engine() -> ScenarioEngine:
    registry = PluginRegistry()
    registry.register(ScreeningScenarioPlugin())
    registry.register(InhalationScreeningPlugin())
    return ScenarioEngine(registry=registry, defaults_registry=DefaultsRegistry.load())


def _load_benchmark_case(case_id: str) -> dict[str, Any]:
    payload = json.loads(BENCHMARK_FIXTURE_PATH.read_text(encoding="utf-8"))
    for case in payload["cases"]:
        if case["id"] == case_id:
            return case
    raise KeyError(f"Unknown benchmark case: {case_id}")


def _freeze_scenario(scenario: ExposureScenario, *, scenario_id: str) -> ExposureScenario:
    return scenario.model_copy(
        update={
            "scenario_id": scenario_id,
            "provenance": scenario.provenance.model_copy(
                update={"generated_at": DETERMINISTIC_GENERATED_AT}
            ),
        },
        deep=True,
    )


def _typed_ref(
    *,
    object_type_ref: str,
    artifact_id: str,
    cached_snapshot: dict[str, Any],
) -> dict[str, Any]:
    return {
        "objectType": "typedHandoffRef",
        "schemaVersion": "1.1.0",
        "objectTypeRef": object_type_ref,
        "cachedSnapshot": cached_snapshot,
        "artifactId": artifact_id,
        "producerModule": PRODUCER_MODULE,
        "producerVersion": CURRENT_VERSION,
        "integrityHash": f"sha256:{_hash_value(cached_snapshot)}",
    }


def _source_hash(snapshot: dict[str, Any]) -> str:
    return _hash_value(snapshot)


def _evidence_provenance(tool_run_id: str, scenario_snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "toolRunId": tool_run_id,
        "createdAt": DETERMINISTIC_GENERATED_AT,
        "createdBy": CREATED_BY,
        "sourceHashes": [
            {
                "algorithm": "sha256",
                "value": _source_hash(scenario_snapshot),
            }
        ],
    }


def build_direct_use_woe_roundtrip_bundle() -> dict[str, Any]:
    engine = _build_engine()
    evidence_items: list[dict[str, Any]] = []
    claim_items: list[dict[str, Any]] = []
    link_items: list[dict[str, Any]] = []
    applicability_items: list[dict[str, Any]] = []
    uncertainty_items: list[dict[str, Any]] = []

    for config in CASE_CONFIGS:
        case = _load_benchmark_case(config["case_id"])
        request = ExposureScenarioRequest(**case["request"])
        scenario = _freeze_scenario(engine.build(request), scenario_id=config["scenario_id"])
        pbpk_input = export_pbpk_input(
            ExportPbpkScenarioInputRequest(scenario=scenario),
            DefaultsRegistry.load(),
            generated_at=DETERMINISTIC_GENERATED_AT,
        )
        pbpk_package = build_pbpk_external_import_package(
            ExportPbpkExternalImportBundleRequest(scenario=scenario),
            generated_at=DETERMINISTIC_GENERATED_AT,
        )

        scenario_snapshot = scenario.model_dump(mode="json", by_alias=True)
        pbpk_input_snapshot = pbpk_input.model_dump(mode="json", by_alias=True)
        pbpk_package_snapshot = pbpk_package.model_dump(mode="json", by_alias=True)
        tool_run_id = f"{config['evidence_id']}-run"
        oral_context = (
            scenario.product_use_profile.oral_exposure_context.value
            if scenario.product_use_profile.oral_exposure_context is not None
            else None
        )
        intended_use_family = (
            scenario.product_use_profile.intended_use_family.value
            if scenario.product_use_profile.intended_use_family is not None
            else None
        )
        route_metric_keys = sorted(scenario.route_metrics.keys())
        claim_text = (
            f"{scenario.product_use_profile.product_name} preserves {config['summary_label']} "
            f"screening context at {scenario.external_dose.value:.8f} "
            f"{scenario.external_dose.unit.value}."
        )
        uncertainty_rationale = (
            "Direct-use screening remains bounded by explicit dosage-unit and ingestion "
            "assumptions and must not be reinterpreted as food-mediated intake."
        )

        evidence_items.append(
            {
                "originalId": config["evidence_id"],
                "evidenceClass": "exposure",
                "sourceModule": "exposure_ingress_v1",
                "provenance": _evidence_provenance(tool_run_id, scenario_snapshot),
                "endpointFamily": "consumer_exposure",
                "biologicalLevel": "organism",
                "methodMaturity": "deterministic_screening",
                "methodDescription": case["description"],
                "studyIdentifiers": [
                    {
                        "identifierType": "benchmark_case_id",
                        "identifierValue": config["case_id"],
                    },
                    {
                        "identifierType": "scenario_id",
                        "identifierValue": scenario.scenario_id,
                    },
                    {
                        "identifierType": "route_mechanism",
                        "identifierValue": "oral_direct_intake",
                    },
                ],
                "schemaVersion": SCHEMA_VERSION,
                "exposureMetric": scenario.external_dose.metric,
                "exposureScenario": "oral_direct_intake",
                "aggregateExposure": False,
                "sourceScenarioId": scenario.scenario_id,
                "route": scenario.route.value,
                "productName": scenario.product_use_profile.product_name,
                "productCategory": scenario.product_use_profile.product_category,
                "populationGroup": scenario.population_profile.population_group,
                "region": scenario.population_profile.region,
                "intendedUseFamily": intended_use_family,
                "oralExposureContext": oral_context,
                "doseValue": scenario.external_dose.value,
                "doseUnit": scenario.external_dose.unit.value,
                "routeMetricKeys": route_metric_keys,
                "upstreamArtifactRefs": [
                    _typed_ref(
                        object_type_ref="ExposureScenario",
                        artifact_id=scenario.scenario_id,
                        cached_snapshot=scenario_snapshot,
                    ),
                    _typed_ref(
                        object_type_ref="PbpkScenarioInput",
                        artifact_id=f"pbpk-input:{scenario.scenario_id}",
                        cached_snapshot=pbpk_input_snapshot,
                    ),
                    _typed_ref(
                        object_type_ref="PbpkExternalImportPackage",
                        artifact_id=f"pbpk-package:{scenario.scenario_id}",
                        cached_snapshot=pbpk_package_snapshot,
                    ),
                ],
            }
        )

        claim_items.append(
            {
                "originalId": config["claim_id"],
                "claimText": claim_text,
                "claimType": "quantitative",
                "supportStatus": "supports",
                "confidence": "moderate",
                "evidenceObjectIds": [config["evidence_id"]],
                "lineOfEvidenceId": config["line_of_evidence_id"],
                "rationale": (
                    "Dose arithmetic is deterministic and the oral context remains product-centric "
                    "rather than food-mediated."
                ),
                "provenance": _evidence_provenance(
                    f"{config['claim_id']}-run",
                    scenario_snapshot,
                ),
            }
        )

        link_items.append(
            {
                "originalId": config["link_id"],
                "sourceId": config["evidence_id"],
                "sourceType": "evidence",
                "targetId": config["claim_id"],
                "targetType": "claim",
                "relationType": "supports",
                "rationale": (
                    "The direct-use exposure scenario directly supports the bounded oral "
                    "exposure claim."
                ),
                "strength": "direct",
                "bidirectional": False,
                "provenance": _evidence_provenance(
                    f"{config['link_id']}-run",
                    scenario_snapshot,
                ),
            }
        )

        applicability_items.append(
            {
                "originalId": config["applicability_id"],
                "evidenceClass": "exposure",
                "intendedUse": "woe_ngra_direct_use_exposure",
                "dimensionAssessments": [
                    {
                        "dimension": "route",
                        "status": "direct",
                        "rationale": (
                            "Oral route is explicit and matches the direct-use intake lane."
                        ),
                        "evidenceValue": scenario.route.value,
                        "targetValue": "oral",
                    },
                    {
                        "dimension": "method_domain",
                        "status": "direct",
                        "rationale": "The producer preserved the intended use family explicitly.",
                        "evidenceValue": intended_use_family,
                        "targetValue": intended_use_family,
                    },
                    {
                        "dimension": "matrix",
                        "status": "direct",
                        "rationale": (
                            "The oral context remains product-centric direct use and must not be "
                            "silently reclassified as food-mediated intake."
                        ),
                        "evidenceValue": oral_context,
                        "targetValue": oral_context,
                    },
                ],
                "overallStatus": "direct",
                "materiality": "material",
                "affectedObjectIds": [config["evidence_id"]],
                "provenance": _evidence_provenance(
                    f"{config['applicability_id']}-run",
                    scenario_snapshot,
                ),
            }
        )

        uncertainty_items.append(
            {
                "originalId": config["uncertainty_id"],
                "uncertaintyClass": "policy_default",
                "burdenLevel": "moderate",
                "affectedObjectIds": [config["evidence_id"]],
                "rationale": uncertainty_rationale,
                "reducibility": "partially_reducible",
                "directionality": "unknown",
                "mitigationPath": (
                    "Escalate to product-specific composition or regimen evidence, or pass the "
                    "screening context into PBPK/BER rather than interpreting it as final intake."
                ),
                "provenance": _evidence_provenance(
                    f"{config['uncertainty_id']}-run",
                    scenario_snapshot,
                ),
            }
        )

    return _sorted_json(
        {
            "sourceFormat": "structured_json_bundle",
            "sourceVersion": SOURCE_VERSION,
            "bundleId": BUNDLE_ID,
            "schemaVersion": SCHEMA_VERSION,
            "createdAt": DETERMINISTIC_GENERATED_AT,
            "createdBy": CREATED_BY,
            "evidenceItems": evidence_items,
            "claimItems": claim_items,
            "linkItems": link_items,
            "applicabilityItems": applicability_items,
            "uncertaintyItems": uncertainty_items,
        }
    )
