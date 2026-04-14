"""Operator, provenance, troubleshooting, and release-guidance resources."""

from __future__ import annotations

from exposure_scenario_mcp.archetypes import ArchetypeLibraryRegistry
from exposure_scenario_mcp.benchmarks import load_benchmark_manifest, load_goldset_manifest
from exposure_scenario_mcp.contracts import build_verification_summary_report
from exposure_scenario_mcp.defaults import DefaultsRegistry, build_defaults_curation_report
from exposure_scenario_mcp.models import (
    ReleaseMetadataReport,
    ReleaseReadinessReport,
    SecurityProvenanceReviewReport,
)
from exposure_scenario_mcp.probability_profiles import ProbabilityBoundsProfileRegistry
from exposure_scenario_mcp.scenario_probability_packages import ScenarioProbabilityPackageRegistry
from exposure_scenario_mcp.tier1_inhalation_profiles import Tier1InhalationProfileRegistry
from exposure_scenario_mcp.validation import (
    build_validation_coverage_report,
    build_validation_dossier_report,
)
from exposure_scenario_mcp.validation_reference_bands import ValidationReferenceBandRegistry
from exposure_scenario_mcp.validation_time_series import ValidationTimeSeriesReferenceRegistry


def _benchmark_matrix_lines() -> list[str]:
    fixture = load_benchmark_manifest()
    lines = ["## Benchmark Matrix", ""]
    for case in fixture.get("cases", []):
        lines.append(
            f"- `{case['id']}` [{case['kind']}] {case['description']}"
        )
    return lines


def _goldset_matrix_lines() -> list[str]:
    manifest = load_goldset_manifest()
    lines = ["## Goldset Cases", ""]
    for case in manifest.get("cases", []):
        lines.append(f"- `{case['id']}` [{case['coverage_status']}] {case['title']}")
        if case.get("benchmark_case_ids"):
            linked = ", ".join(f"`{item}`" for item in case["benchmark_case_ids"])
            lines.append(f"  linked benchmarks: {linked}")
        if case.get("challenge_tags"):
            tags = ", ".join(f"`{item}`" for item in case["challenge_tags"])
            lines.append(f"  challenge tags: {tags}")
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
            "- Household-cleaner, personal-care, disinfectant, and pest-control profile packs",
            "  are kept separate so downstream provenance can distinguish those recommendation",
            "  families and subtype overlays.",
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


def exposure_platform_architecture_guide() -> str:
    return """# Exposure Platform Architecture

Exposure modeling is broader than consumer product use. This platform should grow as a
small set of cooperating MCPs with explicit boundaries rather than one server that tries to
wrap every exposure tool directly.

## Design Rule

- Build around shared scenario contracts and harmonized outputs.
- Do not make desktop tools or region-specific calculators the core abstraction.
- Keep PBPK handoff stable even when upstream exposure engines differ.

## Recommended MCP Boundaries

### Direct-Use Exposure MCP

- Owns human external-dose construction for direct-use and near-field scenarios.
- Covers consumer product-use scenarios, dermal plus direct-use/incidental oral screening,
  indoor aerosol screening,
  and worker task routing while the shared task/use abstractions still hold.
- Accepts reviewed evidence packs from CompTox, SCCS, SCCS opinions, CosIng, ConsExpo,
  nanomaterial/microplastics records, dossiers, and user uploads.
- Emits PBPK-ready external-dose handoff objects.

### Fate MCP

- Owns environmental release, multimedia fate, and compartment concentrations.
- Covers release to air, water, soil, and sediment plus long-term concentration surfaces.
- Candidate model families include `SimpleBox`, `EUSES`, and other multimedia fate engines.
- Should remain a sibling MCP, not an internal subsystem of Direct-Use Exposure MCP.

### Dietary MCP

- Owns food-residue and dietary-intake workflows.
- Covers commodity concentration inputs, food-consumption mappings, and oral intake outputs.
- Candidate model families include `PRIMo` and `DEEM`-aligned workflows.
- Should also remain a sibling MCP because the input taxonomy and regulatory semantics differ
  from direct-use exposure.

### Worker Exposure Mode

- Start worker support inside Direct-Use Exposure MCP.
- Use Tier 1/Tier 2 routing rather than a single worker model.
- Candidate model families include `ECETOC TRA`, `ART`, and `Stoffenmanager` when access
  constraints permit.
- Split into a dedicated Worker MCP only if licensing, validation, or workflow complexity makes
  the shared abstractions stop paying off.

## Shared Cross-MCP Contracts

- `chemical_identity`
- `product_use_evidence_record`
- `exposure_scenario_definition`
- `environmental_release_scenario`
- `concentration_surface`
- `route_dose_estimate`
- `pbpk_external_import_bundle`

These shared contracts are now published from this repo as governed schemas so sibling Fate
and Dietary services can build against stable handoff shapes before their own runtimes land.

## Routing Model

- Consumer spray, cosmetic, cleaner, or particle-aware cosmetic task -> Direct-Use Exposure MCP
  direct-use engine or SCCS/SCCS-opinion/ConsExpo-aligned pack
- Direct-use oral or incidental oral question -> Direct-Use Exposure MCP
- Worker task with limited data -> Direct-Use Exposure MCP worker router plus the current
  screening or Tier 1 path
- Worker task needing higher-tier refinement -> `ART` or `Stoffenmanager` adapter path
- Indoor aerosol room problem -> Direct-Use Exposure MCP indoor engine now;
  `CONTAM` or `IAQX` adapter later
- Environmental release or chronic multimedia question -> Fate MCP
- Food-residue intake question -> Dietary MCP

## Integration Principles

- Tool adapters should translate into shared contracts, not leak tool-native schemas.
- Region-specific evidence should remain additive and reviewable.
- Defaults must stay versioned, attributable, and easy to override.
- Internal dose is downstream of exposure; PBPK remains a separate MCP boundary.
- Probabilistic mode should reuse deterministic kernels rather than replace them.

## Build Order

### Phase 1

- Strengthen the current Direct-Use Exposure MCP.
- Finish consumer direct-use coverage, indoor aerosol refinement, evidence reconciliation,
  particle-aware cosmetics/material context, and stable PBPK export.

### Phase 2

- Mature the current worker router, Tier 2 hooks, dermal absorbed-dose hooks, and better
  inhalation refinement while keeping the worker path inside Direct-Use Exposure MCP.
- Add a structured worker Tier 2 bridge export and ART-side ingest boundary before wiring a
  real occupational solver.

### Phase 3

- Add Fate MCP with environmental release scenarios and concentration surfaces that Exposure
  Scenario MCP can consume.

### Phase 4

- Add Dietary MCP with commodity and consumption abstractions plus oral PBPK handoff.

### Phase 5

- Add probabilistic orchestration on top of the shared contracts.

## Non-Goals

- Do not merge PBPK into Direct-Use Exposure MCP.
- Do not claim risk conclusions from external-dose outputs.
- Do not make the first version depend on heavyweight desktop models being callable in real time.
"""


def cross_mcp_contract_guide() -> str:
    return """# Cross-MCP Contract Guide

Direct-Use Exposure MCP now publishes the shared suite-facing contracts that sibling MCPs
should build against instead of inventing parallel handoff shapes.

## Published Shared Schemas

- `chemicalIdentity.v1`
- `productUseEvidenceRecord.v1`
- `exposureScenarioDefinition.v1`
- `routeDoseEstimate.v1`
- `environmentalReleaseScenario.v1`
- `concentrationSurface.v1`
- `pbpkExternalImportBundle.v1`

## Intent By Contract

### `chemicalIdentity.v1`

- Stable identity handoff for CompTox, Fate, Dietary, Exposure, and PBPK orchestration.
- Carries the suite chemical identifier plus optional CASRN, DTXSID, and other external IDs.

### `productUseEvidenceRecord.v1`

- Shared evidence contract for product-use, reviewed dossier, SCCS, SCCS opinion, CosIng,
  ConsExpo, nanomaterial, microplastics, and other source-normalized records.
- Can carry quantitative product/population overrides plus `particleMaterialContext.v1` when
  the direct-use semantics depend on nano or microparticle properties.
- Can also carry reviewed `ProductUseProfile` routing fields such as `intendedUseFamily` and
  `oralExposureContext` when medicinal, supplement, botanical, or other oral cases need clear
  Direct-Use vs Dietary routing.

### `exposureScenarioDefinition.v1`

- Shared scenario-definition contract for direct-use or concentration-to-dose workflows.
- Keeps product-use grammar separate from concentration-surface references so sibling MCPs can
  hand off cleanly without forcing tool-native payloads into each other.
- When oral workflows are in scope, use `productUseProfile.intendedUseFamily` and
  `productUseProfile.oralExposureContext` to keep medicinal direct-use, supplement regimens,
  food-mediated intake, and environmental-media ingestion from collapsing into one ambiguous
  oral category.

### `routeDoseEstimate.v1`

- Compact auditable dose object for downstream orchestration and PBPK preparation.
- Preserves route, scenario class, provenance, limitations, quality flags, and fit-for-purpose
  instead of reducing everything to a naked numeric value.

### `environmentalReleaseScenario.v1`

- Future Fate MCP ingress contract for source-to-concentration workflows.
- Published here so sibling services can lock the shared semantics before Fate MCP is built out.

### `concentrationSurface.v1`

- Future Fate MCP output contract for concentration-to-dose consumers.
- Keeps medium, compartment, geographic scope, time semantics, model family, and provenance
  explicit so Exposure MCP does not need fate-tool-native parsing logic later.

## Boundary Notes

- Direct-use oral and incidental oral stay in Direct-Use Exposure MCP.
- diet-mediated oral belongs in Dietary MCP and should emit `routeDoseEstimate.v1` rather than
  overloading `exposureScenarioRequest.v1`.
- Traditional Chinese Medicine, herbal medicine, and supplement cases should be routed by
  pathway semantics rather than by cultural label:
  - medicinal or product-centric oral regimens -> Direct-Use Exposure MCP
  - topical or inhaled herbal preparations -> Direct-Use Exposure MCP
  - food-mediated herbal intake or nutrition-style supplement intake -> Dietary MCP
- Environmental release and multimedia transfer belong in Fate MCP and should emit
  `concentrationSurface.v1`, not body-weight-normalized human dose.
- PBPK MCP should consume stable dose semantics and identity records, not product-use prose or
  model-native blobs.

## Design Rules

- Translate external tools or regional sources into shared contracts, not the reverse.
- Preserve provenance and limitation notes at every handoff boundary.
- Treat heuristic and bounded-surrogate paths as explicit maturity states, not hidden internals.
- Add new shared contracts only when at least one cross-MCP handoff needs them.
"""


def service_selection_guide() -> str:
    return """# Service Selection Guide

Use this guide when routing a question to the right ToxMCP service.

## Ownership Table

- Consumer product use, direct-use dermal, direct-use oral, incidental oral, indoor aerosol,
  residual-air reentry, and near-field worker screening -> `Direct-Use Exposure MCP`
- Environmental release, multimedia transfer, and compartment concentration estimation ->
  `Fate MCP`
- Commodity residues, food-consumption mappings, acute/chronic dietary intake ->
  `Dietary MCP`
- Internal dose, TK simulation, tissue concentration time courses -> `PBPK MCP`
- Cross-service orchestration, evidence handling, refinement policy, final reporting -> `ToxClaw`

## Edge Cases

- Direct-use oral stays in Direct-Use Exposure MCP.
- Diet-mediated oral goes to Dietary MCP.
- Medicinal oral products, including Traditional Chinese Medicine regimens, stay in Direct-Use
  Exposure MCP when the workflow is product-centric dosing rather than food consumption.
- Supplement pills or capsules should be split explicitly:
  - labeled product regimen or consumer-use dosing -> Direct-Use Exposure MCP
  - dietary or nutrition-style intake workflow -> Dietary MCP
- Environmental oral from media is not Dietary by default; it should start with Fate MCP
  concentration outputs and then enter a future concentration-to-dose workflow.
- Regional outdoor air due to emissions belongs to Fate MCP.
- Human dose from environmental air concentration belongs to a concentration-to-dose consumer,
  not Fate MCP core.

## Handoff Preference

- Identity or product-use evidence first -> normalize into `chemicalIdentity.v1` and
  `productUseEvidenceRecord.v1`
- Environmental source term first -> `environmentalReleaseScenario.v1`
- Environmental concentration output first -> `concentrationSurface.v1`
- Human dose output first -> `routeDoseEstimate.v1`
- PBPK-ready external handoff -> `pbpkExternalImportBundle.v1`

## Current Exposure MCP Scope

- Exposure MCP already publishes the shared schemas needed to coordinate with future Fate and
  Dietary siblings.
- EU cosmetic nanomaterial, microplastic, and non-plastic particle direct-use questions stay in
  Direct-Use Exposure MCP while the workflow is about direct-use assumptions and external dose,
  not multimedia fate or final toxicology interpretation.
- Oral direct-use cases can now declare `intendedUseFamily` plus `oralExposureContext` to make
  medicinal, supplement, incidental, and non-Direct-Use dietary semantics auditable at the
  request-contract layer.
- Publishing these schemas here does not mean Fate or Dietary logic now belongs inside this repo.
"""


def herbal_medicinal_routing_guide() -> str:
    return """# Herbal, TCM, and Supplement Routing Guide

Use this guide when a case involves Traditional Chinese Medicine, herbal medicines,
botanical supplements, or similar oral or topical consumer products.

## Core Rule

Route by **pathway semantics and intended use**, not by cultural label or dosage form alone.

## Direct-Use Exposure MCP Cases

- Medicinal oral regimens such as Traditional Chinese Medicine decoctions, pills, tinctures,
  or therapeutic powders when the workflow is about labeled product use or explicit dosing.
- Topical herbal or TCM balms, liniments, oils, patches, and related direct-use dermal cases.
- Inhaled herbal or medicinal vapors when the workflow is still a direct-use near-field case.
- Product-centric supplement dosing only when the assessment is explicitly about a labeled
  consumer regimen rather than dietary intake.

Recommended request semantics:

- `productUseProfile.intendedUseFamily=medicinal` for TCM or other therapeutic herbal products.
- `productUseProfile.oralExposureContext=direct_use_medicinal` for medicinal oral regimens.
- `productUseProfile.intendedUseFamily=supplement` plus
  `productUseProfile.oralExposureContext=direct_use_supplement` when a supplement case is being
  treated as a direct-use product regimen.
- When pill or capsule counts matter, add `productUseProfile.dosageUnitCountPerEvent`,
  `productUseProfile.dosageUnitMassG`, and optionally `productUseProfile.dosageUnitLabel`
  so the regimen stays auditable as a counted oral-solid use pattern rather than only a
  bulk mass-per-event number.

## Dietary MCP Cases

- Food-mediated herbal intake, for example herbal teas or botanicals consumed as part of an
  ordinary diet.
- Nutrition-style supplement intake when the workflow is a dietary-consumption assessment
  rather than a product-use dosing case.
- Food-residue or commodity-residue workflows involving herbs, botanicals, or related foods.

These cases should not be sent as `exposureScenarioRequest.v1` payloads in Direct-Use Exposure
MCP.

## Fate-Oriented Seam

- Environmental-media oral intake from contaminated water or soil is not a Direct-Use request
  and is not Dietary by default.
- Start those workflows from Fate MCP `concentrationSurface.v1` outputs and move into a future
  concentration-to-intake consumer.

## Worked Examples

- TCM pill taken as part of a prescribed regimen -> `Direct-Use Exposure MCP`
- TCM balm applied to the skin -> `Direct-Use Exposure MCP`
- Botanical capsule taken as a labeled consumer regimen -> `Direct-Use Exposure MCP`
- Herbal tea consumed as part of normal diet -> `Dietary MCP`
- Herb-derived residue in food commodity -> `Dietary MCP`
- Soil or water ingestion of an herbal contaminant -> Fate seam, not Direct-Use by default

## Why This Split Matters

- It keeps medicinal product-use semantics separate from food-consumption semantics.
- It preserves auditability by making the routing basis explicit in the request contract.
- It avoids creating a separate TCM-specific MCP when the governing scientific distinction is
  already direct-use versus dietary pathway ownership.
"""


def toxmcp_suite_index_guide() -> str:
    return """# ToxMCP Suite Index

Use this guide as the one-page orientation layer for the current ToxMCP family.

## Current Service Map

- `Direct-Use Exposure MCP`
  owns deterministic direct-use and near-field external-dose construction, evidence
  reconciliation, bounded worker screening, and PBPK-ready external handoff packaging.
- `PBPK MCP`
  owns toxicokinetic simulation, internal-dose translation, and downstream TK-facing outputs.
- `Bioactivity-PoD MCP`
  owns bioactivity normalization, PoD/BER interpretation support, and curated downstream
  qualification.
- `ToxClaw`
  owns orchestration, evidence handling, refinement policy, and final NGRA-facing reporting.
- `Fate MCP` (planned sibling)
  should own environmental release, multimedia transfer, and compartment concentration surfaces.
- `Dietary MCP` (planned sibling)
  should own commodity residues, food-consumption mappings, and dietary oral intake.
- `Literature MCP` (optional future sibling)
  should own source normalization, extraction review, and evidence-pack curation rather than
  dose math.

## Shared Cross-MCP Contracts

- `chemicalIdentity.v1`
- `productUseEvidenceRecord.v1`
- `exposureScenarioDefinition.v1`
- `routeDoseEstimate.v1`
- `environmentalReleaseScenario.v1`
- `concentrationSurface.v1`
- `pbpkExternalImportBundle.v1`

Use these contracts to keep sibling MCPs interoperable without leaking tool-native payloads
across domain boundaries.

## Routing Summary

- Product-use, direct-use oral, residual-air reentry, indoor aerosol, and near-field worker
  screening -> `Direct-Use Exposure MCP`
- Herbal medicinal products, TCM regimens, and topical herbal products -> `Direct-Use Exposure MCP`
- Environmental source term or multimedia concentration question -> `Fate MCP`
- Dietary oral intake, food-mediated herbal intake, or food-residue question -> `Dietary MCP`
- Internal dose or TK simulation question -> `PBPK MCP`
- Bioactivity/PoD interpretation question -> `Bioactivity-PoD MCP`
- Cross-service case assembly, refinement choice, or reporting question -> `ToxClaw`

## How To Read This Repo In The Suite

- Start with `docs://service-selection-guide` for service ownership.
- Use `docs://cross-mcp-contract-guide` for the shared handoff shapes.
- Use `docs://capability-maturity-matrix` for maturity/readiness of the released surface.
- Use `docs://red-team-review-memo` for the strongest current hostile-review arguments and
  the repo's remaining governance gaps.
- Use `docs://suite-integration-guide` for detailed Direct-Use Exposure MCP boundary notes.
- Use `docs://herbal-medicinal-routing-guide` for TCM, herbal medicine, and supplement routing.

Static companion: `docs/toxmcp_suite_index.md`
"""


def capability_maturity_matrix_guide() -> str:
    return """# Capability Maturity Matrix

This guide explains how to interpret the released `0.1.0` surface.

The MCP now has four layers:

- a narrow core deterministic external-dose engine
- evidence normalization and integrated workflow helpers
- bounded worker routing, execution, and external exchange layers
- validation, benchmark, and release-governance publication

## Maturity Labels

- `benchmark-regressed`: deterministic behavior is locked to executable benchmark cases
  and release checks
- `curated`: reviewed defaults or packaged determinants are in use for the covered branch
- `external-normalized`: the MCP can ingest or reconcile external evidence or solver
  artifacts into governed contracts
- `bounded surrogate`: a deliberately simplified execution path is provided, with
  explicit solver limits
- `heuristic screening`: the branch remains screening-only and still depends on
  heuristic defaults

## Current Read

- Core deterministic exposure engine: `benchmark-regressed`, with a mix of curated and
  heuristic branches
- Evidence reconciliation and integrated workflow: `external-normalized`
- Worker inhalation support: `bounded surrogate` plus governed external ART exchange
- Worker dermal support: `bounded surrogate` with curated and heuristic elements
- Validation and release governance: `benchmark-regressed`

## How To Use This

- Prefer benchmark-regressed and curated branches when showcasing regulatory trust.
- Treat external-normalized layers as contract-governed bridges, not as reimplemented
  upstream systems.
- Treat heuristic screening branches as useful triage outputs, not decision-ready conclusions.

Static companion: `docs/capability_maturity_matrix.md`
"""


def repository_slug_decision_guide() -> str:
    return """# Repository Slug Decision

The public product name is now:

- `Direct-Use Exposure MCP`

The current public GitHub repository slug is still:

- `ToxMCP/direct-use-exposure-mcp`

The Python package, import path, CLI command, and MCP server identifiers also remain stable
through the `v0.1.x` line.

## Staged Naming Policy

- adopt the clearer product name now
- keep the current slug and technical identifiers through `v0.1.x`
- treat any full repo/package rename as a later compatibility-managed release step

## Why It Is Staged

- badges, clone URLs, and existing references already point to the current slug
- release and review artifacts already encode the current slug
- renaming the technical identifiers immediately would create needless churn during the first
  released line

Static companion: `docs/adr/0004-repository-slug.md`
"""


def red_team_review_memo_guide() -> str:
    return """# Red-Team Review Memo

This memo captures hostile-review arguments that a skeptical toxicologist, exposure physicist,
or regulator could use to attack Direct-Use Exposure MCP, then evaluates which criticisms are
substantive, which are overstated, and what the repo should do next.

## Summary

- The strongest valid attack is systemic-risk / monoculture risk.
- The strongest partly valid attacks are transparency-by-exhaustion, default overuse, and
  precision-without-accuracy in heuristic aerosol branches.
- The correct response is not less transparency. It is layered transparency and stronger
  human-review gating for low-evidence scenarios.

## Attack Matrix

### Transparency by Exhaustion

- Validity: partly valid
- Current mitigation:
  - explicit provenance
  - assumptions
  - limitations
  - validation artifacts
  - verification artifacts
- Remaining gap:
  human review still needs a shorter first-pass digest
- Recommended fix:
  publish a one-page human review summary above the full bundle

### Automated Ignorance / Default Trap

- Validity: valid
- Current mitigation:
  defaults are versioned, source-tagged, and surfaced explicitly
- Remaining gap:
  some default-heavy cases still look too frictionless
- Recommended fix:
  apply stronger fit-for-purpose downgrades and unavoidable warning language when heuristic
  defaults dominate the run

### Scientific Anachronism

- Validity: partly valid
- Current mitigation:
  bounded branches are already framed as screening/surrogate logic, not full high-tier physics
- Remaining gap:
  users can still overread “mechanistic” language if break conditions are not stated plainly
- Recommended fix:
  identify empirical model families by name and list their main break conditions

### Systemic Risk / Monoculture

- Validity: strongly valid
- Current mitigation:
  benchmark regression, goldset linkage, defaults versioning, release metadata, and executable
  validation checks
- Remaining gap:
  a common engine still needs external comparison and periodic adversarial review
- Recommended fix:
  treat independent comparison and red-team review as governance requirements, not optional extras

### Expertise Erasure

- Validity: only if the system is presented badly
- Current mitigation:
  the MCP does not own PBPK execution, BER, WoE, PoD, or final risk conclusions
- Remaining gap:
  workflow users can still misuse a structured engine operationally
- Recommended fix:
  keep expert-review boundaries explicit in operator-facing outputs

### Aerosol Pseudoscience / Precision without Accuracy

- Validity: valid
- Current mitigation:
  aerosol semantics are bounded, family-aware, and quality-flagged rather than hidden
- Remaining gap:
  some heuristic aerosol branches still look more precise than the evidence deserves
- Recommended fix:
  round heuristic outputs more conservatively and label them as screening-resolution

## Bottom Line

The right answer to hostile criticism is not to deny uncertainty. It is to show that defaults,
model limits, benchmark posture, and human-review boundaries are already first-class, then keep
improving the human audit surface.

Static companion: `docs/red_team_review_memo.md`
"""


def worker_routing_guide() -> str:
    return """# Worker Routing Guide

Worker support currently stays inside Direct-Use Exposure MCP only while the shared
task/use abstractions still hold. Use the worker router to decide whether the task can
stay on a bounded screening path in this MCP or should be escalated to a future
occupational adapter.

## Tool Surface

- Tool: `exposure_route_worker_task`
- Request schema: `workerTaskRoutingInput.v1`
- Response schema: `workerTaskRoutingDecision.v1`
- Guidance resource: `docs://worker-routing-guide`

## Detection Rule

- Mark worker context explicitly through `population_profile.demographic_tags`, for example
  `worker`, `occupational`, or `professional`.
- The router also checks `population_group` for worker-like tokens, but explicit
  demographic tags are the preferred trigger.

## Current Routing Policy

- Worker spray inhalation task -> `exposure_build_inhalation_tier1_screening_scenario`
- Worker inhalation task that still behaves like a bounded room-average direct-use event ->
  `exposure_build_inhalation_screening_scenario`
- Worker dermal or oral task with supported direct-use semantics ->
  `exposure_build_screening_exposure_scenario`
- Worker task needing occupational Tier 2 refinement ->
  future `ART` or `Stoffenmanager` adapter path
- Worker dermal task needing absorbed-dose or PPE-aware refinement ->
  `exposure_export_worker_dermal_absorbed_dose_bridge`

## Current Guardrails

- Current worker support remains deterministic screening only.
- The current MCP does not implement `ECETOC TRA`, `ART`, `Stoffenmanager`, measured
  workplace monitoring, or regulatory compliance logic.
- Worker-tagged scenarios now emit explicit worker quality flags, worker boundary
  limitations, and worker routing metadata in `route_metrics`.

## Client Guidance

- Run `exposure_route_worker_task` before constructing a worker scenario when task
  mechanics or tier choice are uncertain.
- If the router still recommends a current MCP tool, preserve emitted `tier_semantics`,
  `quality_flags`, `limitations`, and worker routing fields.
- If the router recommends a future occupational adapter, treat the current MCP as out of
  scope for that task rather than forcing a consumer-style scenario shape.
- For worker dermal absorbed-dose or PPE work, use the dermal bridge and adapter guides rather
  than trying to reinterpret the shared screening scenario as an absorbed-dose result.
"""


def worker_tier2_bridge_guide() -> str:
    return """# Worker Tier 2 Bridge Guide

The worker Tier 2 bridge exports a normalized handoff package for future occupational
inhalation adapters such as an `ART`-aligned path. It does not execute a Tier 2 worker
solver itself.

## Tool Surface

- Tool: `exposure_export_worker_inhalation_tier2_bridge`
- Request schema: `exportWorkerInhalationTier2BridgeRequest.v1`
- Response schema: `workerInhalationTier2BridgePackage.v1`
- Guidance resource: `docs://worker-tier2-bridge-guide`

## What the Bridge Contains

- A preserved worker routing decision
- A typed worker task context
- A normalized adapter request payload
- A future adapter tool-call envelope
- A compatibility/readiness report with missing fields and next steps

## Current Intended Use

- Export the bridge after worker routing indicates a future Tier 2 occupational path
- Preserve the package as a structured handoff artifact for a future `ART` or
  `Stoffenmanager` adapter
- Send `toolCall.arguments` into `worker_ingest_inhalation_tier2_task` when the downstream
  path targets the current ART-side intake boundary
- Use the bridge to force explicit collection of workplace setting, task duration,
  ventilation, and emission-description fields before escalation

## Current Guardrails

- The bridge is inhalation-only for now.
- The bridge is strongest for spray or aerosol worker tasks, though any inhalation request
  can still be normalized into the package.
- Direct-Use Exposure MCP does not execute a Tier 2 worker model here.
- Do not reinterpret bridge export as a solved occupational estimate, compliance result,
  or measured workplace exposure.

## Client Guidance

- Run `exposure_route_worker_task` first when tier choice is still uncertain.
- Use `compatibilityReport.missingFields` as the collection checklist before sending the
  package into a future worker adapter.
- Keep `adapterRequest`, `toolCall`, `qualityFlags`, and `provenance` together so the
  downstream occupational path stays auditable.
"""


def worker_art_adapter_guide() -> str:
    return """# Worker ART Adapter Guide

The ART-side worker inhalation adapter ingests the normalized Tier 2 bridge payload and
converts it into an ART-aligned intake envelope. It still does not execute ART itself.

## Tool Surface

- Tool: `worker_ingest_inhalation_tier2_task`
- Request schema: `workerInhalationTier2AdapterRequest.v1`
- Response schema: `workerInhalationTier2AdapterIngestResult.v1`
- Guidance resource: `docs://worker-art-adapter-guide`

## What the Adapter Ingest Does

- Validates that the request targets a currently supported worker Tier 2 family
- Normalizes worker task fields into an ART-aligned intake envelope
- Matches the task against packaged determinant templates for common worker inhalation families
- Preserves screening handoff context and worker routing metadata
- Reports missing intake fields and whether the payload is ready for downstream execution

## Current Support Boundary

- The current ingest path supports `targetModelFamily=art`
- Other families remain preserved handoff payloads only
- The adapter currently covers inhalation tasks only
- The adapter emits intake-ready structured inputs, not an occupational exposure result
- Template alignment can be `aligned`, `partial`, `heuristic`, or `none`
- Current packaged families include janitorial disinfectant sprays, pest-control sprays,
  janitorial pump sprays, paint/coating aerosols, solvent/degreasing vapor tasks,
  open mixing/blending and enclosed transfer vapor tasks, outdoor or enhanced-ventilation
  spray variants, and generic spray/vapor fallbacks

## Current Guardrails

- Do not interpret adapter ingest as an ART run, workplace simulation, or compliance result
- Treat `artTaskEnvelope.artInputs` as a normalized execution payload, not a validated set of
  measured worker determinants
- Review `artTaskEnvelope.determinantTemplateMatch` before treating packaged determinants as
  task-specific ART inputs
- Preserve `qualityFlags`, `limitations`, and `provenance` so downstream review can see which
  fields remained heuristic or screening-derived

## Client Guidance

- Prefer `exposure_export_worker_inhalation_tier2_bridge` first so the worker routing
  decision and bridge provenance stay attached to the request
- Send the bridge package `toolCall.arguments` directly into
  `worker_ingest_inhalation_tier2_task`
- Treat `readyForAdapterExecution=true` as "the intake payload is complete enough to hand to an
  ART-side execution boundary", not as "the worker problem is solved"
- Use `worker_export_inhalation_art_execution_package` when the next step is a real external
  ART-side run rather than the local surrogate execution tool
"""


def worker_art_execution_guide() -> str:
    return """# Worker ART Execution Guide

The worker inhalation execution tool runs the current ART-aligned surrogate screening kernel.
It preserves the strongest available inhalation screening baseline, then applies explicit worker
control and respiratory-protection modifiers with a transparent assumptions ledger.

## Tool Surface

- Tool: `worker_execute_inhalation_tier2_task`
- Request schema: `executeWorkerInhalationTier2Request.v1`
- Response schema: `workerInhalationTier2ExecutionResult.v1`
- Guidance resource: `docs://worker-art-execution-guide`

## What the Execution Kernel Does

- Reuses the normalized worker inhalation adapter request as the executable input contract
- Reuses the Tier 1 NF/FF spray kernel when Tier 1 spray geometry is available
- Reuses the Tier 0 room-average inhalation kernel for supported spray tasks outside Tier 1
- Falls back to a labeled room-average vapor-release surrogate for vapor-generating tasks
- Applies bounded volatility saturation caps when vapor pressure and molecular weight are supplied
- Applies bounded first-order deposition sinks to room-air loss terms
- Can apply a bounded task-intensity factor to the inhalation rate when the worker task
  explicitly declares light, moderate, or high effort
- Applies worker control and respiratory-protection factors after the baseline kernel,
  including optional `levFamily` and `hoodFaceVelocityMPerS` refinements when callers
  can supply them, with bounded measured-profile bands for supported LEV families
- Returns both the preserved baseline dose and the control-adjusted worker inhalation dose
- Preserves determinant-template alignment, quality flags, limitations, and provenance

## Current Support Boundary

- The executable path currently supports `targetModelFamily=art`
- The execution kernel is intentionally bounded and transparent, not a real ART solver
- Control and respiratory-protection effects are represented by heuristic adjustment factors
- Explicit `levFamily` and `hoodFaceVelocityMPerS` inputs refine those control factors, but
  still remain bounded screening semantics rather than measured LEV performance modeling,
  even when supported LEV-family measured-profile bands are applied
- Task intensity is represented by a bounded inhalation-rate factor, not measured minute
  ventilation
- Volatility and aerosol removal are represented by bounded screening caps and
  first-order loss terms
- Vapor-generating tasks use a room-average surrogate rather than determinant-specific ART vapor
  terms
- Callers can override `controlFactor`, `respiratoryProtectionFactor`, and
  `vaporReleaseFraction`

## Current Guardrails

- Do not treat the result as a real ART execution or measured workplace concentration
- Do not treat the respiratory-protection factor as a compliance-assured assigned protection
  factor
- Do not treat the result as a final occupational compliance determination
- Keep `manualReviewRequired`, `qualityFlags`, `limitations`, and the determinant-template match
  attached to any PBPK or NGRA handoff derived from this result

## Client Guidance

- Use `exposure_export_worker_inhalation_tier2_bridge` first when worker routing and bridge
  provenance need to stay attached to the execution request
- Use `worker_ingest_inhalation_tier2_task` first if you want to inspect the normalized
  determinant-template match before execution
- Use `worker_execute_inhalation_tier2_task` when you need a bounded worker inhalation estimate
  with explicit control and respiratory-protection modifiers
- Use `worker_export_inhalation_art_execution_package` and
  `worker_import_inhalation_art_execution_result` when you have access to a real external
  ART-side execution path and want to bring the result back into the governed MCP contract
- Review the assumptions ledger for `worker_control_factor`,
  `respiratory_protection_factor`, `worker_task_intensity_factor`, and any
  vapor-release surrogate assumptions before downstream use
"""


def worker_art_external_exchange_guide() -> str:
    return """# Worker ART External Exchange Guide

The external ART exchange path is the real solver boundary for worker inhalation Tier 2
work. It exports a normalized ART-ready payload from the current adapter intake, then imports
the completed external ART result back into the governed worker execution schema.

## Tool Surface

- Tool: `worker_export_inhalation_art_execution_package`
- Request schema: `exportWorkerArtExecutionPackageRequest.v1`
- Response schema: `workerArtExternalExecutionPackage.v1`
- Tool: `worker_import_inhalation_art_execution_result`
- Request schema: `importWorkerArtExecutionResultRequest.v1`
- Response schema: `workerInhalationTier2ExecutionResult.v1`
- Guidance resource: `docs://worker-art-external-exchange-guide`

## What the Export Tool Does

- Reuses the normalized worker Tier 2 adapter request as the external execution contract
- Preserves the ART determinant-template match and normalized `artInputs`
- Emits an `externalExecutionPayload` object suitable for a real ART-side adapter or runner
- Emits a `resultImportToolCall.argumentTemplate` so clients can re-import the external result
  without rebuilding the request shape manually

## What the Import Tool Does

- Revalidates the worker Tier 2 adapter request against the current ART-side intake boundary
- Accepts a normalized external ART result with concentration, inhaled-mass, or normalized-dose
  metrics
- Can also derive that normalized summary from named raw-artifact adapters, including:
  `art_worker_result_summary_json_v1`
- Also supports a nested runner export shape through
  `art_worker_execution_report_json_v1`
- Also supports flat CSV exports through
  `art_worker_result_summary_csv_wide_v1` and
  `art_worker_result_summary_csv_key_value_v1`
- Also supports semicolon-delimited spreadsheet CSV exports through
  `art_worker_result_summary_csv_semicolon_v1`
- Preserves the current internal screening baseline for comparison
- Returns the imported Tier 2 result in the same governed
  `workerInhalationTier2ExecutionResult.v1` schema used elsewhere in the MCP

## Current Guardrails

- Direct-Use Exposure MCP still does not run ART internally.
- The import path normalizes and compares the external result; it does not independently verify
  the external solver.
- Keep `rawArtifacts`, `resultPayload`, `qualityNotes`, `qualityFlags`, `limitations`,
  and `provenance`
  attached to any downstream PBPK or NGRA use.
- Do not treat the imported result as a final occupational compliance determination.

## Client Guidance

- Use `exposure_export_worker_inhalation_tier2_bridge` first when worker routing and bridge
  provenance need to remain attached.
- Use `worker_ingest_inhalation_tier2_task` if you want to inspect template alignment before
  exporting the external execution package.
- Use `worker_export_inhalation_art_execution_package` when a real external ART-side runner is
  available.
- Prefer preserving a structured JSON runner summary on `rawArtifacts[].contentJson` so the
  import path can reconstruct the normalized result even when a client does not separately emit
  `resultPayload`.
- If your runner emits a richer nested report, preserve it under
  `schemaVersion='artWorkerExecutionReport.v1'`; the import path will normalize it through the
  dedicated execution-report adapter.
- If a runner only emits CSV, preserve it on `rawArtifacts[].contentText` with
  `mediaType='text/csv'`; the import path can read either one-row summary CSVs or `key,value`
  CSV exports directly.
- If the runner output has passed through an EU spreadsheet workflow and now uses semicolon
  separators, the import path can read that through the semicolon CSV adapter as well.
- When the client already knows the runner format, set `rawArtifacts[].adapterHint` so the
  import path does not need to infer the adapter.
- Use `worker_import_inhalation_art_execution_result` to bring the completed external result
  back into the governed MCP schema with screening-baseline comparison preserved.
"""


def worker_dermal_bridge_guide() -> str:
    return """# Worker Dermal Bridge Guide

The worker dermal bridge exports a normalized absorbed-dose and PPE handoff package from a
dermal screening request. It preserves the external-loading source request while forcing the
caller to declare the contact pattern, body zone, surface-loading context, and PPE state
needed for a future occupational dermal workflow.

## Tool Surface

- Tool: `exposure_export_worker_dermal_absorbed_dose_bridge`
- Request schema: `exportWorkerDermalAbsorbedDoseBridgeRequest.v1`
- Response schema: `workerDermalAbsorbedDoseBridgePackage.v1`
- Guidance resource: `docs://worker-dermal-bridge-guide`

## What the Bridge Exports

- A typed worker dermal task context
- Optional `barrierMaterial` and `chemicalContext` descriptors for bounded downstream
  material-aware and chemistry-aware refinement
- A normalized absorbed-dose/PPE adapter request payload
- A future adapter tool-call envelope
- A compatibility report with missing dermal-task fields and next steps

## Current Intended Use

- Export the bridge when worker routing indicates that external dermal loading is no longer a
  sufficient endpoint
- Preserve the package as a structured handoff artifact for a future dermal absorbed-dose or
  PPE-aware occupational workflow
- Send `toolCall.arguments` into `worker_ingest_dermal_absorbed_dose_task` when the downstream
  path targets the current dermal adapter boundary
- Send a typed execution request into `worker_execute_dermal_absorbed_dose_task` when you want
  the current bounded absorbed-dose kernel rather than an ingest-only handoff
- Use the bridge to force explicit collection of contact duration, contact pattern, exposed body
  areas, PPE state, and surface-loading context before escalation

## Current Guardrails

- The bridge is dermal-only for now.
- The bridge prepares a future occupational handoff; it does not execute a dermal absorption,
  glove breakthrough, or compliance model.
- The bridge is strongest when `contactPattern`, `exposedBodyAreas`, and `ppeState` are all
  explicit rather than inferred.
- `barrierMaterial` and `chemicalContext` are optional refinement hints; they do not turn the
  bridge itself into a permeation or breakthrough model.

## Client Guidance

- Run `exposure_route_worker_task` first when the worker dermal path is still uncertain.
- Use `compatibilityReport.missingFields` as the collection checklist before sending the package
  into a dermal adapter.
- Keep `adapterRequest`, `toolCall`, `qualityFlags`, and `provenance` together so the
  downstream dermal path stays auditable.
"""


def worker_dermal_adapter_guide() -> str:
    return """# Worker Dermal Adapter Guide

The dermal worker adapter ingests the normalized bridge payload and converts it into an
absorbed-dose/PPE-oriented intake envelope. It does not execute a dermal absorption solver.

## Tool Surface

- Tool: `worker_ingest_dermal_absorbed_dose_task`
- Request schema: `workerDermalAbsorbedDoseAdapterRequest.v1`
- Response schema: `workerDermalAbsorbedDoseAdapterIngestResult.v1`
- Guidance resource: `docs://worker-dermal-adapter-guide`

## What the Adapter Ingest Does

- Validates that the request targets the currently supported dermal absorbed-dose family
- Normalizes worker dermal fields into a PPE-aware intake envelope
- Matches the task against packaged determinant templates for common worker dermal families
- Preserves screening handoff context and worker routing metadata
- Preserves optional `barrierMaterial` and `chemicalContext` inputs into the intake envelope
- Reports missing intake fields and whether the payload is ready for downstream execution

## Current Support Boundary

- The current ingest path supports `targetModelFamily=dermal_absorption_ppe`
- Other families remain preserved handoff payloads only
- The adapter currently covers dermal tasks only
- The adapter emits intake-ready structured inputs. Execution now happens in the separate
  `worker_execute_dermal_absorbed_dose_task` tool.
- Template alignment can be `aligned`, `partial`, `heuristic`, or `none`
- Current packaged families include janitorial wet-wipe glove contact, solvent transfer with
  gloves, generic gloved or ungloved hand contact, and generic liquid splash contact

## Current Guardrails

- Do not interpret adapter ingest as a dermal absorption run, glove breakthrough calculation,
  or compliance result
- Treat `dermalTaskEnvelope.dermalInputs` as a normalized execution payload, not a validated set
  of measured dermal determinants
- Review `dermalTaskEnvelope.determinantTemplateMatch` before treating packaged determinants as
  task-specific adapter inputs
- Preserve `qualityFlags`, `limitations`, and `provenance` so downstream review can see which
  fields remained generic or screening-derived

## Client Guidance

- Prefer `exposure_export_worker_dermal_absorbed_dose_bridge` first so the worker routing
  decision and bridge provenance stay attached to the request
- Send the bridge package `toolCall.arguments` directly into
  `worker_ingest_dermal_absorbed_dose_task`
- Treat `readyForAdapterExecution=true` as "the intake payload is complete enough to hand to a
  downstream dermal workflow", not as "the dermal worker problem is solved"
- Use `worker_execute_dermal_absorbed_dose_task` when you want the current PPE-aware execution
  kernel to produce a bounded absorbed-dose estimate
"""


def worker_dermal_execution_guide() -> str:
    return """# Worker Dermal Execution Guide

The worker dermal execution tool runs the current PPE-aware absorbed-dose screening kernel. It
starts from the skin-boundary dermal loading implied by the adapter request or an explicit
external mass override, then applies PPE penetration and bounded dermal absorption factors.

## Tool Surface

- Tool: `worker_execute_dermal_absorbed_dose_task`
- Request schema: `executeWorkerDermalAbsorbedDoseRequest.v1`
- Response schema: `workerDermalAbsorbedDoseExecutionResult.v1`
- Guidance resource: `docs://worker-dermal-execution-guide`

## What the Execution Kernel Does

- Reuses the normalized dermal adapter request as the executable input contract
- Re-derives or accepts external skin mass per day at the skin boundary
- Applies a bounded retained-loading cap and reports excess mass as runoff or non-retained contact
- Applies residual PPE penetration before absorption is calculated, with a bounded
  breakthrough-lag profile when barrier material and contact duration are available
- Applies bounded absorption logic from physical form, contact pattern, contact duration, and
  skin condition unless the caller overrides those factors
- Applies optional bounded `barrierMaterial` and `chemicalContext` modifiers when those
  descriptors are supplied, including a duration-aware evaporation-competition term for
  volatile contacts
- Returns both normalized external skin dose and normalized absorbed dermal dose
- Preserves the determinant-template match, assumptions ledger, limitations, and provenance

## Current Support Boundary

- The executable path currently supports `targetModelFamily=dermal_absorption_ppe`
- The execution kernel is intentionally bounded and transparent, not a chemical-specific
  permeability solver
- PPE effects are represented as residual penetration factors with optional bounded
  `barrierMaterial`, chemistry, and lag-time modifiers, not certified glove-breakthrough
  curves
- Skin-boundary loading is capped by a retained surface-loading heuristic before PPE and
  absorption are applied
- Absorption is represented by screening factors with optional bounded `chemicalContext`
  and evaporation-competition modifiers, not measured permeability data
- Callers can override `externalSkinMassMgPerDay`, `bodyZoneSurfaceAreaCm2`,
  `ppePenetrationFactor`, `dermalAbsorptionFraction`, and `contactDurationFactor`

## Current Guardrails

- Do not treat the absorbed dose as a validated occupational dermal model result
- Do not treat the PPE factor as glove certification or permeation evidence
- Do not treat the result as a final occupational compliance determination
- Keep `manualReviewRequired`, `qualityFlags`, and `limitations` attached to any PBPK or NGRA
  handoff derived from this result

## Client Guidance

- Use `exposure_export_worker_dermal_absorbed_dose_bridge` first when the dermal worker context
  needs to stay auditable from routing through execution
- Use `worker_ingest_dermal_absorbed_dose_task` first if you want to inspect the normalized
  determinant-template match before running execution
- Use `worker_execute_dermal_absorbed_dose_task` when you need a bounded absorbed-dose estimate
  with explicit PPE and absorption modifiers
- Supply `barrierMaterial` and `chemicalContext` when available to move the screening kernel
  away from the most generic dermal assumptions
- Review the assumptions ledger for `ppe_penetration_factor`,
  `dermal_absorption_fraction`, and any execution overrides before downstream use
"""


def integrated_exposure_workflow_guide() -> str:
    return """# Integrated Exposure Workflow Guide

The integrated exposure workflow runs the local evidence-to-scenario-to-PBPK handoff chain in
one auditable call. It normalizes CompTox, SCCS, SCCS opinion, CosIng, ConsExpo, nanomaterial,
and microplastics records into the generic evidence contract, reconciles them against the source
request, builds the effective scenario, and can emit the PBPK-side handoff objects immediately.

## Tool Surface

- Tool: `exposure_run_integrated_workflow`
- Request schema: `runIntegratedExposureWorkflowInput.v1`
- Response schema: `integratedExposureWorkflowResult.v1`
- Guidance resource: `docs://integrated-exposure-workflow-guide`

## What the Workflow Does

- Accepts one source request plus optional CompTox, SCCS, SCCS opinion, CosIng, ConsExpo,
  nanomaterial, microplastics, and additional evidence records
- CompTox, SCCS, SCCS opinion, CosIng, ConsExpo, nanomaterial, and microplastics records are
  normalized into `productUseEvidenceRecord.v1`
- Reconciles the evidence against the source request and selects an effective request
- Preserves inhalation request subtypes so Tier 1 spray requests stay Tier 1 after enrichment
- Builds the scenario from the effective request using the existing deterministic engines
- Evaluates PBPK compatibility for the built scenario
- Optionally exports both `pbpkScenarioInput.v1` and the external-import bundle package

## Current Guardrails

- The workflow does not call a live external CompTox, SCCS, CosIng, or ConsExpo MCP. It only uses
  the typed records supplied by the caller.
- Incompatible evidence does not have to stop the workflow. When allowed, the source request is
  retained and the evidence rejection is surfaced explicitly.
- PBPK exports remain upstream external-exposure handoffs only. They are not PBPK execution or
  internal-dose results.
- Review `evidenceStrategy`, `reconciliationReport`, `manualReviewRequired`, `qualityFlags`,
  and `limitations` before downstream use.

## Client Guidance

- Use this tool when you want a single audited response instead of separate evidence,
  scenario-build, and PBPK-export calls.
- Prefer supplying regional evidence packs such as SCCS, ConsExpo, or reviewed dossier records
  when the product-use context is jurisdiction-sensitive.
- For EU cosmetics, prefer SCCS guidance records as the primary reviewed use-profile source and
  use ConsExpo as a supporting mechanistic consumer-model source.
- Use SCCS opinions when ingredient-specific cosmetics context matters, CosIng for identity and
  function metadata, and particle-aware evidence records when nano or microparticle properties
  affect the direct-use scenario semantics.
- Use `continueOnEvidenceReject=false` only when incompatible evidence should hard-stop the
  workflow.
- Keep the returned `effectiveRequest`, `scenario`, and PBPK handoffs together so the chain
  remains auditable end to end.
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


def inhalation_residual_air_reentry_guide() -> str:
    return """# Inhalation Residual-Air Reentry Guide

## Current State

- `v0.1.0` now ships a first-class residual-air reentry inhalation tool:
  `exposure_build_inhalation_residual_air_reentry_scenario`
- Request schema: `inhalationResidualAirReentryScenarioRequest.v1`
- Response schema: `exposureScenario.v1`
- The tool now supports two explicit modes:
  - `anchored_reentry`: starts from a supplied room-air concentration at reentry start
  - `native_treated_surface_reentry`: derives the reentry air profile from treated-surface
    chemical mass, a bounded first-order surface-emission term, and room-loss terms

## Required Inputs

- `product_use_profile.application_method=residual_air_reentry`
- For `anchored_reentry`: `airConcentrationAtReentryStartMgPerM3`
- For `native_treated_surface_reentry`: either
  `treatedSurfaceChemicalMassMg` or enough product-use data to derive treated-surface source
  mass from `use_amount_per_event` and `concentration_fraction`
- `product_use_profile.exposure_duration_hours` or a justified default room duration
- `population_profile.inhalation_rate_m3_per_hour` and `body_weight_kg`, explicit or defaulted

## Optional Inputs

- `reentryMode`
- `additionalDecayRatePerHour`
- `postApplicationDelayHours`
- `surfaceEmissionRatePerHour`
- `treatedSurfaceResidueFraction`
- `physchemContext` to refine native treated-surface emission-rate resolution and saturation
  capping
- Room-volume and air-exchange overrides when the monitored or assessed room differs from the
  shared defaults

## Calculation Semantics

- `anchored_reentry` starts from the supplied concentration at reentry start and applies:
  `total_decay_rate = air_exchange_rate + additional_decay_rate + deposition_rate`
- `native_treated_surface_reentry` derives the reentry air profile from:
  treated-surface chemical mass, a bounded first-order surface-emission rate, room volume,
  air exchange, additional decay, and deposition
- When `physchemContext.vaporPressureMmhg` and `molecularWeightGPerMol` are available, bounded
  saturation capping is applied to prevent impossible supersaturated room-air values
- Reports:
  `average_air_concentration_mg_per_m3`
- Reports:
  `air_concentration_at_reentry_end_mg_per_m3`
- Reports:
  `inhaled_mass_mg_per_day`
- Reports:
  `normalized_external_dose`

## What This Solves

- Post-application room-air screening for treated indoor environments
- Literature-anchored reentry scenarios such as chlorpyrifos or diazinon indoor air studies
- Same-room treated-surface screening when no measured reentry-start concentration is available
- PBPK-ready external-dose handoff when the exposure window begins after application

## Guardrails

- This is not an application-phase spray-cloud model
- `anchored_reentry` is only as credible as the supplied reentry-start concentration anchor and
  decay assumption
- `native_treated_surface_reentry` is a bounded first-order surface-emission screening model,
  not a chamber-validated SVOC partitioning or heterogeneous indoor-surface solver
- A narrow executable chlorpyrifos reentry-start concentration band plus a sparse 4-hour to
  24-hour room-air time-series pack now exist for this domain, but treated-surface emission
  and decay dynamics remain only partially anchored
"""


def validation_framework() -> str:
    report = build_validation_dossier_report()
    reference_manifest = ValidationReferenceBandRegistry.load().manifest()
    time_series_manifest = ValidationTimeSeriesReferenceRegistry.load().manifest()
    goldset = load_goldset_manifest()
    lines = [
        "# Validation Framework",
        "",
        "Current validation posture is verification plus benchmark regression, with a typed",
        "validation dossier for external-reference readiness and open evidence gaps.",
        "",
        "## Benchmark Domains",
        "",
        "- Use `validation://coverage-report` or `docs://validation-coverage-report` for a",
        "  domain-by-domain trust summary across benchmark cases, external datasets,",
        "  reference bands, time-series packs, and goldset links.",
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
            (
                f"- The executable time-series manifest currently publishes "
                f"`{time_series_manifest.pack_count}`"
            ),
            (
                "  sparse reference packs through `validation://time-series-packs`."
            ),
            "- Current executable checks cover hand-cream loading realism for hand-scale",
            "  dermal scenarios and wet-cloth contact mass realism for household-cleaner",
            "  wipe scenarios.",
            (
                "- Current executable checks also cover air-space insecticide aerosol "
                "concentration realism for a narrow household mosquito aerosol room-air "
                "benchmark."
            ),
            (
                "- Residual-air reentry now also supports sparse time-series checks for "
                "chlorpyrifos room-air decay when the assessed reentry window lands on the "
                "published 24-hour comparison point."
            ),
            (
                f"- A separate goldset short list publishes "
                f"`{len(goldset.get('cases', []))}` externally anchored showcase cases "
                "through `benchmarks://goldset`."
            ),
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


def validation_time_series_packs_guide() -> str:
    manifest = ValidationTimeSeriesReferenceRegistry.load().manifest()
    lines = [
        "# Validation Time-Series Packs",
        "",
        "These sparse packs back time-resolved executable validation checks where a route",
        "model can be compared against more than one published concentration snapshot.",
        "",
        f"- Reference version: `{manifest.reference_version}`",
        f"- Manifest hash: `{manifest.reference_hash_sha256}`",
        f"- Pack count: `{manifest.pack_count}`",
        f"- Point count: `{manifest.point_count}`",
        f"- Resource path: `{manifest.path}`",
        "",
        "## Packs",
        "",
    ]
    for pack in manifest.packs:
        selectors = ", ".join(
            f"{key}={value}" for key, value in sorted(pack.applicable_selectors.items())
        ) or "global"
        lines.append(
            f"- `{pack.reference_pack_id}` [{pack.domain}] "
            f"time reference: `{pack.time_coordinate_reference}`"
        )
        lines.append(f"  dataset: `{pack.reference_dataset_id}`")
        lines.append(f"  selectors: {selectors}")
        lines.append(f"  note: {pack.note}")
        for point in pack.points:
            lines.append(
                f"  point `{point.point_id}` -> `{point.check_id}` at "
                f"`{point.time_coordinate_hours}` h"
            )
            lines.append(
                f"    metric: `{point.scenario_metric_key}` "
                f"`{point.reference_lower}` to `{point.reference_upper}` `{point.unit}`"
            )
            lines.append(f"    note: {point.note}")
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
            "ingestion_fraction",
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


def validation_coverage_report_markdown() -> str:
    report = build_validation_coverage_report()
    lines = [
        "# Validation Coverage Report",
        "",
        "This report summarizes current trust posture by validation domain using the governed",
        "benchmark corpus, external dataset register, executable reference bands, executable",
        "time-series packs, and showcase goldset links.",
        "",
        f"- Policy version: `{report.policy_version}`",
        f"- Benchmark defaults version: `{report.benchmark_defaults_version}`",
        f"- Reference-band version: `{report.reference_band_version}`",
        f"- Time-series version: `{report.time_series_reference_version}`",
        f"- Goldset version: `{report.goldset_version}`",
        f"- Domain count: `{report.domain_count}`",
        f"- Benchmark cases: `{report.benchmark_case_count}`",
        f"- External datasets: `{report.external_dataset_count}`",
        f"- Reference bands: `{report.reference_band_count}`",
        f"- Time-series packs: `{report.time_series_pack_count}`",
        f"- Goldset cases: `{report.goldset_case_count}`",
        "",
        "## Goldset Coverage Mix",
        "",
    ]
    for coverage_status, count in sorted(report.goldset_coverage_counts.items()):
        lines.append(f"- `{coverage_status}`: `{count}`")
    if report.unmapped_goldset_case_ids:
        lines.append(
            "- Unmapped goldset cases: "
            + ", ".join(f"`{item}`" for item in report.unmapped_goldset_case_ids)
        )
    lines.extend(["", "## Domain Coverage", ""])
    for item in report.domain_summaries:
        lines.append(
            f"- `{item.domain}` [{item.coverage_level}] "
            f"tier `{item.highest_supported_uncertainty_tier.value}`"
        )
        lines.append(f"  summary: {item.summary}")
        if item.benchmark_case_ids:
            lines.append(
                "  benchmarks: " + ", ".join(f"`{case_id}`" for case_id in item.benchmark_case_ids)
            )
        if item.goldset_case_ids:
            lines.append(
                "  goldset: " + ", ".join(f"`{case_id}`" for case_id in item.goldset_case_ids)
            )
        if item.external_dataset_ids:
            lines.append(
                "  datasets: "
                + ", ".join(f"`{dataset_id}`" for dataset_id in item.external_dataset_ids)
            )
        if item.executable_reference_band_ids:
            lines.append(
                "  reference bands: "
                + ", ".join(f"`{band_id}`" for band_id in item.executable_reference_band_ids)
            )
        if item.time_series_pack_ids:
            lines.append(
                "  time-series packs: "
                + ", ".join(f"`{pack_id}`" for pack_id in item.time_series_pack_ids)
            )
        if item.open_gap_ids:
            lines.append(
                "  open gaps: " + ", ".join(f"`{gap_id}`" for gap_id in item.open_gap_ids)
            )
    lines.extend(["", "## Notes", ""])
    lines.extend(f"- {item}" for item in report.overall_notes)
    return "\n".join(lines)


def goldset_benchmark_guide() -> str:
    manifest = load_goldset_manifest()
    cases = manifest.get("cases", [])
    coverage_counts: dict[str, int] = {}
    for item in cases:
        coverage = str(item.get("coverage_status", "unknown"))
        coverage_counts[coverage] = coverage_counts.get(coverage, 0) + 1

    lines = [
        "# Goldset Benchmark Guide",
        "",
        "The goldset is the short list of externally anchored, recognizable showcase cases",
        "used to explain what this MCP can already defend, what it can demonstrate through",
        "integration, and where the hard validation gaps still are.",
        "",
        "## Design Rules",
        "",
    ]
    lines.extend(f"- {item}" for item in manifest.get("selection_criteria", []))
    lines.extend(
        [
            "",
            "## Coverage Mix",
            "",
            f"- Goldset version: `{manifest['goldset_version']}`",
            f"- Case count: `{len(cases)}`",
        ]
    )
    for coverage_status, count in sorted(coverage_counts.items()):
        lines.append(f"- `{coverage_status}`: `{count}`")
    lines.extend([""])
    lines.extend(_goldset_matrix_lines())
    lines.extend(["", "## Case Notes", ""])
    for case in cases:
        lines.append(f"- `{case['id']}`: {case['why_it_matters']}")
        lines.append(f"  showcase: {case['showcase_story']}")
        if case.get("recognizable_examples"):
            examples = ", ".join(f"`{item}`" for item in case["recognizable_examples"])
            lines.append(f"  recognizable examples: {examples}")
        if case.get("external_sources"):
            sources = ", ".join(
                f"`{item['source_id']}` ({item['locator']})" for item in case["external_sources"]
            )
            lines.append(f"  sources: {sources}")
        if case.get("evidence_gaps"):
            lines.append("  evidence gaps:")
            for gap in case["evidence_gaps"]:
                lines.append(f"  - {gap}")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `benchmark_regressed_showcase` means the case is tied to one or more executable",
            "  benchmark fixtures in this repo and also linked to recognizable external sources.",
            "- `integration_showcase` means the workflow is useful and source-backed, but the",
            "  exact case is not yet governed by its own executable reference fixture.",
            "- `challenge_case` means the case is strategically important and source-backed,",
            "  but still highlights a meaningful validation or determinant-pack gap.",
        ]
    )
    return "\n".join(lines)


def verification_summary_guide() -> str:
    report = build_verification_summary_report(DefaultsRegistry.load())
    lines = [
        "# Verification Summary",
        "",
        "This resource consolidates the release, benchmark, validation, and trust-surface",
        "checks that reviewers otherwise have to assemble from multiple machine-readable",
        "resources.",
        "",
        "## Status",
        "",
        f"- Verification status: `{report.status}`",
        f"- Server: `{report.server_name}` `{report.server_version}`",
        f"- Release version: `{report.release_version}`",
        f"- Defaults version: `{report.defaults_version}`",
        f"- Release readiness: `{report.release_readiness_status}`",
        f"- Security/provenance review: `{report.security_review_status}`",
        "",
        "## Public Surface",
        "",
        f"- Tools: `{report.public_surface.tool_count}`",
        f"- Resources: `{report.public_surface.resource_count}`",
        f"- Prompts: `{report.public_surface.prompt_count}`",
        f"- Transports: {', '.join(f'`{item}`' for item in report.public_surface.transports)}",
        "",
        "## Trust Counts",
        "",
        f"- Validation domains: `{report.validation_domain_count}`",
        f"- Benchmark cases: `{report.benchmark_case_count}`",
        f"- External datasets: `{report.external_dataset_count}`",
        f"- Reference bands: `{report.reference_band_count}`",
        f"- Time-series packs: `{report.time_series_pack_count}`",
        f"- Goldset cases: `{report.goldset_case_count}`",
    ]
    if report.unmapped_goldset_case_ids:
        lines.append(
            "- Unmapped goldset cases: "
            + ", ".join(f"`{item}`" for item in report.unmapped_goldset_case_ids)
        )
    lines.extend(["", "## Checks", ""])
    for check in report.checks:
        lines.append(f"- `{check.check_id}` [{check.status.upper()}] {check.title}")
        lines.append(f"  evidence: {check.evidence}")
        if check.related_resources:
            lines.append(
                "  resources: "
                + ", ".join(f"`{item}`" for item in check.related_resources)
            )
        if check.recommendation:
            lines.append(f"  next step: {check.recommendation}")
    lines.extend(["", "## Validation Commands", ""])
    lines.extend(f"- `{command}`" for command in report.validation_commands)
    lines.extend(["", "## Notes", ""])
    lines.extend(f"- {item}" for item in report.notes)
    return "\n".join(lines)


def troubleshooting_guide() -> str:
    return """# Troubleshooting

## Common Failures

- `comparison_chemical_mismatch`: the compared scenarios do not share the same `chemical_id`.
- `pbpk_body_weight_missing`: the scenario does not resolve `body_weight_kg`.
- `pbpk_inhalation_duration_missing`: inhalation PBPK export needs explicit event duration.
- `aggregate_internal_equivalent_bioavailability_missing`: internal-equivalent aggregation needs
  route bioavailability fractions for each represented route.
- `pbpk_unit_unsupported`: PBPK handoff accepts only canonical external dose units.
- `aggregate_duplicate_component`: aggregate inputs reused the same component scenario.
- `pbpk_transient_profile_duration_missing`: transient inhalation PBPK export needs explicit event
  duration.
- `pbpk_transient_profile_route_metrics_missing`: the source inhalation scenario did not expose
  start and end air concentrations for transient export.

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
        "# Direct-Use Exposure MCP v0.1.0",
        "",
        "Direct-Use Exposure MCP `v0.1.0` is the first public deterministic external-dose "
        "release candidate for the ToxMCP suite.",
        "",
        "## Included In This Release",
        "",
        "- Dermal, direct-use/incidental oral, and inhalation screening scenario construction",
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
