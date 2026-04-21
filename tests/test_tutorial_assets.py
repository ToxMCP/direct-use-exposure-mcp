from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate

REPO_ROOT = Path(__file__).resolve().parents[1]
TUTORIAL_PATH = REPO_ROOT / "docs" / "tutorials" / "regulatory_screening_walkthrough.md"
REQUEST_PATH = REPO_ROOT / "schemas" / "examples" / "screening_dermal_request.json"
RESULT_PATH = REPO_ROOT / "schemas" / "examples" / "screening_dermal_scenario.json"
REQUEST_SCHEMA_PATH = REPO_ROOT / "schemas" / "exposureScenarioRequest.v1.json"
RESULT_SCHEMA_PATH = REPO_ROOT / "schemas" / "exposureScenario.v1.json"


def test_guided_tutorial_links_checked_in_examples() -> None:
    tutorial = TUTORIAL_PATH.read_text(encoding="utf-8")

    assert "schemas/examples/screening_dermal_request.json" in tutorial
    assert "schemas/examples/screening_dermal_scenario.json" in tutorial


def test_guided_tutorial_examples_validate_against_public_schemas() -> None:
    request_schema = json.loads(REQUEST_SCHEMA_PATH.read_text(encoding="utf-8"))
    result_schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    request_payload = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
    result_payload = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    validate(instance=request_payload, schema=request_schema)
    validate(instance=result_payload, schema=result_schema)
