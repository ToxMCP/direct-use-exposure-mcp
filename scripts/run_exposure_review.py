"""Reproduce source/applicability review using an isolated SDK2 Exposure server."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from decimal import Decimal, InvalidOperation
from importlib.metadata import version
from pathlib import Path
from typing import Any

import anyio
from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client

from scripts.exposure_review_models import (
    ReviewComponent,
    ReviewServers,
    ReviewSources,
    ReviewWorksheet,
)

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 50 * 1024 * 1024
METHODS = {
    "sccs-1647-22-corrigendum-2": {
        "sha256": "811c669b0211152a19433dda7d3517b480dd47b7fd9cbb64e5bbdeb91c7c6daa",
        "url": "https://health.ec.europa.eu/document/download/32a999f7-d820-496a-b659-d8c296cc99c1_en?filename=sccs_o_273_final.pdf",
        "version": "SCCS/1647/22, 12th revision, corrigendum 2, adopted 21 December 2023",
        "locator": "sections 3-2 and 3-3; documentary applicability review only",
    },
    "oecd-tg-428-2004": {
        "sha256": "4f16790b65a8e21b301da1eccf8856f4edadbdd8644d025e2137bf006ae576eb",
        "url": "https://www.oecd.org/content/dam/oecd/en/publications/reports/2004/11/test-no-428-skin-absorption-in-vitro-method_g1gh4b52/9789264071087-en.pdf",
        "version": "OECD TG 428, adopted 13 April 2004",
        "locator": (
            "paragraphs 14 and 18–22; applicability and reporting, not a new-assay requirement"
        ),
    },
}


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def capture(path: Path, destination: Path) -> bytes:
    if path.stat().st_size > LIMIT:
        raise ValueError(f"Input exceeds the {LIMIT}-byte capture limit: {path.name}")
    raw = path.read_bytes()
    destination.write_bytes(raw)
    return raw


def catalogue() -> dict[str, Any]:
    record = json.loads(
        (ROOT / "tests/fixtures/regulatory_exposure_review_cases.v1.json").read_text()
    )
    return {case["id"]: case for case in record["cases"]}


def source_records(config: ReviewSources, base: Path, output: Path) -> dict[str, Any]:
    expected = {key: value["source"] for key, value in catalogue().items()} | METHODS
    result = {}
    for key, metadata in expected.items():
        row = {"status": "missing", "expected": metadata}
        if key in config.files:
            path = (base / config.files[key]).resolve()
            try:
                raw = capture(path, output / "inputs" / ("source-" + metadata["sha256"] + ".pdf"))
                digest = hashlib.sha256(raw).hexdigest()
                row.update(
                    {
                        "status": "verified" if digest == metadata["sha256"] else "hash_mismatch",
                        "sha256": digest,
                        "bytes": len(raw),
                    }
                )
            except (OSError, ValueError) as error:
                row.update({"status": "unreadable", "error": str(error)})
        result[key] = row
    for key in set(config.files) - set(expected):
        result[key] = {
            "status": "unreviewed_source_identifier",
            "reopening_condition": (
                "Pin and review this source identifier in a separate catalogue update."
            ),
        }
    return result


def issue(code: str, condition: str, **context: Any) -> dict[str, Any]:
    return {
        "code": code,
        "action_family": "documentary_appraisal",
        "priority": "before_combining_or_transferring_exposure",
        "reopening_condition": condition,
        **context,
    }


def verified(ids: list[str], sources: dict[str, Any]) -> bool:
    return bool(ids) and all(sources.get(key, {}).get("status") == "verified" for key in ids)


def selected_fraction(value: str, unit: str) -> Decimal:
    number = Decimal(value)
    if not number.is_finite() or number < 0:
        raise ValueError("Absorption selection must be finite and nonnegative.")
    fraction = number / 100 if unit == "percent" else number
    if fraction > 1:
        raise ValueError("Absorption selection exceeds a fraction of one.")
    return fraction


def contribution(
    component: ReviewComponent,
    worksheet: ReviewWorksheet,
    native: dict[str, Any],
    sources: dict[str, Any],
) -> tuple[str | None, list[dict[str, Any]]]:
    findings = []
    if component.scope != worksheet.scope:
        findings.append(
            issue(
                "worksheet_scope_mismatch",
                (
                    "Rebuild corresponding material, population, period, duration, "
                    "endpoint and dose-basis components, or keep them separate."
                ),
            )
        )
    if len({x.nature for x in worksheet.components}) > 1:
        findings.append(
            issue(
                "worksheet_mixed_input_natures",
                "Separate documented, illustrative and hypothetical scenarios into distinct "
                "worksheets; sensitivity values do not close documented gaps.",
            )
        )
    if any(
        str(value).strip().lower() in {"unknown", "unresolved", "unspecified"}
        for value in component.scope.model_dump().values()
    ):
        findings.append(
            issue(
                "worksheet_scope_unresolved",
                "Recover the corresponding material, population, period, duration and dose "
                "basis before treating contributions as compatible.",
            )
        )
    if component.role != "additive" or component.overlap_with:
        findings.append(
            issue(
                "worksheet_source_relationship_unresolved",
                (
                    "Review event independence; exclude alternatives, already-counted "
                    "intake and unresolved overlap."
                ),
            )
        )
    if len(worksheet.components) > 1 and not component.independence_review:
        findings.append(
            issue(
                "worksheet_independence_unreviewed",
                "Record the source-supported reasoning for treating this event as independent.",
            )
        )
    if component.dose_statistic != "deterministic":
        findings.append(
            issue(
                "worksheet_statistic_not_additive",
                (
                    "Use compatible deterministic scenarios, or supply a separately "
                    "reviewed joint exposure method; marginal P95s are not summed."
                ),
            )
        )
    if component.source_ids and not verified(component.source_ids, sources):
        findings.append(
            issue(
                "worksheet_source_unverified",
                (
                    "Supply the correctly pinned source files and verify their "
                    "locators before relying on this reconstruction."
                ),
            )
        )
    if component.nature == "documented" and not component.source_ids:
        findings.append(
            issue(
                "worksheet_documented_source_missing",
                "Provide the pinned record supporting the documented inputs, or retain them "
                "as explicitly hypothetical arithmetic in a separate worksheet.",
            )
        )
    if native.get("chemical_id") != component.scope.chemical_id:
        findings.append(
            issue(
                "worksheet_identity_mismatch",
                (
                    "Resolve the ledger versus producer chemical identifier. No "
                    "structure or material identity is inferred."
                ),
            )
        )
    weights = [x["value"] for x in native.get("assumptions", []) if x["name"] == "body_weight_kg"]
    if (
        not weights
        or component.scope.body_weight_kg is None
        or any(x != component.scope.body_weight_kg for x in weights)
    ):
        findings.append(
            issue(
                "worksheet_denominator_mismatch",
                (
                    "Recover the original calculation denominator and corresponding "
                    "worksheet population."
                ),
            )
        )
    population = native.get("population_profile", {})
    if (
        population.get("population_group") != component.scope.population
        or population.get("region") != component.scope.region
    ):
        findings.append(
            issue(
                "worksheet_population_mismatch",
                (
                    "Preserve the actual producer population and region; a generic "
                    "cohort cannot replace a published cohort."
                ),
            )
        )
    if component.non_detect:
        try:
            bound = Decimal(component.concentration_upper_bound_fraction or "NaN")
            native_concentration = Decimal(
                str(native["product_use_profile"]["concentration_fraction"])
            )
            if not bound.is_finite() or not 0 < bound <= 1 or native_concentration != bound:
                raise ValueError(
                    "Non-detect requires the original positive upper-bound concentration."
                )
        except (InvalidOperation, KeyError, ValueError):
            findings.append(
                issue(
                    "worksheet_non_detect_bound_not_preserved",
                    (
                        "Use the documented positive analytical bound and corresponding "
                        "concentration input; do not substitute zero or infer future-lot "
                        "compliance."
                    ),
                )
            )
    flags = native.get("quality_flags", [])
    if any(x.get("severity") == "error" for x in flags):
        findings.append(
            issue(
                "worksheet_producer_error",
                "Resolve the original producer error findings; retain their codes and messages.",
            )
        )
    dose = native.get("external_dose", {})
    if dose.get("unit") != "mg/kg-day" or worksheet.scope.dose_basis not in {
        "external_mg_kg_day",
        "absorbed_mg_kg_day",
    }:
        findings.append(
            issue(
                "worksheet_dose_basis_unsupported",
                (
                    "Keep local skin/respiratory, per-application and systemic doses "
                    "separate; provide a reviewed derivation before changing basis."
                ),
            )
        )
    if findings:
        return None, findings
    amount = Decimal(str(dose["value"]))
    if not amount.is_finite() or amount < 0:
        return None, [issue("worksheet_dose_invalid", "Resolve the nonfinite or negative dose.")]
    if worksheet.scope.dose_basis == "absorbed_mg_kg_day":
        selection = component.absorption
        if (
            selection is None
            or selection.value is None
            or selection.applicability in {"unknown", "rejected"}
        ):
            return None, [
                issue(
                    "worksheet_absorption_applicability_unresolved",
                    (
                        "Appraise tested versus assessed material, formulation, "
                        "concentration, contact conditions and study quality before "
                        "selecting absorption."
                    ),
                )
            ]
        if not verified(selection.source_ids, sources):
            return None, [
                issue(
                    "worksheet_absorption_source_unverified",
                    (
                        "Supply the correctly hashed primary absorption record before "
                        "relying on its selected value."
                    ),
                )
            ]
        if selection.applicability == "reviewed" and not all(
            [
                selection.tested_material,
                selection.assessed_material,
                selection.tested_formulation,
                selection.assessed_formulation,
                selection.tested_concentration_percent,
                selection.contact_conditions,
                selection.study_model,
                selection.quality_appraisal,
            ]
        ):
            return None, [
                issue(
                    "worksheet_absorption_appraisal_incomplete",
                    "Record the tested/assessed material, formulation, concentration, contact, "
                    "study model and quality appraisal. A reviewed label alone is insufficient.",
                )
            ]
        if selection.statistic in {"p95", "unknown"}:
            return None, [
                issue(
                    "worksheet_absorption_statistic_unresolved",
                    (
                        "Preserve the source statistic; a P95 selection does not create a "
                        "joint population P95."
                    ),
                )
            ]
        try:
            amount *= selected_fraction(selection.value, selection.unit)
        except (InvalidOperation, ValueError):
            return None, [
                issue(
                    "worksheet_absorption_value_invalid",
                    (
                        "Recover the original percentage or fraction and its finite, "
                        "dimensionless conversion."
                    ),
                )
            ]
    return str(amount), []


class Exchanges:
    def __init__(self, output: Path):
        self.path = output / "sdk-exchanges.jsonl"

    async def invoke(self, client: Client, method: str, *args: Any) -> dict[str, Any]:
        record: dict[str, Any] = {"method": method, "arguments": args}
        try:
            result = await getattr(client, method)(*args)
            wire: dict[str, Any] = result.model_dump(mode="json", by_alias=True, exclude_none=True)
            record["response"] = wire
            return wire
        except Exception as error:
            record["error"] = {"type": type(error).__name__, "message": str(error)}
            raise
        finally:
            with self.path.open("a") as stream:
                stream.write(json.dumps(record, allow_nan=False) + "\n")


def resolve_path(value: str, config: Path) -> Path:
    return (config.parent / value).resolve()


def preflight(servers: ReviewServers, config: Path, output: Path) -> tuple[Path, Path]:
    server = servers.exposure
    checkout = resolve_path(server.source_checkout, config)
    # Preserve a virtual-environment interpreter path: resolving its symlink
    # selects the base interpreter and loses that environment's dependencies.
    python = Path(os.path.abspath(config.parent / server.python))
    if not (checkout / "src/exposure_scenario_mcp/__main__.py").is_file() or not python.is_file():
        raise ValueError(
            "Server configuration must identify an existing Exposure source "
            "checkout and Python interpreter."
        )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(checkout / "src")
    code = (
        "import sys,json,exposure_scenario_mcp; from importlib.metadata "
        "import version; "
        "print(json.dumps({'python':list(sys.version_info[:3]),'mcp':version('mcp'),'version':exposure_scenario_mcp.__version__,'module':exposure_scenario_mcp.__file__}))"
    )
    process = subprocess.run(  # noqa: S603 -- explicitly configured local Python, argument array
        [str(python), "-c", code], env=env, capture_output=True, text=True, timeout=20, check=False
    )  # noqa: S603
    (output / "preflight-diagnostics.log").write_text(process.stderr)
    if process.returncode:
        raise ValueError("Server Python preflight failed; see preflight-diagnostics.log.")
    result = json.loads(process.stdout)
    if (
        result["python"][:2] < [3, 12]
        or not result["mcp"].startswith("2.")
        or result["version"] != server.expected_version
    ):
        raise ValueError(
            f"Server requires Python >=3.12, SDK2 and expected package version: {result}"
        )
    Path(result["module"]).resolve().relative_to(checkout)
    git = shutil.which("git")
    if server.expected_commit is not None and not (checkout / ".git").exists():
        raise ValueError("An expected_commit requires a Git source checkout.")
    if git is None and server.expected_commit is not None:
        raise ValueError("Git is required to check expected_commit.")
    if git is not None and (checkout / ".git").exists():
        commit = subprocess.run(  # noqa: S603 -- resolved Git, read-only argument array
            [git, "-C", str(checkout), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()  # noqa: S603
        if server.expected_commit is not None and commit != server.expected_commit:
            raise ValueError("Server commit does not match the supplied expected_commit.")
        result["commit"] = commit
        status = subprocess.run(  # noqa: S603 -- resolved Git, read-only argument array
            [git, "-C", str(checkout), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout
        result["checkout_dirty"] = bool(status)
        if server.expected_commit is not None and status:
            raise ValueError("An expected_commit requires a clean checkout.")
    result["source_file_hashes"] = {
        str(path.relative_to(checkout)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((checkout / "src/exposure_scenario_mcp").rglob("*.py"))
    }
    write_json(output / "server-preflight.json", result)
    return checkout, python


async def execute(
    worksheet: ReviewWorksheet,
    servers: ReviewServers,
    server_config: Path,
    sources: dict[str, Any],
    output: Path,
) -> dict[str, Any]:
    checkout, python = preflight(servers, server_config, output)
    recorder = Exchanges(output)
    records: list[dict[str, Any]] = []
    native_additive: list[dict[str, Any]] = []
    params = StdioServerParameters(
        command=str(python),
        args=["-m", "exposure_scenario_mcp"],
        env={"PYTHONPATH": str(checkout / "src")},
        cwd=str(output),
    )
    with (output / "server-diagnostics.log").open("w") as diagnostics:
        async with Client(stdio_client(params, errlog=diagnostics)) as client:
            tools = await recorder.invoke(client, "list_tools")
            resources = await recorder.invoke(client, "list_resources")
            write_json(
                output / "discovered-contracts.json", {"tools": tools, "resources": resources}
            )
            names = {tool["name"] for tool in tools["tools"]}
            required = {x.producer_tool for x in worksheet.components} | {
                "exposure_build_aggregate_exposure_scenario"
            }
            if not required <= names:
                raise ValueError("Required producer contracts were not discovered.")
            for uri in ["defaults://manifest", "release://metadata-report"]:
                await recorder.invoke(client, "read_resource", uri)
            for component in worksheet.components:
                write_json(
                    output / "inputs" / (component.id + "-producer-request.json"),
                    component.producer_request,
                )
                wire = await recorder.invoke(
                    client,
                    "call_tool",
                    component.producer_tool,
                    {"params": component.producer_request},
                )
                write_json(output / (component.id + "-producer-response.json"), wire)
                if wire.get("isError"):
                    records.append(
                        {
                            "id": component.id,
                            "status": "producer_error",
                            "worksheet_contribution": None,
                            "findings": [
                                issue(
                                    "worksheet_producer_call_failed",
                                    "Resolve the original tool refusal recorded in this exchange.",
                                )
                            ],
                            "producer_refusal": wire,
                        }
                    )
                    continue
                native = wire["structuredContent"]
                amount, findings = contribution(component, worksheet, native, sources)
                if amount is not None:
                    native_additive.append(native)
                row = {
                    "id": component.id,
                    "nature": component.nature,
                    "status": "worksheet_arithmetic_available"
                    if amount is not None
                    else "review_needed",
                    "worksheet_contribution": amount,
                    "findings": findings,
                    "producer_dose": native["external_dose"],
                    "producer_flags": native.get("quality_flags", []),
                    "producer_limitations": native.get("limitations", []),
                }
                if component.check_pbpk_export:
                    handoff = await recorder.invoke(
                        client,
                        "call_tool",
                        "exposure_export_pbpk_external_import_bundle",
                        {"params": {"scenario": native}},
                    )
                    write_json(output / (component.id + "-pbpk-response.json"), handoff)
                    row["pbpk_response"] = handoff
                records.append(row)
            if native_additive:
                aggregate = await recorder.invoke(
                    client,
                    "call_tool",
                    "exposure_build_aggregate_exposure_scenario",
                    {
                        "params": {
                            "chemical_id": worksheet.scope.chemical_id,
                            "label": "Accounted external contributions for worksheet inspection",
                            "component_scenarios": native_additive,
                        }
                    },
                )
                write_json(output / "native-external-aggregate.json", aggregate)
    refs = catalogue()
    published = [
        {
            "id": key,
            "source_status": sources.get(key, {}).get("status", "missing"),
            "record": refs[key] if sources.get(key, {}).get("status") == "verified" else None,
            "reopening_condition": None
            if sources.get(key, {}).get("status") == "verified"
            else "Provide the correctly pinned primary record before attributing its conclusion.",
        }
        for key in worksheet.reference_cases
        if key in refs
    ]
    unknown_refs = [
        issue(
            "worksheet_reference_unmapped",
            (
                "Add and independently review a pinned catalogue entry before "
                "attributing its conclusion."
            ),
            reference=key,
        )
        for key in worksheet.reference_cases
        if key not in refs
    ]
    amounts = [
        Decimal(row["worksheet_contribution"])
        for row in records
        if row["worksheet_contribution"] is not None
    ]
    return {
        "schema_version": "exposureReviewReport.v1",
        "worksheet": worksheet.model_dump(mode="json"),
        "published_records": published,
        "sources": sources,
        "components": records,
        "accounted_worksheet_subtotal": str(sum(amounts)) if amounts else None,
        "subtotal_basis": worksheet.scope.dose_basis,
        "complete_aggregate_exposure": None,
        "global_findings": unknown_refs
        + [
            issue(
                "worksheet_material_appraisal_unresolved",
                "Appraise the assessed batch/specification, constituents and use conditions "
                "against the tested material. Publication, graph equality and caller review "
                "labels do not establish correspondence or approval.",
            ),
            issue(
                "worksheet_complete_coverage_unverified",
                (
                    "Review a complete source/event inventory with quantified "
                    "omissions where evidence permits; unknown bounds remain unknown."
                ),
            ),
        ],
        "approval": None,
        "assessmentStopAuthorized": False,
        "qualification": "not_established",
        "status": "completed",
    }


def semantic_results(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": report["status"],
        "qualification": report["qualification"],
        "assessmentStopAuthorized": report["assessmentStopAuthorized"],
        "published": [
            {"id": x["id"], "source_status": x["source_status"]}
            for x in report["published_records"]
        ],
        "components": [
            {
                "id": x["id"],
                "nature": x.get("nature"),
                "status": x["status"],
                "contribution": x["worksheet_contribution"],
                "finding_codes": [i["code"] for i in x["findings"]],
                "producer_flag_codes": [i["code"] for i in x.get("producer_flags", [])],
            }
            for x in report["components"]
        ],
        "accounted_worksheet_subtotal": report["accounted_worksheet_subtotal"],
        "subtotal_basis": report["subtotal_basis"],
        "complete_aggregate_exposure": None,
        "omitted_sources": report["worksheet"]["omitted_sources"],
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {report['worksheet']['title']}",
        "",
        "Execution completed. Qualification is not established; assessmentStopAuthorized is false.",
        "",
        "## Published findings",
        "",
    ]
    for row in report["published_records"]:
        record = row["record"]
        conclusion = (
            record.get("disposition", record.get("overall_disposition", record.get("lesson")))
            if record
            else row["reopening_condition"]
        )
        lines.append(f"- {row['id']}: {conclusion}")
        if record:
            lines.append(
                f"  Source: {record['source']['url']}; "
                f"printed pages {record['source']['printed_pages']}."
            )
    lines += [
        "",
        "## Producer and worksheet results",
        "",
        (
            "Producer doses remain external. Absorption arithmetic is separate"
            " worksheet arithmetic, with the original selection and "
            "applicability recorded in the input."
        ),
        "",
        "| Contribution | Input nature | Worksheet result | Review state |",
        "| --- | --- | --- | --- |",
    ]
    for row in report["components"]:
        lines.append(
            f"| {row['id']} | {row.get('nature', 'supplied')} | "
            f"{row['worksheet_contribution'] or 'unavailable'} | {row['status']} |"
        )
    subtotal = report["accounted_worksheet_subtotal"]
    lines += [
        "",
        f"Accounted worksheet subtotal ({report['subtotal_basis']}): "
        f"{subtotal if subtotal is not None else 'unavailable'}.",
        "",
        (
            "Complete aggregate exposure: unresolved. This is not an aggregate"
            " P95 or a producer-qualified TTC descriptor."
        ),
        "",
        "## Evidence decisions",
        "",
    ]
    for row in report["components"]:
        for finding in row["findings"]:
            lines.append(f"- {row['id']} / {finding['code']}: {finding['reopening_condition']}")
        if "pbpk_response" in row:
            response = row["pbpk_response"]
            lines.append(
                f"- {row['id']} / PBPK: inspect the captured readiness, denominator and "
                f"original limitations in {row['id']}-pbpk-response.json "
                f"(tool error: {response.get('isError', False)})."
            )
        for flag in row.get("producer_flags", []) + row.get("producer_limitations", []):
            lines.append(
                f"- {row['id']} / producer {flag['code']} ({flag['severity']}): "
                f"{flag['message']} Reopening: review and resolve this original "
                "producer finding against its source/context; an unmapped code remains visible."
            )
    for finding in report["global_findings"]:
        lines.append(f"- {finding['code']}: {finding['reopening_condition']}")
    for omission in report["worksheet"]["omitted_sources"]:
        lines.append(
            f"- Omitted {omission['id']}: bound "
            f"{omission['upper_bound'] if omission['upper_bound'] is not None else 'unknown'}. "
            f"Reopening: {omission['reopening_condition']}"
        )
    for note in report["worksheet"]["notes"]:
        lines.append(f"- {note}")
    lines += [
        "",
        (
            "Hypothetical and illustrative inputs are exposure calculations "
            "only. CAS/graph equality, publication, a reviewed label or "
            "successful mapping does not establish material correspondence or "
            "scientific approval."
        ),
        "",
        (
            "Inspect sdk-exchanges.jsonl and captured inputs/responses for "
            "actual calls. No active registration or production server was "
            "used."
        ),
        "",
    ]
    return "\n".join(lines)


def seal(output: Path) -> None:
    rows = [
        {
            "path": str(path.relative_to(output)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        }
        for path in sorted(output.rglob("*"))
        if path.is_file() and path.name != "SHA256SUMS.json"
    ]
    write_json(
        output / "SHA256SUMS.json", {"schema_version": "reviewRunManifest.v1", "files": rows}
    )


def run(worksheet_path: Path, servers_path: Path, sources_path: Path, output: Path) -> int:
    output.mkdir(parents=True, exist_ok=False)
    (output / "inputs").mkdir()
    (output / "server-diagnostics.log").touch()
    try:
        worksheet_raw = capture(worksheet_path, output / "inputs/worksheet.json")
        servers_raw = capture(servers_path, output / "inputs/servers.json")
        sources_raw = capture(sources_path, output / "inputs/sources.json")
        worksheet = ReviewWorksheet.model_validate_json(worksheet_raw)
        servers = ReviewServers.model_validate_json(servers_raw)
        config = ReviewSources.model_validate_json(sources_raw)
        write_json(output / "inputs/review-catalogue.json", catalogue())
        if not version("mcp").startswith("2."):
            raise ValueError("Run the worksheet with the repository's SDK2 Python environment.")
        sources = source_records(config, sources_path.parent, output)
        write_json(output / "source-verification.json", sources)
        report = anyio.run(execute, worksheet, servers, servers_path, sources, output)
        write_json(output / "report.json", report)
        write_json(output / "semantic-results.json", semantic_results(report))
        (output / "REPORT.md").write_text(markdown(report))
        return 0
    except Exception as error:
        write_json(
            output / "failure.json",
            {
                "status": "failed",
                "type": type(error).__name__,
                "message": str(error),
                "assessmentStopAuthorized": False,
            },
        )
        (output / "REPORT.md").write_text(
            f"# Exposure review could not complete\n\n{type(error).__name__}: {error}\n\n"
            "Correct the recorded failure and rerun into a fresh directory. "
            "No qualification or assessment-stop authority is established.\n"
        )
        return 1
    finally:
        seal(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ["worksheet", "servers", "sources", "output"]:
        parser.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(
            args.worksheet.resolve(),
            args.servers.resolve(),
            args.sources.resolve(),
            args.output.resolve(),
        )
    except FileExistsError:
        parser.exit(
            2, "Output directory exists. Preserve earlier results and choose a fresh --output.\n"
        )
    sys.exit(result)


if __name__ == "__main__":
    main()
