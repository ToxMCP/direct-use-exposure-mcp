"""Validate that hardcoded eval answers still match the current server surface."""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.server import create_mcp_server

REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_PATH = REPO_ROOT / "evals" / "exposure_scenario_mcp_readonly.xml"
CONTRACT_MANIFEST_PATH = REPO_ROOT / "docs" / "contracts" / "contract_manifest.json"


def _load_eval_answers() -> dict[str, str]:
    tree = ET.parse(EVAL_PATH)  # noqa: S314
    root = tree.getroot()
    answers: dict[str, str] = {}
    for qa in root.findall("qa_pair"):
        question = qa.find("question")
        answer = qa.find("answer")
        if question is not None and answer is not None:
            answers[question.text.strip() if question.text else ""] = (
                answer.text.strip() if answer.text else ""
            )
    return answers


def _answer_for_keyword(answers: dict[str, str], keyword: str) -> str | None:
    for q, a in answers.items():
        if keyword in q:
            return a
    return None


def main() -> int:
    errors: list[str] = []
    answers = _load_eval_answers()

    # 1. Defaults version drift.
    registry = DefaultsRegistry.load()
    expected_defaults = _answer_for_keyword(answers, "defaults pack version")
    if expected_defaults != registry.version:
        errors.append(
            f"Eval defaults version mismatch: eval={expected_defaults} current={registry.version}"
        )

    # 2. Tool count drift.
    manifest = json.loads(CONTRACT_MANIFEST_PATH.read_text(encoding="utf-8"))
    actual_tools = len(manifest["tools"])
    expected_tools = _answer_for_keyword(answers, "Count the public tools")
    if expected_tools is not None and int(expected_tools) != actual_tools:
        errors.append(f"Eval tool count mismatch: eval={expected_tools} current={actual_tools}")

    # 3. Server boot and verification check.
    server = create_mcp_server()
    if server is None:
        errors.append("Server failed to boot during eval validation.")

    if errors:
        print("Eval validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("Eval validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
