"""Generate JSON Schemas, examples, contract manifests, and release metadata."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from exposure_scenario_mcp.contracts import (
    build_contract_manifest,
    build_examples,
    build_release_metadata_report,
    schema_payloads,
)
from exposure_scenario_mcp.defaults import DEFAULTS_REPO_RELATIVE_PATH, DefaultsRegistry
from exposure_scenario_mcp.guidance import release_notes_markdown
from exposure_scenario_mcp.package_metadata import (
    CURRENT_RELEASE_METADATA_RELATIVE_PATH,
    CURRENT_RELEASE_NOTES_RELATIVE_PATH,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "schemas"
EXAMPLES_DIR = SCHEMA_DIR / "examples"
DOC_SCHEMA_DIR = REPO_ROOT / "docs" / "contracts" / "schemas"
CONTRACT_MANIFEST_PATH = REPO_ROOT / "docs" / "contracts" / "contract_manifest.json"
DEFAULTS_MANIFEST_PATH = REPO_ROOT / "defaults" / "manifest.json"
RELEASE_METADATA_PATH = REPO_ROOT / CURRENT_RELEASE_METADATA_RELATIVE_PATH
RELEASE_NOTES_PATH = REPO_ROOT / CURRENT_RELEASE_NOTES_RELATIVE_PATH
READONLY_EVAL_PATH = REPO_ROOT / "evals" / "exposure_scenario_mcp_readonly.xml"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _readonly_eval_bundle(
    *,
    defaults_manifest: dict,
    examples: dict[str, dict],
    manifest: dict,
) -> str:
    inhalation_request = examples["inhalation_request"]
    inhalation_scenario = examples["inhalation_scenario"]
    aggregate_summary = examples["aggregate_summary"]
    comparison_record = examples["comparison_record"]
    jurisdictional_comparison = examples["jurisdictional_comparison_result"]

    route_totals = {
        item["route"]: item["total_dose"]["value"]
        for item in aggregate_summary["per_route_totals"]
    }
    dominant_route = max(route_totals.items(), key=lambda item: item[1])[0]
    comparison_direction = "increase" if comparison_record["absolute_delta"] > 0 else "decrease"

    qa_pairs = [
        (
            "Inspect the contract manifest and the example dermal screening scenario. "
            "What exact canonical unit is used for the primary external dose? Answer with "
            "the unit string only.",
            "mg/kg-day",
        ),
        (
            "Using the example inhalation request and the corresponding inhalation scenario "
            "output, what room volume is used for the screening calculation? Respond with "
            "the numeric value only.",
            str(inhalation_request["product_use_profile"]["room_volume_m3"]),
        ),
        (
            "Read the defaults manifest or any example provenance bundle. What defaults "
            "pack version is in force for this server? Answer exactly.",
            defaults_manifest["defaults_version"],
        ),
        (
            "From the example inhalation scenario, what is the average air concentration "
            "value? Respond with the numeric value only and keep all shown decimal places.",
            str(inhalation_scenario["route_metrics"]["average_air_concentration_mg_per_m3"]),
        ),
        (
            "Look at the aggregate summary example and determine which route contributes the "
            "larger route-wise total. Answer with one of dermal, oral, or inhalation.",
            dominant_route,
        ),
        (
            "Count the public tools declared in the machine-readable contract manifest. "
            "Respond with the number only.",
            str(len(manifest["tools"])),
        ),
        (
            "Compare the dermal baseline and refined example scenarios using the comparison "
            "record. Did the comparison dose increase or decrease relative to baseline? "
            "Answer with increase or decrease only.",
            comparison_direction,
        ),
        (
            "Inspect the PBPK export example and the contract manifest. Which exact schema "
            "name describes the PBPK export response object? Answer exactly.",
            "pbpkScenarioInput.v1",
        ),
        (
            "In the dermal screening example, which assumption name provides the denominator "
            "used to normalize the daily external dose? Answer with the assumption name only.",
            "body_weight_kg",
        ),
        (
            "Using the comparison example, identify the changed assumption that governs "
            "product-to-skin transfer rather than retention. Answer with the exact assumption "
            "name only.",
            "transfer_efficiency",
        ),
        (
            "Inspect the contract manifest. What is the exact tool name for comparing the same "
            "scenario across multiple jurisdictions? Answer exactly.",
            "exposure_compare_jurisdictional_scenarios",
        ),
        (
            "Using the jurisdictional comparison example, which jurisdiction yields the lower "
            "external dose: global or china? Answer with the jurisdiction name only.",
            jurisdictional_comparison["doseRange"]["minimumJurisdiction"],
        ),
        (
            "From the jurisdictional comparison example, name the assumption that is the "
            "primary variance driver between global and china. Answer with the exact "
            "assumption name only.",
            jurisdictional_comparison["varianceDrivers"][0]["assumptionName"],
        ),
    ]

    root = ET.Element("evaluation")
    for question, answer in qa_pairs:
        pair = ET.SubElement(root, "qa_pair")
        ET.SubElement(pair, "question").text = question
        ET.SubElement(pair, "answer").text = answer
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def main() -> None:
    defaults_registry = DefaultsRegistry.load()

    for schema_name, payload in schema_payloads().items():
        _write_json(SCHEMA_DIR / f"{schema_name}.json", payload)
        _write_json(DOC_SCHEMA_DIR / f"{schema_name}.json", payload)

    examples = build_examples()
    for example_name, payload in examples.items():
        _write_json(EXAMPLES_DIR / f"{example_name}.json", payload)

    manifest = build_contract_manifest(defaults_registry).model_dump(mode="json")
    _write_json(CONTRACT_MANIFEST_PATH, manifest)
    release_metadata = build_release_metadata_report(defaults_registry).model_dump(
        mode="json", by_alias=True
    )
    _write_json(RELEASE_METADATA_PATH, release_metadata)
    defaults_manifest = {
        **defaults_registry.manifest(),
        "defaults_file": str(DEFAULTS_REPO_RELATIVE_PATH),
    }
    _write_json(DEFAULTS_MANIFEST_PATH, defaults_manifest)
    _write_text(
        RELEASE_NOTES_PATH,
        release_notes_markdown(build_release_metadata_report(defaults_registry)).rstrip() + "\n",
    )
    _write_text(
        READONLY_EVAL_PATH,
        _readonly_eval_bundle(
            defaults_manifest=defaults_manifest,
            examples=examples,
            manifest=manifest,
        )
        + "\n",
    )


if __name__ == "__main__":
    main()
