"""Exact arithmetic checks for pinned public exposure-review examples."""

from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "regulatory_exposure_review_cases.v1.json"


def test_tea_tree_oil_table_arithmetic_and_committee_correction() -> None:
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
    case = next(item for item in cases if item["id"] == "tea-tree-oil-2025")
    reconstructed = []
    for row in case["rows"]:
        sed = (
            Decimal(row["product_exposure_mg_kg_day"])
            * Decimal(row["concentration_percent"])
            / Decimal(100)
            * Decimal(row["absorption_percent"])
            / Decimal(100)
        )
        reconstructed.append(sed)
        assert sed.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) == Decimal(
            row["published_sed_mg_kg_day"]
        )
    assert sum(reconstructed) == Decimal("0.014309516")
    assert sum(Decimal(row["published_sed_mg_kg_day"]) for row in case["rows"]) == Decimal(
        case["committee_corrected_sum_mg_kg_day"]
    )
    assert Decimal(case["applicant_printed_sum_mg_kg_day"]) == Decimal("0.144")
    assert Decimal(case["committee_corrected_sum_mg_kg_day"]) == Decimal("0.0144")
    # Preserve different product-specific absorption evidence within one route.
    assert {row["absorption_percent"] for row in case["rows"]} == {"20.41", "12.84"}


def test_public_reference_scope_and_attribution_are_not_qualification_records() -> None:
    record = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert record["provenance"]["approval"] is None
    assert len(record["cases"]) == 4
    for case in record["cases"]:
        assert case["source"]["url"].startswith("https://health.ec.europa.eu/")
        assert len(bytes.fromhex(case["source"]["sha256"])) == 32
        assert case["source"]["printed_pages"]
        assert case["source"]["evidence_ids"]
        assert case["lesson"]
    by_id = {case["id"]: case for case in record["cases"]}
    assert by_id["kojic-acid-2012"]["source"]["status"] == "historical opinion"
    assert by_id["kojic-acid-2012"]["scope"]["dose_basis"] == "ug/cm2; not a generic fraction"
    assert by_id["cannabidiol-sensitisation-2026"]["scope"]["endpoint"] == "skin sensitisation"
