"""Track-B scientific-invariants gate — regression + adversarial proofs.

These tests pin the gate's contract:

* the PRISTINE released corpus passes (the gate is a tripwire, GREEN by default);
* every ADVERTISED scientific code BITES on a producer-emittable, strict-contract-
  VALID declared-field fault, and reverts to green when the fault is removed;
* the SOURCE-CONTRACT GUARD rejects a forbidden / undeclared-field packet fail-
  closed (SOURCE_CONTRACT_VIOLATION) and the packet is NEVER projected — this is
  the dead-arm closer;
* the bridge fails closed on a vendored-engine digest mismatch (tamper);
* the projection is total (declared fields only) and raises PROJECTION_INCOMPLETE
  rather than safe-defaulting a missing required field.

Node is required (the bridge shells out to the vendored engine); the tests skip
cleanly if it is unavailable so the native suite stays green on a Node-less box,
while CI runs them with Node present.
"""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

import scripts.scientific_invariants_gate as gate
from exposure_scenario_mcp.governance import project_to_spine as projector
from exposure_scenario_mcp.governance import spine_bridge as bridge
from exposure_scenario_mcp.governance.errors import (
    SOURCE_CONTRACT_VIOLATION,
    VENDOR_DIGEST_MISMATCH,
    ProjectionIncompleteError,
)
from exposure_scenario_mcp.governance.source_contract import validate_source_packet

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = REPO_ROOT / "tests" / "fixtures" / "governance"
EXTERNAL_FIXTURE = CORPUS_DIR / "aggregate_external_summary.json"
INTERNAL_FIXTURE = CORPUS_DIR / "aggregate_internal_equivalent_summary.json"

requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node is required to run the vendored spine engine"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Pristine corpus is GREEN
# --------------------------------------------------------------------------- #


@requires_node
def test_pristine_corpus_passes() -> None:
    assert gate.run_gate(list(gate.DEFAULT_CORPUS)) == 0


@requires_node
def test_pristine_is_deterministic_two_runs() -> None:
    assert gate.run_gate(list(gate.DEFAULT_CORPUS)) == 0
    assert gate.run_gate(list(gate.DEFAULT_CORPUS)) == 0


# --------------------------------------------------------------------------- #
# Source-contract guard (the dead-arm closer)
# --------------------------------------------------------------------------- #


def test_guard_accepts_real_producer_emission() -> None:
    assert validate_source_packet(_load(EXTERNAL_FIXTURE), corpus="ext") is None
    assert validate_source_packet(_load(INTERNAL_FIXTURE), corpus="ie") is None


def test_guard_rejects_undeclared_root_field() -> None:
    bad = copy.deepcopy(_load(EXTERNAL_FIXTURE))
    bad["allowedDownstreamUses"] = ["risk_assessment"]
    finding = validate_source_packet(bad, corpus="bad")
    assert finding is not None
    assert finding.code == SOURCE_CONTRACT_VIOLATION
    assert finding.origin == "meta"


def test_guard_rejects_forged_enum() -> None:
    bad = copy.deepcopy(_load(EXTERNAL_FIXTURE))
    bad["aggregationMode"] = "regulatory_conclusion"
    finding = validate_source_packet(bad, corpus="bad")
    assert finding is not None
    assert finding.code == SOURCE_CONTRACT_VIOLATION


def test_guard_rejects_undeclared_nested_field() -> None:
    bad = copy.deepcopy(_load(EXTERNAL_FIXTURE))
    bad["provenance"]["smuggled"] = "x"
    finding = validate_source_packet(bad, corpus="bad")
    assert finding is not None
    assert finding.code == SOURCE_CONTRACT_VIOLATION


@requires_node
def test_gate_blocks_forbidden_field_without_projecting(tmp_path: Path) -> None:
    bad = copy.deepcopy(_load(EXTERNAL_FIXTURE))
    bad["allowedDownstreamUses"] = ["risk_assessment", "regulatory_submission"]
    out = tmp_path / "forbidden.json"
    out.write_text(json.dumps(bad), encoding="utf-8")
    # exit 1 (blocked) and never projected.
    assert gate.run_gate([str(out)]) == 1


# --------------------------------------------------------------------------- #
# Each advertised scientific code bites on a producer-emittable declared fault
# --------------------------------------------------------------------------- #


def _blocking_codes(paths: list[Path]) -> set[str]:
    findings: list = []
    for p in paths:
        source = _load(p)
        contract = validate_source_packet(source, corpus=str(p))
        assert contract is None, "fault fixtures must be strict-contract VALID"
        for _label, obj in projector.project_summary(source, summary_id=str(p)):
            findings.extend(bridge.validate_object(obj).findings)
    return {f.code for f in findings}


@requires_node
def test_external_exposure_not_internal_dose_bites(tmp_path: Path) -> None:
    base = copy.deepcopy(_load(EXTERNAL_FIXTURE))
    ie = _load(INTERNAL_FIXTURE)
    # external_summary smuggling an internal-equivalent total — a real,
    # strict-contract-VALID producer fault (both fields are declared & nullable).
    base["internalEquivalentTotalDose"] = ie["internalEquivalentTotalDose"]
    out = tmp_path / "fault.json"
    out.write_text(json.dumps(base), encoding="utf-8")
    codes = _blocking_codes([out])
    assert "EXTERNAL_EXPOSURE_NOT_INTERNAL_DOSE" in codes


@requires_node
def test_uncertainty_and_ceiling_required_bites(tmp_path: Path) -> None:
    base = copy.deepcopy(_load(EXTERNAL_FIXTURE))
    base["uncertaintyRegister"] = []
    base["validationSummary"] = None
    out = tmp_path / "fault.json"
    out.write_text(json.dumps(base), encoding="utf-8")
    codes = _blocking_codes([out])
    assert "EXPOSURE_UNCERTAINTY_AND_CEILING_REQUIRED" in codes


@requires_node
def test_exposure_scenario_context_required_bites(tmp_path: Path) -> None:
    base = copy.deepcopy(_load(EXTERNAL_FIXTURE))
    base["uncertaintyRegister"] = []
    out = tmp_path / "fault.json"
    out.write_text(json.dumps(base), encoding="utf-8")
    codes = _blocking_codes([out])
    assert "EXPOSURE_SCENARIO_CONTEXT_REQUIRED" in codes


@requires_node
def test_coherent_internal_equivalent_passes() -> None:
    # The legitimate internal_equivalent summary is an external->internal-equivalent
    # dosimetry step (NOT an escalation) and must pass.
    source = _load(INTERNAL_FIXTURE)
    findings: list = []
    for _label, obj in projector.project_summary(source, summary_id="ie"):
        findings.extend(bridge.validate_object(obj).findings)
    assert findings == []


# --------------------------------------------------------------------------- #
# Fail-closed: vendored-engine digest tamper blocks
# --------------------------------------------------------------------------- #


@requires_node
def test_vendor_digest_mismatch_blocks(monkeypatch, tmp_path: Path) -> None:
    # Point the bridge at a tampered copy of the vendored engine.
    src_vendor = REPO_ROOT / "vendor" / "schema-spine"
    tampered = tmp_path / "schema-spine"
    shutil.copytree(src_vendor, tampered)
    # Mutate a tracked engine file so its sha256 no longer matches the manifest.
    victim = tampered / "policy-validator.mjs"
    victim.write_text(victim.read_text(encoding="utf-8") + "\n// tamper\n", encoding="utf-8")

    monkeypatch.setattr(bridge, "_VENDOR_ROOT", tampered)
    monkeypatch.setattr(bridge, "_VENDORED_FROM", tampered / "VENDORED_FROM.json")
    monkeypatch.setattr(bridge, "_RUN_POLICY_CLI", tampered / "run-policy.mjs")
    monkeypatch.setattr(bridge, "_INDEX_MJS", tampered / "index.mjs")

    obj = projector.project_route_dose_estimate(_load(EXTERNAL_FIXTURE), summary_id="x")
    result = bridge.validate_object(obj)
    assert not result.valid
    assert VENDOR_DIGEST_MISMATCH in result.blocking_codes


# --------------------------------------------------------------------------- #
# Projection is total (declared fields only), never safe-defaults
# --------------------------------------------------------------------------- #


def test_projection_requires_declared_fields() -> None:
    base = copy.deepcopy(_load(EXTERNAL_FIXTURE))
    del base["chemical_id"]
    with pytest.raises(ProjectionIncompleteError):
        projector.project_route_dose_estimate(base, summary_id="x")


def test_projection_requires_component_scenarios() -> None:
    base = copy.deepcopy(_load(EXTERNAL_FIXTURE))
    base["component_scenarios"] = []
    with pytest.raises(ProjectionIncompleteError):
        projector.project_scenario_contexts(base, summary_id="x")


def test_projection_emits_recognized_schema_ids() -> None:
    objs = projector.project_summary(_load(EXTERNAL_FIXTURE), summary_id="x")
    schema_ids = {obj["schemaId"] for _label, obj in objs}
    assert projector.ROUTE_DOSE_ESTIMATE_SCHEMA_ID in schema_ids
    assert projector.EXPOSURE_SCENARIO_CONTEXT_SCHEMA_ID in schema_ids


def test_external_summary_does_not_authorize_internal_dose() -> None:
    # Positive structured evidence: a coherent external_summary authorizes only
    # external-exposure tokens (no internal_dose token).
    uses = projector._allowed_downstream_uses(_load(EXTERNAL_FIXTURE))
    assert "internal_dose_estimate" not in uses
    assert "aggregate_exposure_prioritization" in uses
