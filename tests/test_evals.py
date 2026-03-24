from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.generate_contract_assets import main as generate_contract_assets

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULTS_MANIFEST_PATH = REPO_ROOT / "defaults" / "manifest.json"
EVAL_PATH = REPO_ROOT / "evals" / "exposure_scenario_mcp_readonly.xml"
EXAMPLES_DIR = REPO_ROOT / "schemas" / "examples"
MANIFEST_PATH = REPO_ROOT / "docs" / "contracts" / "contract_manifest.json"


def _answers() -> list[str]:
    tree = ET.parse(EVAL_PATH)
    return [answer.text or "" for answer in tree.getroot().iterfind("./qa_pair/answer")]


def test_eval_bundle_matches_current_examples_and_manifest() -> None:
    generate_contract_assets()
    answers = _answers()
    defaults_manifest = json.loads(DEFAULTS_MANIFEST_PATH.read_text(encoding="utf-8"))
    inhalation_request = json.loads(
        (EXAMPLES_DIR / "inhalation_request.json").read_text(encoding="utf-8")
    )
    inhalation_scenario = json.loads(
        (EXAMPLES_DIR / "inhalation_scenario.json").read_text(encoding="utf-8")
    )
    aggregate_summary = json.loads(
        (EXAMPLES_DIR / "aggregate_summary.json").read_text(encoding="utf-8")
    )
    comparison_record = json.loads(
        (EXAMPLES_DIR / "comparison_record.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    route_totals = {
        item["route"]: item["total_dose"]["value"] for item in aggregate_summary["per_route_totals"]
    }
    dominant_route = max(route_totals.items(), key=lambda item: item[1])[0]
    comparison_direction = "increase" if comparison_record["absolute_delta"] > 0 else "decrease"

    assert answers[0] == "mg/kg-day"
    assert answers[1] == str(inhalation_request["product_use_profile"]["room_volume_m3"])
    assert answers[2] == defaults_manifest["defaults_version"]
    assert answers[3] == str(
        inhalation_scenario["route_metrics"]["average_air_concentration_mg_per_m3"]
    )
    assert answers[4] == dominant_route
    assert answers[5] == str(len(manifest["tools"]))
    assert answers[6] == comparison_direction
    assert answers[7] == "pbpkScenarioInput.v1"
    assert answers[8] == "body_weight_kg"
    assert answers[9] == "transfer_efficiency"
