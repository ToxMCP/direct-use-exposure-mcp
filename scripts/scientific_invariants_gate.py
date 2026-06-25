#!/usr/bin/env python3
"""Track-B scientific-invariants gate (vendored schema-spine engine).

Projects each RELEASED ``aggregateExposureSummary.v1`` object onto its canonical
ToxMCP schema-spine shapes, runs the vendored, digest-pinned spine policy engine
over the projection via a fail-closed Node bridge, aggregates every blocking
finding, and EXITS NON-ZERO if any public-release-blocking code fires.

A SOURCE-CONTRACT GUARD runs at the TOP of the gate, BEFORE any projection: every
raw source packet is validated against the producer's STRICT emission contract
(``additionalProperties:false`` JSON schema mirroring the pydantic ``extra=forbid``
serializer). A packet that violates the contract — including any undeclared /
schema-forbidden field — is a ``SOURCE_CONTRACT_VIOLATION`` that BLOCKS and is NEVER
projected. This closes the producer-emission-contract dead-arm class.

direct-use-exposure-mcp is deterministic and non-LLM and already enforces these
invariants natively, so on the PRISTINE corpus this gate is GREEN. Its job is to
BLOCK if a future change ever lets one of these regressions into a released object:

  Scientific (from the engine, advertised == producer-contract-valid-reachable):
    EXTERNAL_EXPOSURE_NOT_INTERNAL_DOSE      — an external aggregate exposure
        estimate authorizing an internal-dose / risk / regulatory downstream use
        (e.g. an external_summary that smuggles an internalEquivalentTotalDose).
    EXPOSURE_UNCERTAINTY_AND_CEILING_REQUIRED — a released summary that drops its
        uncertainty / confidence-ceiling references.
    EXPOSURE_SCENARIO_CONTEXT_REQUIRED        — a component exposure scenario with
        an unassessed route or no explicit uncertainty references.

  Meta fail-closed (synthesized by the guard/bridge/projection):
    SOURCE_CONTRACT_VIOLATION, ENGINE_UNAVAILABLE, UNRECOGNIZED_SPINE_SCHEMA_ID,
    VENDOR_DIGEST_MISMATCH, PROJECTION_INCOMPLETE.

DEAD-ARM DISCIPLINE (advertised == actual coverage). The released summary carries NO
AI / model-use / LLM / provenance-of-generation source field (the producer is
deterministic), so NO AssessmentRun is projected and NO AI-provenance spine code is
advertised — advertising one would be a DEAD ARM (no real source fault could make the
engine dispatch it). See ADR 0005.

This gate is ADVISORY on the free-plan repo (no required-status-checks). The bridge
additionally fails closed at runtime on VENDOR_DIGEST_MISMATCH / ENGINE_UNAVAILABLE.
PROMOTE-TO-BLOCKING PATH: when the repo moves to a plan with branch protection /
rulesets, mark the ``scientific-invariants`` CI job a required status check — the gate
already exits non-zero on any blocking code, so no script change is needed.

Exit codes:
    0 — every projected object passed the engine (no blocking code fired)
    1 — at least one blocking code fired (release-blocking regression)
    2 — usage / corpus-loading error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from exposure_scenario_mcp.governance import project_to_spine as projector  # noqa: E402
from exposure_scenario_mcp.governance import spine_bridge as bridge  # noqa: E402
from exposure_scenario_mcp.governance.errors import (  # noqa: E402
    PROJECTION_INCOMPLETE,
    BlockingFinding,
    ProjectionIncompleteError,
)
from exposure_scenario_mcp.governance.source_contract import (  # noqa: E402
    validate_source_packet,
)

# The released-object corpus (relative to repo root). These are byte-faithful
# captures of the real producer emission (regenerate via
# scripts/build_scientific_invariants_corpus.py).
DEFAULT_CORPUS: tuple[str, ...] = (
    "tests/fixtures/governance/aggregate_external_summary.json",
    "tests/fixtures/governance/aggregate_internal_equivalent_summary.json",
)

# The public-release-blocking scientific codes this gate asserts on. (Meta codes
# from errors.META_FAIL_CLOSED_CODES are ALWAYS blocking and need no listing.)
BLOCKING_SCIENTIFIC_CODES: frozenset[str] = frozenset(
    {
        "EXTERNAL_EXPOSURE_NOT_INTERNAL_DOSE",
        "EXPOSURE_UNCERTAINTY_AND_CEILING_REQUIRED",
        "EXPOSURE_SCENARIO_CONTEXT_REQUIRED",
    }
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_gate(corpus: list[str], *, emit_json: bool = False) -> int:
    findings: list[tuple[str, BlockingFinding]] = []
    checked = 0
    for rel in corpus:
        path = REPO_ROOT / rel
        if not path.exists():
            print(f"[scientific-invariants] FAIL: corpus file missing: {rel}", file=sys.stderr)
            return 2
        source = _load(path)

        # 0. SOURCE-CONTRACT GUARD — validate the raw packet against the producer's
        #    STRICT emission contract BEFORE any projection. A violation blocks and
        #    the packet is never projected.
        contract_finding = validate_source_packet(source, corpus=rel)
        if contract_finding is not None:
            findings.append((f"{rel}#source", contract_finding))
            continue

        # 1. Projection can itself raise PROJECTION_INCOMPLETE -> a hard block.
        try:
            projected = projector.project_summary(source, summary_id=rel)
        except ProjectionIncompleteError as exc:
            findings.append(
                (
                    rel,
                    BlockingFinding.meta(
                        PROJECTION_INCOMPLETE, exc.message, path=exc.path, corpus=rel
                    ),
                )
            )
            continue

        for label, obj in projected:
            checked += 1
            result = bridge.validate_object(obj)
            for finding in result.findings:
                findings.append((label, finding))

    blocking = [
        (label, f)
        for (label, f) in findings
        if f.origin == "meta" or f.code in BLOCKING_SCIENTIFIC_CODES
    ]

    if emit_json:
        print(
            json.dumps(
                {
                    "checkedObjects": checked,
                    "blocking": [{"object": label, **f.as_dict()} for (label, f) in blocking],
                    "allFindings": [{"object": label, **f.as_dict()} for (label, f) in findings],
                },
                indent=2,
            )
        )

    if blocking:
        print(
            f"[scientific-invariants] BLOCK — {len(blocking)} release-blocking "
            f"finding(s) across {checked} projected object(s):",
            file=sys.stderr,
        )
        for label, f in blocking:
            print(f"  - [{f.origin}] {f.code} @ {label} {f.path}: {f.message}", file=sys.stderr)
        return 1

    print(
        f"[scientific-invariants] OK — {checked} projected object(s) passed the "
        f"vendored spine policy engine (no release-blocking code fired).",
        file=sys.stderr,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus",
        nargs="*",
        default=list(DEFAULT_CORPUS),
        help="Released-object JSON files to project + validate (default: the standard corpus).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable JSON report to stdout.",
    )
    args = parser.parse_args(argv)
    return run_gate(args.corpus, emit_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
