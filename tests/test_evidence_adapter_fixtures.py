from __future__ import annotations

import json
from pathlib import Path

from exposure_scenario_mcp.integrations import (
    CompToxChemicalRecord,
    ConsExpoEvidenceRecord,
    CosIngIngredientRecord,
    SccsCosmeticsEvidenceRecord,
    build_product_use_evidence_from_comptox,
    build_product_use_evidence_from_consexpo,
    build_product_use_evidence_from_cosing,
    build_product_use_evidence_from_sccs,
)

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "evidence_adapter_cases.json"


def test_evidence_adapter_fixtures_stay_normalizable() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    builders = {
        "comptox": (
            CompToxChemicalRecord,
            build_product_use_evidence_from_comptox,
        ),
        "consexpo": (
            ConsExpoEvidenceRecord,
            build_product_use_evidence_from_consexpo,
        ),
        "sccs": (
            SccsCosmeticsEvidenceRecord,
            build_product_use_evidence_from_sccs,
        ),
        "cosing": (
            CosIngIngredientRecord,
            build_product_use_evidence_from_cosing,
        ),
    }

    for case in fixture["cases"]:
        model, builder = builders[case["kind"]]
        evidence = builder(model(**case["input"]))
        for field_name, expected_value in case["expected"].items():
            assert getattr(evidence, field_name) == expected_value, case["kind"]
