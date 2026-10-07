"""Boundary controls and real SDK2 exercise for the repository worksheet."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from scripts import run_exposure_review as runner
from scripts.exposure_review_models import OmittedSource, ReviewSources, ReviewWorksheet

ROOT = Path(__file__).resolve().parents[1]


def worksheet() -> ReviewWorksheet:
    raw = json.loads((ROOT / "examples/exposure-review/ehmc.v1.json").read_text())
    raw["scope"]["dose_basis"] = "external_mg_kg_day"
    raw["reference_cases"] = []
    raw["components"][0]["scope"] = raw["scope"].copy()
    return ReviewWorksheet.model_validate(raw)


def native() -> dict:
    return {
        "chemical_id": "review:EHMC",
        "external_dose": {"value": 1.66666667, "unit": "mg/kg-day"},
        "assumptions": [{"name": "body_weight_kg", "value": 60}],
        "population_profile": {"population_group": "adult", "region": "EU"},
        "product_use_profile": {"concentration_fraction": 0.1},
        "quality_flags": [],
    }


def codes(findings: list[dict]) -> set[str]:
    return {x["code"] for x in findings}


def test_compatible_deterministic_amount_is_only_worksheet_arithmetic() -> None:
    record = worksheet()
    assert runner.contribution(record.components[0], record, native(), {}) == ("1.66666667", [])
    record.components[0].non_detect = True
    record.components[0].concentration_upper_bound_fraction = "0.1"
    amount, findings = runner.contribution(record.components[0], record, native(), {})
    assert amount == "1.66666667"
    assert findings == []


@pytest.mark.parametrize(
    "field", ["material", "population", "region", "period", "duration", "endpoint"]
)
def test_scope_mismatches_do_not_join(field: str) -> None:
    record = worksheet()
    setattr(record.components[0].scope, field, "different")
    amount, findings = runner.contribution(record.components[0], record, native(), {})
    assert amount is None
    assert "worksheet_scope_mismatch" in codes(findings)


@pytest.mark.parametrize("role", ["alternative", "already_counted", "unknown"])
def test_nonadditive_roles_are_excluded(role: str) -> None:
    record = worksheet()
    record.components[0].role = role
    amount, findings = runner.contribution(record.components[0], record, native(), {})
    assert amount is None
    assert "worksheet_source_relationship_unresolved" in codes(findings)


def test_overlap_and_mixed_sensitivity_inputs_do_not_join() -> None:
    record = worksheet()
    other = record.components[0].model_copy(deep=True)
    other.id = "other"
    other.nature = "documented"
    record.components.append(other)
    component = record.components[0]
    component.overlap_with = ["other"]
    amount, findings = runner.contribution(component, record, native(), {})
    assert amount is None
    assert {
        "worksheet_source_relationship_unresolved",
        "worksheet_mixed_input_natures",
        "worksheet_independence_unreviewed",
    } <= codes(findings)


@pytest.mark.parametrize("statistic", ["mean", "marginal_p95", "unknown"])
def test_marginal_statistics_never_become_aggregate_p95(statistic: str) -> None:
    record = worksheet()
    record.components[0].dose_statistic = statistic
    amount, findings = runner.contribution(record.components[0], record, native(), {})
    assert amount is None
    assert "worksheet_statistic_not_additive" in codes(findings)


@pytest.mark.parametrize("bound", [None, "0", "-1", "NaN", "Infinity", "0.2"])
def test_non_detects_preserve_original_positive_bound(bound: str | None) -> None:
    record = worksheet()
    record.components[0].non_detect = True
    record.components[0].concentration_upper_bound_fraction = bound
    amount, findings = runner.contribution(record.components[0], record, native(), {})
    assert amount is None
    assert "worksheet_non_detect_bound_not_preserved" in codes(findings)


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("identity", "worksheet_identity_mismatch"),
        ("weight", "worksheet_denominator_mismatch"),
        ("population", "worksheet_population_mismatch"),
        ("units", "worksheet_dose_basis_unsupported"),
        ("error", "worksheet_producer_error"),
        ("negative", "worksheet_dose_invalid"),
    ],
)
def test_producer_correspondence_and_errors(mutation: str, expected: str) -> None:
    record = worksheet()
    payload = native()
    if mutation == "identity":
        payload["chemical_id"] = "other"
    elif mutation == "weight":
        payload["assumptions"][0]["value"] = 70
    elif mutation == "population":
        payload["population_profile"]["population_group"] = "child"
    elif mutation == "units":
        payload["external_dose"]["unit"] = "mg/application"
    elif mutation == "error":
        payload["quality_flags"] = [
            {"code": "unknown_original_code", "severity": "error", "message": "Retain me"}
        ]
    else:
        payload["external_dose"]["value"] = -1
    original = copy.deepcopy(payload)
    amount, findings = runner.contribution(record.components[0], record, payload, {})
    assert amount is None
    assert expected in codes(findings)
    assert payload == original
    assert all(x["priority"] and x["reopening_condition"] for x in findings)


def test_source_and_absorption_applicability_are_separate() -> None:
    record = worksheet()
    record.scope.dose_basis = "absorbed_mg_kg_day"
    record.components[0].scope.dose_basis = "absorbed_mg_kg_day"
    component = record.components[0]
    sources = {"ehmc-absorption-2025-corrigendum-2026": {"status": "verified"}}
    for applicability in ["unknown", "rejected"]:
        component.absorption.applicability = applicability
        amount, findings = runner.contribution(component, record, native(), sources)
        assert amount is None
        assert "worksheet_absorption_applicability_unresolved" in codes(findings)
    component.absorption.applicability = "reviewed"
    amount, findings = runner.contribution(component, record, native(), sources)
    assert amount is None
    assert "worksheet_absorption_appraisal_incomplete" in codes(findings)
    component.absorption.applicability = "published_reconstruction"
    amount, findings = runner.contribution(component, record, native(), {})
    assert amount is None
    assert "worksheet_absorption_source_unverified" in codes(findings)
    amount, findings = runner.contribution(component, record, native(), sources)
    assert Decimal(amount) == Decimal("1.66666667") * Decimal("0.0045")
    assert findings == []
    component.absorption.statistic = "p95"
    assert runner.contribution(component, record, native(), sources)[0] is None


@pytest.mark.parametrize(
    ("value", "unit"), [("101", "percent"), ("NaN", "percent"), ("-1", "fraction")]
)
def test_invalid_absorption_never_becomes_a_fraction(value: str, unit: str) -> None:
    with pytest.raises(ValueError, match="Absorption"):
        runner.selected_fraction(value, unit)


def test_missing_and_mismatched_sources_stay_visible(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "inputs").mkdir()
    raw = b"retained bytes\n"
    (tmp_path / "record.pdf").write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(runner, "catalogue", lambda: {"record": {"source": {"sha256": digest}}})
    good = runner.source_records(
        ReviewSources(
            schema_version="exposureReviewSources.v1",
            files={"record": "record.pdf", "unreviewed": "record.pdf"},
        ),
        tmp_path,
        tmp_path,
    )
    assert good["record"]["status"] == "verified"
    assert (tmp_path / "inputs" / f"source-{digest}.pdf").read_bytes() == raw
    assert good["unreviewed"]["status"] == "unreviewed_source_identifier"
    (tmp_path / "record.pdf").write_bytes(b"changed")
    bad = runner.source_records(
        ReviewSources(schema_version="exposureReviewSources.v1", files={"record": "record.pdf"}),
        tmp_path,
        tmp_path,
    )
    assert bad["record"]["status"] == "hash_mismatch"
    assert bad["oecd-tg-428-2004"]["status"] == "missing"


@pytest.mark.parametrize("value", ["-1", "NaN", "Infinity"])
def test_unknown_omissions_are_not_negative_or_nonfinite_bounds(value: str) -> None:
    with pytest.raises(ValidationError, match="finite and nonnegative"):
        OmittedSource(
            id="omission", description="unknown", upper_bound=value, reopening_condition="Review"
        )


def configs(tmp_path: Path, python: str = sys.executable) -> tuple[Path, Path]:
    servers = tmp_path / "servers.json"
    sources = tmp_path / "sources.json"
    servers.write_text(
        json.dumps(
            {
                "schema_version": "exposureReviewServers.v1",
                "exposure": {
                    "source_checkout": str(ROOT),
                    "python": python,
                    "expected_version": "0.3.2",
                },
            }
        )
    )
    sources.write_text(json.dumps({"schema_version": "exposureReviewSources.v1", "files": {}}))
    return servers, sources


def verify_manifest(output: Path) -> None:
    manifest = json.loads((output / "SHA256SUMS.json").read_text())
    for row in manifest["files"]:
        assert hashlib.sha256((output / row["path"]).read_bytes()).hexdigest() == row["sha256"]


def test_failed_server_preserves_inputs_diagnostics_and_refuses_reuse(tmp_path: Path) -> None:
    servers, sources = configs(tmp_path, "/missing/python")
    sheet = ROOT / "examples/exposure-review/ehmc.v1.json"
    output = tmp_path / "failed"
    assert runner.run(sheet, servers, sources, output) == 1
    assert (output / "inputs/worksheet.json").read_bytes() == sheet.read_bytes()
    failure = json.loads((output / "failure.json").read_text())
    assert failure["assessmentStopAuthorized"] is False
    verify_manifest(output)
    snapshot = (output / "SHA256SUMS.json").read_bytes()
    with pytest.raises(FileExistsError):
        runner.run(sheet, servers, sources, output)
    assert (output / "SHA256SUMS.json").read_bytes() == snapshot


def test_actual_sdk2_round_trip_and_stable_semantic_results(tmp_path: Path) -> None:
    servers, sources = configs(tmp_path)
    sheet = tmp_path / "worksheet.json"
    record = worksheet()
    record.components[0].check_pbpk_export = True
    sheet.write_text(record.model_dump_json(indent=2) + "\n")
    reports = []
    for name in ["first", "second"]:
        output = tmp_path / name
        assert runner.run(sheet, servers, sources, output) == 0
        report = json.loads((output / "report.json").read_text())
        assert report["approval"] is None
        assert report["assessmentStopAuthorized"] is False
        assert report["complete_aggregate_exposure"] is None
        assert Decimal(report["accounted_worksheet_subtotal"]) == Decimal("1.66666667")
        assert (output / "inputs/worksheet.json").read_bytes() == sheet.read_bytes()
        assert (output / "native-external-aggregate.json").is_file()
        assert (output / "hypothetical_cream-pbpk-response.json").is_file()
        exchanges = [
            json.loads(x) for x in (output / "sdk-exchanges.jsonl").read_text().splitlines()
        ]
        assert {x["method"] for x in exchanges} == {
            "list_tools",
            "list_resources",
            "read_resource",
            "call_tool",
        }
        assert json.loads((output / "server-preflight.json").read_text())["mcp"].startswith("2.")
        verify_manifest(output)
        reports.append((output / "semantic-results.json").read_bytes())
    assert reports[0] == reports[1]


def test_documented_inputs_need_sources_and_unknown_scope_is_visible() -> None:
    record = worksheet()
    record.components[0].nature = "documented"
    record.components[0].scope.period = "unknown"
    amount, findings = runner.contribution(record.components[0], record, native(), {})
    assert amount is None
    assert {"worksheet_documented_source_missing", "worksheet_scope_unresolved"} <= codes(findings)


def test_malformed_input_is_captured_and_sealed(tmp_path: Path) -> None:
    servers, sources = configs(tmp_path)
    sheet = tmp_path / "bad.json"
    sheet.write_bytes(b"{invalid JSON\n")
    output = tmp_path / "malformed"
    assert runner.run(sheet, servers, sources, output) == 1
    assert (output / "inputs/worksheet.json").read_bytes() == sheet.read_bytes()
    assert (output / "server-diagnostics.log").is_file()
    verify_manifest(output)


def test_missing_sources_block_actual_published_reconstruction(tmp_path: Path) -> None:
    servers, sources = configs(tmp_path)
    output = tmp_path / "missing-sources"
    assert (
        runner.run(ROOT / "examples/exposure-review/tea-tree-oil.v1.json", servers, sources, output)
        == 0
    )
    report = json.loads((output / "report.json").read_text())
    assert report["published_records"][0]["record"] is None
    assert report["accounted_worksheet_subtotal"] is None
    assert all(
        "worksheet_source_unverified" in codes(row["findings"]) for row in report["components"]
    )
    assert not (output / "native-external-aggregate.json").exists()
    # A new native code is surfaced verbatim, without invented clearance.
    report["components"][0]["producer_flags"].append(
        {"code": "novel_original_finding", "severity": "warning", "message": "Needs appraisal"}
    )
    rendered = runner.markdown(report)
    assert "novel_original_finding" in rendered
    assert "Needs appraisal" in rendered
    assert "an unmapped code remains visible" in rendered
    verify_manifest(output)


def test_all_example_payloads_have_explicit_retention_and_nature() -> None:
    for path in (ROOT / "examples/exposure-review").glob("*.v1.json"):
        raw = json.loads(path.read_text())
        if raw["schema_version"] != "exposureReviewWorksheet.v1":
            continue
        record = ReviewWorksheet.model_validate(raw)
        for component in record.components:
            assert component.nature in {"hypothetical", "illustrative_reconstruction"}
            product = component.producer_request["product_use_profile"]
            assert product["retention_factor"] == 1
            assert product["transfer_efficiency"] == 1
        assert record.omitted_sources[0].upper_bound is None
