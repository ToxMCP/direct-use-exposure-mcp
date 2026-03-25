"""Operator, provenance, troubleshooting, and release-guidance resources."""

from __future__ import annotations

from exposure_scenario_mcp.archetypes import ArchetypeLibraryRegistry
from exposure_scenario_mcp.benchmarks import load_benchmark_manifest
from exposure_scenario_mcp.defaults import build_defaults_curation_report
from exposure_scenario_mcp.models import (
    ReleaseMetadataReport,
    ReleaseReadinessReport,
    SecurityProvenanceReviewReport,
)
from exposure_scenario_mcp.probability_profiles import ProbabilityBoundsProfileRegistry
from exposure_scenario_mcp.scenario_probability_packages import ScenarioProbabilityPackageRegistry
from exposure_scenario_mcp.tier1_inhalation_profiles import Tier1InhalationProfileRegistry
from exposure_scenario_mcp.validation import build_validation_dossier_report
from exposure_scenario_mcp.validation_reference_bands import ValidationReferenceBandRegistry


def _benchmark_matrix_lines() -> list[str]:
    fixture = load_benchmark_manifest()
    lines = ["## Benchmark Matrix", ""]
    for case in fixture.get("cases", []):
        lines.append(
            f"- `{case['id']}` [{case['kind']}] {case['description']}"
        )
    return lines


def _archetype_library_lines() -> list[str]:
    manifest = ArchetypeLibraryRegistry.load().manifest()
    lines = [
        "## Packaged Archetype Sets",
        "",
        f"- Library version: `{manifest.library_version}`",
        f"- Set count: `{manifest.set_count}`",
    ]
    for item in manifest.sets:
        lines.append(
            f"- `{item.set_id}` [{item.route.value}/{item.scenario_class.value}] {item.label}"
        )
        if item.driver_parameters:
            lines.append(
                f"  drivers: {', '.join(f'`{name}`' for name in item.driver_parameters)}"
            )
    return lines


def _probability_profile_lines() -> list[str]:
    manifest = ProbabilityBoundsProfileRegistry.load().manifest()
    lines = [
        "## Packaged Probability Profiles",
        "",
        f"- Profile version: `{manifest.profile_version}`",
        f"- Profile count: `{manifest.profile_count}`",
    ]
    for item in manifest.profiles:
        lines.append(
            f"- `{item.profile_id}` "
            f"[{item.route.value}/{item.driver_family.value}/{item.product_family}] "
            f"{item.label}"
        )
    return lines


def _scenario_package_probability_lines() -> list[str]:
    manifest = ScenarioProbabilityPackageRegistry.load().manifest()
    lines = [
        "## Packaged Scenario-Probability Profiles",
        "",
        f"- Package profile version: `{manifest.profile_version}`",
        f"- Package profile count: `{manifest.profile_count}`",
    ]
    for item in manifest.profiles:
        lines.append(
            f"- `{item.profile_id}` "
            f"[{item.route.value}/{item.package_family.value}/{item.product_family}] "
            f"{item.label}"
        )
    return lines


def _tier1_inhalation_profile_lines() -> list[str]:
    manifest = Tier1InhalationProfileRegistry.load().manifest()
    lines = [
        "## Packaged Tier 1 Inhalation Profiles",
        "",
        f"- Profile version: `{manifest.profile_version}`",
        f"- Airflow classes: `{manifest.directionality_profile_count}`",
        f"- Particle regimes: `{manifest.particle_profile_count}`",
        f"- Product-family profiles: `{manifest.profile_count}`",
    ]
    for item in manifest.profiles:
        lines.append(
            f"- `{item.profile_id}` [{item.product_family}/{item.application_method}] {item.label}"
        )
    return lines


def tier1_inhalation_parameter_guide() -> str:
    manifest = Tier1InhalationProfileRegistry.load().manifest()
    lines = [
        "# Tier 1 Inhalation Parameter Guide",
        "",
        "This guide publishes the packaged Tier 1 NF/FF screening parameter pack used by the",
        "dedicated Tier 1 inhalation tool and referenced by Tier 1 source locators.",
        "",
        "## Parameter Pack",
        "",
        f"- Profile version: `{manifest.profile_version}`",
        f"- Manifest hash: `{manifest.profile_hash_sha256}`",
        f"- Resource path: `{manifest.path}`",
        "",
        "## Registered Sources",
        "",
    ]
    for item in manifest.sources:
        lines.append(f"- `{item.source_id}` [{item.version}] {item.title}")
    lines.extend(["", "## Airflow Classes", ""])
    for item in manifest.directionality_profiles:
        lines.append(
            f"- `{item.directionality.value}` -> `{item.exchange_turnover_per_hour}` 1/h: "
            f"{item.note}"
        )
    lines.extend(["", "## Particle Regimes", ""])
    for item in manifest.particle_profiles:
        lines.append(
            f"- `{item.particle_size_regime.value}` -> `{item.persistence_factor}`: {item.note}"
        )
    lines.extend([""])
    lines.extend(_tier1_inhalation_profile_lines())
    lines.extend(
        [
            "",
            "## Usage Notes",
            "",
            "- Use these profiles as governed screening anchors, not as substitutes for measured",
            "  room, plume, or droplet data.",
            "- Household-cleaner and personal-care profile packs are kept separate so downstream",
            "  provenance can distinguish those recommendation families.",
            "- Caller-supplied Tier 1 geometry and timing inputs remain authoritative even when a",
            "  matching packaged profile exists.",
            "- When caller-supplied Tier 1 geometry or regime inputs diverge materially from a",
            "  matched packaged profile, the runtime emits a warning-quality",
            "  `tier1_profile_anchor_divergence` flag and records alignment status in",
            "  `route_metrics`.",
        ]
    )
    return "\n".join(lines)


def operator_guide() -> str:
    return """# Operator Guide

## Runtime Modes

- Use `stdio` for local agent-to-server execution. This is the safest default.
- Use `streamable-http` only when the server is behind trusted network controls.
- Prefer deterministic screening tools for route-specific scenario construction and use export tools
  only after the scenario is auditable.

## Standard Validation

Run these commands before changing defaults, schemas, or plugins:

```bash
uv run ruff check .
uv run pytest
uv run generate-exposure-contracts
```

## Release Validation

Run these commands before publishing a release artifact set:

```bash
uv run ruff check .
uv run pytest
uv build
uv run generate-exposure-contracts
uv run check-exposure-release-artifacts
```

## Interpretation Guardrails

- Treat every output as external-exposure context only.
- Do not reinterpret screening outputs as internal dose, BER, PoD, or final risk conclusions.
- Review `qualityFlags`, `limitations`, `uncertaintyRegister`, `tierUpgradeAdvisories`, and
  `provenance` before using any scenario downstream.
- Treat `sensitivityRanking` as driver triage, not as a probabilistic uncertainty measure.

## Operational Checklist

- Confirm the defaults manifest version and SHA256 before benchmark or release runs.
- Run the release artifact verifier after `uv build` so published metadata matches `dist/`.
- Regenerate contracts whenever public schemas, examples, tools, or resources change.
- Keep ToxClaw and PBPK handoffs explicit; do not add hidden transformation logic in clients.
"""


def provenance_policy() -> str:
    return """# Provenance Policy

## Core Rules

- Every scenario, comparison, aggregate summary, and PBPK export must carry explicit provenance.
- Every applied default must appear in `exposureAssumptionRecord` output with a versioned source.
- Derived values remain visible as deterministic assumptions; they are not silently folded away.
- Every assumption now carries explicit governance metadata for evidence grade, applicability,
  uncertainty type, and default visibility.
- Every scenario now carries `tierSemantics` so screening outputs cannot quietly overclaim.

## Source Hierarchy

- `user_input`: explicit scenario inputs supplied by the caller.
- `default_registry`: values resolved from the versioned defaults pack.
- `derived`: deterministic runtime calculations generated by the active algorithm.

## Integrity Expectations

- The defaults pack is versioned and hashed with SHA256.
- Heuristic defaults must emit warning-quality flags so downstream users know they are still
  screening-level factors.
- ToxClaw-facing evidence exports use deterministic content hashes and stable IDs.

## Boundary

- Provenance demonstrates how external-dose outputs were produced.
- Provenance does not convert screening outputs into validated internal-dose or risk decisions.
"""


def uncertainty_framework() -> str:
    return """# Uncertainty Framework

## Tier A

- Deterministic point estimate plus explicit `uncertaintyRegister`.
- Deterministic one-at-a-time `sensitivityRanking`.
- Known dependencies preserved as `dependencyMetadata`.
- No probabilistic claims, confidence intervals, or population statements.

## Tier B

- Named deterministic scenario envelopes built from explicit archetypes.
- Deterministic parameter-bounds propagation from explicit lower and upper driver values.
- Envelope spans are bounded scenario sets, not confidence intervals.
- Parameter-bounds summaries are screening ranges, not population intervals or probabilistic claims.
- Driver attribution is based on explicit archetype differences, not Monte Carlo decomposition.

## Tier 1 Hooks

- Spray inhalation scenarios can emit `tierUpgradeAdvisories` that recommend Tier 1
  near-field/far-field modeling whenever Tier 0 room averages are too coarse.
- `requestedTier=tier_1` on the base inhalation request remains an explicit routing hook;
  callers should use the dedicated Tier 1 tool rather than expecting the Tier 0 room model
  to upgrade itself implicitly.
- `exposure_build_inhalation_tier1_screening_scenario` accepts the governed
  `inhalationTier1ScenarioRequest.v1` contract and returns a deterministic Tier 1 external-dose
  scenario for spray contexts.
- Tier 1 remains a screening model family with explicit airflow-class and particle-regime
  heuristics sourced from a packaged manifest; it is not a calibrated aerosol transport simulator.

## Tier C

- Packaged single-driver probability-bounds profiles for selected monotonic drivers.
- Packaged scenario-package probability profiles for selected coupled-driver clusters.
- Cumulative probability bounds apply to the selected driver support points only.
- Single-driver outputs keep all other scenario inputs fixed at the base scenario.
- Scenario-package outputs preserve coupled drivers within packaged template states.
- Tier C outputs are not joint exposure distributions or population simulations.

## Current Guardrail

- `v0.1.0` supports Tier A on every scenario output, Tier B via deterministic envelopes
  and parameter-bounds propagation, and Tier C only for packaged single-driver
  or scenario-package probability bounds.
- Probabilistic tiers remain blocked until validation evidence, dependency handling, and
  distribution governance mature.
"""


def archetype_library_guide() -> str:
    lines = [
        "# Archetype Library Guide",
        "",
        "Packaged archetype sets are governed Tier B screening templates that instantiate full",
        "deterministic envelopes with caller-supplied chemical identity.",
        "",
        "## Guardrails",
        "",
        "- Packaged sets are starting points for transparent Tier B envelopes,",
        "  not population distributions.",
        "- Keep route, use-context, and microenvironment interpretation tied",
        "  to the published set definition.",
        "- Replace library templates with scenario-specific evidence when",
        "  better product or use information exists.",
        "",
    ]
    lines.extend(_archetype_library_lines())
    lines.extend(
        [
            "",
            "## Client Guidance",
            "",
            "- Discover packaged sets through `archetypes://manifest` before building envelopes.",
            "- Use `exposure_build_exposure_envelope_from_library` when a",
            "  governed template is preferable to manual archetype construction.",
            "- Some packaged inhalation sets instantiate Tier 1 NF/FF requests rather than",
            "  Tier 0 room-average requests; preserve the resulting scenario tier semantics",
            "  on each archetype output instead of collapsing them into a generic",
            "  inhalation label.",
            "- Preserve `archetypeLibrarySetId`, `archetypeLibraryVersion`,",
            "  and any emitted library limitations in downstream reports.",
        ]
    )
    return "\n".join(lines)


def probability_bounds_guide() -> str:
    lines = [
        "# Probability Bounds Guide",
        "",
        "Packaged probability-bounds profiles expose cumulative probability bounds for one",
        "selected driver at a time while all other scenario inputs remain fixed.",
        "",
        "## Guardrails",
        "",
        "- Tier C probability-bounds outputs are not joint scenario distributions.",
        "- Profiles are packaged and reviewable; callers do not inject arbitrary",
        "  probability claims.",
        "- Single-driver summaries keep dependence externalized because only one",
        "  driver varies.",
        "- Single-driver summaries carry curated driver taxonomy through",
        "  `driverFamily`, `productFamily`, `dependencyCluster`, `fixedAxes`,",
        "  `relationshipType`, and `handlingStrategy`.",
        "- Scenario-package summaries carry curated package taxonomy through",
        "  `packageFamily`, `productFamily`, `dependencyAxes`, `relationshipType`,",
        "  and `handlingStrategy`.",
        "",
    ]
    lines.extend(_probability_profile_lines())
    lines.extend([""])
    lines.extend(_scenario_package_probability_lines())
    lines.extend(
        [
            "",
            "## Client Guidance",
            "",
            "- Discover packaged driver profiles through `probability-bounds://manifest`.",
            "- Discover packaged coupled-driver profiles through `scenario-probability://manifest`.",
            "- Use `exposure_build_probability_bounds_from_profile` only when the base request",
            "  matches the published profile applicability.",
            "- Use `exposure_build_probability_bounds_from_scenario_package` when preserving",
            "  coupled drivers matters more than isolating a single parameter.",
            "- Some packaged scenario-package profiles may evaluate governed Tier 1",
            "  inhalation archetype states; preserve emitted `tierSemantics`, matched",
            "  Tier 1 profile IDs, and inhalation limitations on every support point.",
            "- Preserve `driverProfileId` or `packageProfileId`, `profileVersion`, and all",
            "  emitted taxonomy, fixed-axis, and limitation fields in downstream summaries",
            "  and reports.",
        ]
    )
    return "\n".join(lines)


def inhalation_tier_upgrade_guide() -> str:
    lines = [
        "# Inhalation Tier Upgrade Guide",
        "",
        "## Current State",
        "",
        "- `v0.1.0` implements Tier 0 inhalation and a spray-focused Tier 1 NF/FF",
        "  screening path.",
        "- Spray scenarios can emit `tierUpgradeAdvisories` when the Tier 0 output",
        "  is likely to miss",
        "  breathing-zone peaks or source-proximal behavior.",
        "- `requestedTier=tier_1` on `inhalationScenarioRequest.v1` remains an",
        "  explicit routing hook and still fails loudly so callers do not silently",
        "  reinterpret the Tier 0 solver as Tier 1.",
        "- `exposure_build_inhalation_tier1_screening_scenario` accepts the published",
        "  `inhalationTier1ScenarioRequest.v1` schema and returns an",
        "  `exposureScenario.v1` result with",
        "  Tier 1 semantics.",
        "",
        "## When The Hook Triggers",
        "",
        "- Spray application methods such as `trigger_spray`, `pump_spray`, or `aerosol_spray`",
        "- Short event durations where transient peaks are plausible",
        "- Any screening context where a room-average concentration is not sufficient",
        "",
        "## Required Tier 1 Inputs",
        "",
        "- `source_distance_m`",
        "- `spray_duration_seconds`",
        "- `near_field_volume_m3`",
        "- `airflow_directionality`",
        "- `particle_size_regime`",
        "",
        "## Current Tier 1 Tool",
        "",
        "- Tool: `exposure_build_inhalation_tier1_screening_scenario`",
        "- Request schema: `inhalationTier1ScenarioRequest.v1`",
        "- Response schema: `exposureScenario.v1`",
        "- Current behavior: builds a deterministic near-field/far-field",
        "  screening scenario for spray",
        "  events while preserving Tier 1 limitations, quality flags, and screening-only caveats.",
        "",
        "## Packaged Tier 1 Screening Profiles",
        "",
        "- Discover governed airflow classes, particle regimes, and",
        "  product-family profiles through",
        "  `tier1-inhalation://manifest`.",
        "- Read the human-facing parameter notes in",
        "  `docs://tier1-inhalation-parameter-guide`.",
        "- The packaged manifest publishes explicit screening parameter",
        "  sources rather than burying",
        "  Tier 1 heuristics in code constants.",
        "- Preserve `tier1_profile_alignment_status` and any",
        "  `tier1_profile_anchor_divergence` warning when caller inputs",
        "  depart materially from the packaged Tier 1 anchors.",
        "",
    ]
    lines.extend(_tier1_inhalation_profile_lines())
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- Do not reinterpret Tier 0 spray outputs as near-field resolved.",
            "- Do not treat Tier 1 screening outputs as validated CFD,",
            "  deposition, or absorbed-dose",
            "  models.",
            "- Keep `tierUpgradeAdvisories`, `limitations`, `tierSemantics`, and any matched",
            "  Tier 1 profile identifiers attached to downstream reports.",
            "",
            "## Tier 1 Screening Semantics",
            "",
            "- Model family: `inhalation_near_field_far_field_screening`",
            "- Scope: still external-dose only",
            "- Mechanism: room-average far-field background plus an",
            "  active-spray near-field increment",
            "- Required inputs use governed airflow-directionality and",
            "  particle-regime vocabularies",
            "- Non-goals: deposited dose, absorbed dose, PBPK state",
            "  variables, or final risk conclusions",
        ]
    )
    return "\n".join(lines)


def validation_framework() -> str:
    report = build_validation_dossier_report()
    reference_manifest = ValidationReferenceBandRegistry.load().manifest()
    lines = [
        "# Validation Framework",
        "",
        "Current validation posture is verification plus benchmark regression, with a typed",
        "validation dossier for external-reference readiness and open evidence gaps.",
        "",
        "## Benchmark Domains",
        "",
    ]
    for item in report.benchmark_domains:
        lines.append(
            f"- `{item.domain}`: {', '.join(f'`{case_id}`' for case_id in item.case_ids)}"
        )
        for note in item.notes:
            lines.append(f"  note: {note}")
    lines.extend(["", "## External Validation Datasets", ""])
    for item in report.external_datasets:
        prefix = f"- `{item.dataset_id}` [{item.status.value}] {item.observable}: {item.note}"
        if item.reference_title and item.reference_locator:
            prefix += f" Reference: {item.reference_title} ({item.reference_locator})."
        lines.append(prefix)
    lines.extend(
        [
            "",
            "## Executable Validation Checks",
            "",
            "- `validationSummary.executedValidationChecks` is populated only when a scenario",
            "  matches a supported reference pattern with directly comparable metrics.",
            (
                f"- The executable reference-band manifest currently publishes "
                f"`{reference_manifest.band_count}`"
            ),
            "  narrow screening bands through `validation://reference-bands`.",
            "- Current executable checks cover hand-cream loading realism for hand-scale",
            "  dermal scenarios and wet-cloth contact mass realism for household-cleaner",
            "  wipe scenarios.",
        ]
    )
    lines.extend(["", "## Heuristic Source Families", ""])
    for source_id in report.heuristic_source_ids:
        lines.append(f"- `{source_id}`")
    lines.extend(["", "## Open Validation Gaps", ""])
    for item in report.open_gaps:
        lines.append(f"- `{item.gap_id}` [{item.severity.value}] {item.title}")
    lines.extend(["", "## Notes", ""])
    lines.extend(f"- {item}" for item in report.notes)
    return "\n".join(lines)


def validation_reference_bands_guide() -> str:
    manifest = ValidationReferenceBandRegistry.load().manifest()
    lines = [
        "# Validation Reference Bands",
        "",
        "These bands back the narrow executable validation checks exposed through",
        "`validationSummary.executedValidationChecks`.",
        "",
        f"- Reference version: `{manifest.reference_version}`",
        f"- Manifest hash: `{manifest.reference_hash_sha256}`",
        f"- Band count: `{manifest.band_count}`",
        f"- Resource path: `{manifest.path}`",
        "",
        "## Bands",
        "",
    ]
    for item in manifest.bands:
        selectors = ", ".join(
            f"{key}={value}" for key, value in sorted(item.applicable_selectors.items())
        ) or "global"
        lines.append(
            f"- `{item.reference_band_id}` -> `{item.check_id}` "
            f"[{item.domain}] `{item.reference_lower}` to `{item.reference_upper}` `{item.unit}`"
        )
        lines.append(f"  dataset: `{item.reference_dataset_id}`")
        lines.append(f"  selectors: {selectors}")
        lines.append(f"  note: {item.note}")
    lines.extend(["", "## Notes", ""])
    lines.extend(f"- {item}" for item in manifest.notes)
    return "\n".join(lines)


def defaults_curation_report_markdown() -> str:
    report = build_defaults_curation_report()
    lines = [
        "# Defaults Curation Report",
        "",
        f"- Defaults version: `{report.defaults_version}`",
        f"- Total branches: `{report.entry_count}`",
        f"- Curated branches: `{report.curated_entry_count}`",
        f"- Route-semantic branches: `{report.route_semantic_entry_count}`",
        f"- Heuristic branches: `{report.heuristic_entry_count}`",
        "",
        "## Curated Highlights",
        "",
    ]
    for entry in report.entries:
        if entry.curation_status.value != "curated":
            continue
        if entry.parameter_name not in {
            "retention_factor",
            "transfer_efficiency",
            "aerosolized_fraction",
        }:
            continue
        selectors = ", ".join(
            f"{key}={value}" for key, value in sorted(entry.applicability.items())
        ) or "global"
        lines.append(f"- `{entry.path_id}` -> `{entry.source_id}` ({selectors})")
    lines.extend(["", "## Route-Semantic Highlights", ""])
    for entry in report.entries:
        if entry.curation_status.value != "route_semantic":
            continue
        if entry.parameter_name not in {
            "retention_factor",
            "transfer_efficiency",
            "ingestion_fraction",
        }:
            continue
        lines.append(f"- `{entry.path_id}` -> `{entry.source_id}`")
    lines.extend(["", "## Residual Heuristic Branches", ""])
    for entry in report.entries:
        if entry.curation_status.value != "heuristic":
            continue
        lines.append(f"- `{entry.path_id}` -> `{entry.source_id}`")
    lines.extend(["", "## Notes", ""])
    lines.extend(f"- {item}" for item in report.notes)
    return "\n".join(lines)


def validation_dossier_markdown() -> str:
    report = build_validation_dossier_report()
    lines = [
        "# Validation Dossier",
        "",
        f"- Policy version: `{report.policy_version}`",
        f"- Benchmark domains: `{len(report.benchmark_domains)}`",
        f"- External validation datasets: `{len(report.external_datasets)}`",
        f"- Heuristic source families still active: `{len(report.heuristic_source_ids)}`",
        "",
        "## Open Gaps",
        "",
    ]
    for item in report.open_gaps:
        domains = ", ".join(f"`{domain}`" for domain in item.applies_to_domains)
        sources = ", ".join(f"`{source_id}`" for source_id in item.related_source_ids) or "none"
        lines.append(f"- `{item.gap_id}` [{item.severity.value}] {item.title}")
        lines.append(f"  domains: {domains}")
        lines.append(f"  sources: {sources}")
        lines.append(f"  note: {item.note}")
        lines.append(f"  recommendation: {item.recommendation}")
    lines.extend(["", "## Notes", ""])
    lines.extend(f"- {item}" for item in report.notes)
    return "\n".join(lines)


def troubleshooting_guide() -> str:
    return """# Troubleshooting

## Common Failures

- `comparison_chemical_mismatch`: the compared scenarios do not share the same `chemical_id`.
- `pbpk_body_weight_missing`: the scenario does not resolve `body_weight_kg`.
- `pbpk_inhalation_duration_missing`: inhalation PBPK export needs explicit event duration.
- `pbpk_unit_unsupported`: PBPK handoff accepts only canonical external dose units.
- `aggregate_component_duplicate`: aggregate inputs reused the same component scenario.

## Troubleshooting Sequence

1. Validate the request against the published schema resource.
2. Inspect `qualityFlags`, `limitations`, and `provenance` in the returned object.
3. Check the defaults manifest and defaults evidence map for the active factor source.
4. Re-run contract generation after changing any outward-facing schema or example.

## Remote Deployment Caution

- The server does not add authentication or origin enforcement on its own.
- If you expose `streamable-http`, put it behind trusted network controls or a gateway.
"""


def result_status_semantics() -> str:
    return """# Result Status Semantics

## Purpose

- Tool responses keep their existing `structuredContent` payload contracts.
- Future-safe execution state is published separately in top-level tool-result `_meta`.
- The metadata shape follows `toolResultMeta.v1`.

## Current v0.1 Behavior

- `executionMode` is always `sync`.
- `resultStatus` is `completed` for successful calls and `failed` for error results.
- `terminal` is always `true`.
- `queueRequired` is always `false`.
- `jobId` and `statusCheckUri` are `null`.

## Reserved Future States

- `accepted`: a request was accepted for asynchronous execution.
- `running`: execution is still in progress.
- Future async tools should reuse the same keys rather than inventing a second result style.

## Client Guidance

- Read `structuredContent` for the domain object.
- Read top-level `_meta` for execution semantics.
- Do not expect polling or queue semantics from the current deterministic release.
"""


def release_readiness_markdown(report: ReleaseReadinessReport) -> str:
    lines = [
        "# Release Readiness",
        "",
        report.summary,
        "",
        "## Status",
        "",
        f"- Release candidate: `{report.release_candidate}`",
        f"- Server: `{report.server_name}` `{report.server_version}`",
        f"- Defaults version: `{report.defaults_version}`",
        f"- Readiness status: `{report.status}`",
        "",
        "## Public Surface",
        "",
        f"- Tools: `{report.public_surface.tool_count}`",
        f"- Resources: `{report.public_surface.resource_count}`",
        f"- Prompts: `{report.public_surface.prompt_count}`",
        f"- Transports: {', '.join(f'`{item}`' for item in report.public_surface.transports)}",
        "",
        "## Validation Commands",
        "",
    ]
    lines.extend(f"- `{command}`" for command in report.validation_commands)
    lines.extend(["", "## Checks", ""])
    for check in report.checks:
        status = check.status.upper()
        lines.append(f"- `{check.check_id}` [{status}] {check.title}: {check.evidence}")
        if check.recommendation:
            lines.append(f"  next step: {check.recommendation}")
    lines.extend(["", *_benchmark_matrix_lines(), ""])
    lines.extend(["", "## Known Limitations", ""])
    lines.extend(f"- {item}" for item in report.known_limitations)
    return "\n".join(lines)


def security_provenance_review_markdown(report: SecurityProvenanceReviewReport) -> str:
    lines = [
        "# Security And Provenance Review",
        "",
        report.summary,
        "",
        "## Status",
        "",
        f"- Review ID: `{report.review_id}`",
        f"- Server: `{report.server_name}` `{report.server_version}`",
        f"- Defaults version: `{report.defaults_version}`",
        f"- Reviewed at: `{report.reviewed_at}`",
        f"- Review status: `{report.status}`",
        "",
        "## Reviewed Surface",
        "",
        f"- Tools: `{len(report.reviewed_surface.tool_names)}`",
        f"- Resources: `{len(report.reviewed_surface.resource_uris)}`",
        f"- Prompts: `{len(report.reviewed_surface.prompt_names)}`",
        "",
        "## Findings",
        "",
    ]
    for finding in report.findings:
        lines.append(
            f"- `{finding.finding_id}` [{finding.status.upper()}] {finding.title}: "
            f"{finding.evidence}"
        )
        if finding.recommendation:
            lines.append(f"  next step: {finding.recommendation}")
        if finding.references:
            lines.append(
                "  references: "
                + ", ".join(f"`{reference}`" for reference in finding.references)
            )
    lines.extend(["", "## External Requirements", ""])
    lines.extend(f"- {item}" for item in report.external_requirements)
    return "\n".join(lines)


def release_notes_markdown(report: ReleaseMetadataReport) -> str:
    lines = [
        "# Release Notes",
        "",
        (
            "Exposure Scenario MCP `v0.1.0` is the first public deterministic external-dose "
            "release candidate for the ToxMCP suite."
        ),
        "",
        "## Release Scope",
        "",
        "- Dermal, oral, and inhalation screening scenario construction",
        "- Aggregate/co-use summaries and auditable scenario comparison",
        "- PBPK handoff export aligned to the published PBPK MCP request shape",
        "- Deterministic ToxClaw evidence and refinement-bundle exports",
        "",
        "## Benchmark Summary",
        "",
        f"- Benchmark cases: `{report.benchmark_case_count}`",
        f"- Covered case IDs: {', '.join(f'`{item}`' for item in report.benchmark_case_ids)}",
        "",
        *_benchmark_matrix_lines(),
        "",
        "## Migration Notes",
        "",
    ]
    lines.extend(f"- {item}" for item in report.migration_notes)
    lines.extend(["", "## Validation Commands", ""])
    lines.extend(f"- `{item}`" for item in report.validation_commands)
    return "\n".join(lines)


def conformance_report_markdown(
    metadata: ReleaseMetadataReport,
    readiness: ReleaseReadinessReport,
    security_review: SecurityProvenanceReviewReport,
) -> str:
    lines = [
        "# Conformance Report",
        "",
        "This report summarizes the current release candidate against the published contract, "
        "benchmark, and review gates.",
        "",
        "## Status",
        "",
        f"- Package: `{metadata.package_name}` `{metadata.package_version}`",
        f"- Readiness: `{metadata.readiness_status}`",
        f"- Security/provenance review: `{metadata.security_review_status}`",
        f"- Contract schemas: `{metadata.contract_schema_count}`",
        f"- Contract examples: `{metadata.contract_example_count}`",
        "",
        "## Distribution Artifacts",
        "",
    ]
    for artifact in metadata.distribution_artifacts:
        availability = "present" if artifact.present else "not-built"
        details = [f"at `{artifact.relative_path}`"]
        if artifact.sha256 is not None:
            details.append(f"sha256 `{artifact.sha256[:16]}`")
        if artifact.size_bytes is not None:
            details.append(f"size `{artifact.size_bytes}` bytes")
        lines.append(
            f"- `{artifact.kind}` `{artifact.filename}` [{availability}] " + ", ".join(details)
        )
    lines.extend(["", "## Benchmark Coverage", ""])
    lines.append(f"- Benchmark cases published: `{metadata.benchmark_case_count}`")
    lines.extend(
        f"- `{case_id}`" for case_id in metadata.benchmark_case_ids
    )
    lines.extend(["", "## Release Gates", ""])
    for check in readiness.checks:
        lines.append(f"- `{check.check_id}` [{check.status.upper()}] {check.title}")
    lines.extend(["", "## Security Review Findings", ""])
    for finding in security_review.findings:
        lines.append(f"- `{finding.finding_id}` [{finding.status.upper()}] {finding.title}")
    return "\n".join(lines)
