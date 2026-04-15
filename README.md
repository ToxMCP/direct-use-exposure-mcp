# Direct-Use Exposure MCP

[![CI](https://github.com/ToxMCP/direct-use-exposure-mcp/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ToxMCP/direct-use-exposure-mcp/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](./LICENSE)
[![Release](https://img.shields.io/github/v/release/ToxMCP/direct-use-exposure-mcp?sort=semver)](https://github.com/ToxMCP/direct-use-exposure-mcp/releases)
[![Status](https://img.shields.io/badge/Status-Ready%20with%20Known%20Limitations-2E8B57)](#release-verification)
[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)

> Part of **ToxMCP** Suite → https://github.com/ToxMCP/toxmcp

**Public MCP server for deterministic direct-use and near-field external exposure construction in exposure-led NGRA workflows.**
It turns product-use assumptions into auditable dermal, direct-use/incidental oral,
inhalation, and aggregate external-dose scenarios, then exports structured evidence
objects and PBPK-ready handoff payloads without taking over PBPK execution, WoE synthesis,
BER, PoD derivation, or final risk decisions.

## Architecture

```mermaid
flowchart LR
    subgraph Clients["Clients and Orchestrators"]
        Codex["Codex CLI / Desktop"]
        Scripts["Scripts / notebooks"]
        Other["Other MCP-aware agents"]
    end

    subgraph MCP["FastMCP Service"]
        Server["Tool and resource surface"]
        Contracts["Schemas, examples,\ncontract manifest"]
        Prompts["Refinement and\nhandoff prompts"]
    end

    subgraph Engine["Scenario Engine"]
        Runtime["Deterministic runtime"]
        Screening["Dermal / direct-use oral screening plugin"]
        Inhalation["Inhalation screening plugin"]
        Aggregate["Aggregate/co-use summary"]
    end

    subgraph Evidence["Scientific Control Layer"]
        Defaults["Versioned defaults packs"]
        Provenance["Assumption ledger,\nprovenance, quality flags"]
        Review["Release readiness,\nsecurity, provenance review"]
    end

    subgraph Downstream["Suite Handoffs"]
        PBPK["PBPK MCP import bundle"]
        EvidenceBundle["Evidence export bundle"]
        Refinement["Refinement export bundle"]
    end

    Clients --> Server
    Server --> Contracts
    Server --> Prompts
    Server --> Runtime
    Runtime --> Screening
    Runtime --> Inhalation
    Runtime --> Aggregate
    Runtime --> Defaults
    Runtime --> Provenance
    Server --> Review
    Server --> PBPK
    Server --> EvidenceBundle
    Server --> Refinement
```

The core engine is intentionally narrow, even though the released MCP also publishes
bounded worker, exchange, and validation surfaces:

- `Direct-Use Exposure MCP` owns external-dose construction only.
- Current suite interoperability is with `CompTox MCP`, `ADMETlab MCP`, `AOP MCP`,
  `O-QT MCP`, and `PBPK MCP`.
- `PBPK MCP` owns kinetic translation and internal-dose interpretation.
- Defaults, assumptions, provenance, and limitations are first-class outputs, not hidden internals.
- Dietary and fate seams are still explicit: medicinal or product-centric oral regimens stay
  here, while food-mediated intake and multimedia release/concentration workflows remain
  separate future module boundaries.

For a one-page maturity framing of the full released surface, see
[docs/capability_maturity_matrix.md](./docs/capability_maturity_matrix.md).
For a suite-level map of sibling services and shared handoff contracts, see
[docs/toxmcp_suite_index.md](./docs/toxmcp_suite_index.md).

## ToxMCP suite fit

This repo is the exposure-construction module inside the broader
[ToxMCP Suite](https://github.com/ToxMCP/toxmcp). The current public module map is:

| Module | Role in the suite | Relationship to this repo |
| --- | --- | --- |
| `Direct-Use Exposure MCP` | Direct-use and near-field external-dose construction | This repo |
| `CompTox MCP` | Identity, hazard, and EPA CompTox-backed enrichment | Upstream evidence/context source |
| `ADMETlab MCP` | Rapid ADMET prediction utilities | Adjacent screening module |
| `AOP MCP` | Mechanistic pathway and AOP workflows | Adjacent mechanistic module |
| `O-QT MCP` | OECD QSAR Toolbox workflows and reporting | Adjacent modeling module |
| `PBPK MCP` | Internal-dose and TK simulation | Downstream handoff target |

Two additional seams are already documented here but are not current public modules in the
umbrella repo:

- `Fate MCP`: environmental release, multimedia transfer, and concentration surfaces
- `Dietary MCP`: food-mediated intake, commodity residue, and dietary oral workflows

That distinction matters for the README and contract story: this MCP should read as one
module in a growing suite, not as the whole ToxMCP platform.

## What's in v0.1.0

- Deterministic dermal plus direct-use/incidental oral screening scenario construction
- Deterministic inhalation screening with room-volume, ventilation, saturation-cap, and deposition semantics
- Tier A uncertainty registers, deterministic sensitivity ranking, and dependency metadata
- Tier B deterministic scenario envelopes, archetype-library sets, and bounded parameter propagation
- Tier C single-driver probability bounds plus coupled scenario-package probability profiles without Monte Carlo overclaiming
- Machine-actionable Tier 1 inhalation upgrade advisories plus packaged airflow, particle, and product-family screening profiles
- Curated RIVM-backed dermal contact defaults plus governed spray airborne-fraction defaults for personal-care and household-cleaner contexts
- Evidence reconciliation across CompTox, SCCS, SCCS opinions, CosIng, ConsExpo, nano/micro guidance, and reviewed user-supplied product-use records
- Particle-aware evidence lanes for EU cosmetic nanomaterials, synthetic polymer microparticles, and non-plastic micro/nanoparticles
- Integrated evidence-to-scenario-to-PBPK workflow execution as one audited MCP response
- External-dose aggregate summaries plus opt-in route-bioavailability-adjusted internal-equivalent screening totals
- Scenario comparison, refinement deltas, evidence export, and refinement-bundle export
- PBPK scenario export plus exact external-import payload packaging, with optional transient inhalation concentration profiles
- Published JSON schemas, examples, contract manifest, shared cross-MCP contracts, and release metadata
- Release-readiness, verification, result-status, troubleshooting, provenance, and scientific-boundary resources
- Source-backed herbal/TCM/supplement routing plus governed medicinal oral, supplement, topical spray, and topical patch anchors
- Worker-task routing, Tier 2 bridge/export support, governed ART external exchange, and bounded worker dermal execution
- Validation dossier, validation coverage report, executable reference bands, executable time-series packs, and showcase goldset resources

## Why this project exists

Exposure information is often the weakest structured input in early NGRA orchestration:
there may be CompTox context, product-use hints in prompts, or local refinement notes,
but not a stable, auditable external-dose object that downstream systems can trust.

Direct-Use Exposure MCP gives the suite a dedicated exposure layer that is:

- **deterministic-first** for transparent screening use
- **MCP-native** with typed tools, resources, prompts, schemas, and examples
- **auditable** through assumption records, defaults versioning, provenance, and quality flags
- **bounded** so it complements PBPK and adjacent review/orchestration layers instead of overlapping them

## Capability maturity

The repo now has a broader released surface than the early "small deterministic builder"
story implied. The cleanest way to read it is:

- `core deterministic exposure engine`: benchmark-regressed external-dose construction
- `evidence reconciliation and integrated workflow`: external-normalized orchestration helpers
- `worker inhalation and dermal`: bounded extension layers with explicit solver limits
- `validation and release resources`: first-class trust and governance surface

The detailed maturity matrix is in
[docs/capability_maturity_matrix.md](./docs/capability_maturity_matrix.md).

## Feature snapshot

| Capability | Description |
| --- | --- |
| `🧪 Screening scenarios` | Builds route-specific external-dose scenarios for dermal, direct-use/incidental oral, and inhalation screening use cases, with bounded volatility saturation caps, first-order deposition sinks, and explicit extrathoracic swallowed-mass handoff metrics on spray inhalation branches where applicable. |
| `📊 Tier A uncertainty diagnostics` | Publishes qualitative uncertainty registers, one-at-a-time sensitivity ranking, dependency metadata, and validation posture on each scenario. |
| `📦 Tier B deterministic envelopes` | Builds named archetype envelopes with bounded min/median/max outputs and explicit driver attribution without probabilistic overclaiming. |
| `🗂️ Tier B archetype library` | Publishes governed packaged archetype sets, including Tier 1 inhalation request templates where near-field screening is part of the intended context, and instantiates them into deterministic envelopes with set/version provenance. |
| `📏 Tier B parameter bounds` | Propagates explicit lower and upper parameter bounds through a deterministic scenario to produce min/max ranges, monotonicity checks, and bounded uncertainty records. |
| `📈 Tier C probability bounds` | Publishes packaged single-driver probability-bounds profiles with curated driver taxonomy and evaluates their support points without Monte Carlo or joint-distribution claims. |
| `🧷 Tier C scenario packages` | Publishes dependency-aware packaged scenario states with cumulative probability bounds, curated package taxonomy, preserved coupled drivers without Monte Carlo claims, and propagated mechanistic-constraint uncertainty notes when support-point scenarios activate bounded physics caps. |
| `🚨 Tier 1 inhalation screening` | Publishes machine-actionable upgrade advisories for spray inhalation scenarios, preserves the `requestedTier` routing hook on Tier 0 requests, ships a deterministic Tier 1 NF/FF screening tool, exposes packaged airflow, particle, and product-family screening profiles through a machine-readable manifest, warns when caller geometry or regime inputs diverge materially from matched profile anchors, and applies a bounded local-entrainment floor when very weak static interzonal mixing would otherwise become physically implausible. |
| `🌫️ Residual-air reentry inhalation` | Builds post-application room-air screening scenarios in two explicit modes: anchored reentry from a supplied start concentration, or native treated-surface reentry from bounded surface-emission plus room-loss terms, both with a low deposition sink and explicit non-application-plume semantics. |
| `🔬 Evidence reconciliation and workflow` | Normalizes CompTox, SCCS, SCCS opinions, CosIng, ConsExpo, nanomaterial guidance, microplastics regulatory records, and user-reviewed evidence into a shared product-use contract, ranks fit, builds merged requests, and can run an audited evidence-to-scenario-to-PBPK workflow in one response. |
| `🧫 Particle-aware cosmetics and materials context` | Publishes particle material context for EU cosmetic nanomaterials, synthetic polymer microparticles, and non-plastic micro/nanoparticles so route relevance, regulatory flags, and direct-use assumptions stay explicit without drifting into fate or toxicology claims. |
| `🏭 Worker task routing` | Routes worker-tagged tasks to the strongest current MCP path, emits worker-specific scenario guardrails when the shared screening engines are reused, and points higher-tier occupational cases toward future adapter hooks. |
| `🔌 Worker Tier 2 bridge` | Exports a typed worker inhalation handoff package, compatibility checklist, and future adapter tool-call envelope for ART-style Tier 2 refinement without pretending the occupational solver already exists. |
| `🛠️ Worker Tier 2 execution` | Executes a governed control-aware worker inhalation surrogate, supports bounded task-intensity inhalation-rate scaling plus explicit LEV/control-context, capture-zone, hood/enclosure-sensitive capture-distance decay, and LEV-family / hood-face-velocity refinements with bounded measured-profile bands, supports deterministic benchmark regression, and preserves comparability with external ART imports without claiming a native ART solver run. |
| `🔄 Worker ART external exchange` | Exports normalized external ART execution packages and imports reviewed external results or runner artifacts through a bounded, provenance-preserving adapter surface. |
| `🧴 Worker dermal absorbed-dose execution` | Exports and ingests dermal absorbed-dose/PPE handoffs, then executes a bounded dermal kernel with retained-loading/runoff caps, barrier-material and chemistry modifiers, bounded breakthrough-lag timing, duration-aware evaporation competition, and family-, subtype-, carrier-, formulation-, and physchem-aware pressurized-aerosol mass interpretation when only volumetric aerosol defaults are available, while keeping certified glove performance and full permeation modeling explicitly out of scope. |
| `🧮 Aggregate summaries` | Produces additive co-use summaries while preserving route and component transparency. |
| `🧬 PBPK handoff export` | Emits PBPK-ready objects plus an exact external-import package aligned to the upstream PBPK MCP request shape. |
| `📤 Evidence export` | Emits deterministic evidence, claim, and structured handoff primitives for downstream review and orchestration layers. |
| `🔁 Refinement workflow support` | Emits comparison/refinement bundles with explicit `refine_exposure` semantics and workflow hooks. |
| `✅ Validation dossier` | Publishes a typed validation dossier with benchmark domains, cited external validation datasets, heuristic-source families, and open evidence gaps, and threads evidence-readiness, executed validation checks, and gap IDs into every scenario-level `validationSummary`. |
| `📋 Validation coverage report` | Publishes a typed cross-domain trust summary over benchmark cases, external datasets, executable bands, time-series packs, and goldset mappings so validation posture is explicit instead of inferred. |
| `🛡️ Verification summary` | Publishes and executes a consolidated consistency check across release metadata, contract counts, benchmark coverage, validation assets, and published trust resources. |
| `📐 Executable validation bands` | Publishes a typed, versioned manifest for the narrow executable reference bands used by `validationSummary.executedValidationChecks`, so screening acceptance anchors are data-driven rather than hardcoded. |
| `⏱️ Executable time-series packs` | Publishes sparse governed time-series anchors for domains like residual-air reentry and air-space aerosol decay, so time-resolved validation is versioned and machine-readable. |
| `🏅 Goldset showcase corpus` | Publishes a separate, source-backed showcase set for recognizable cases while keeping the deterministic regression fixture stable and auditable. |
| `🧷 Curated dermal contact packs` | Replaces the highest-volume transfer and surface-contact-retention heuristics with RIVM-backed screening defaults for `personal_care` hand application and `household_cleaner` wipe contact while preserving explicit applicability domains and remaining evidence gaps. |
| `🗃️ Defaults curation report` | Publishes a typed branch-level report showing which defaults paths are curated, route-semantic, or still heuristic, so downstream clients can target the strongest scenario branches deliberately. |
| `📚 Contract publication` | Publishes schemas, examples, manifest metadata, docs resources, release metadata, and result-status conventions. |
| `🔗 Shared suite contracts` | Publishes governed cross-MCP schemas for shared chemical identity, scenario definition, route-dose handoff, and future Fate concentration handoffs. |
| `🚧 Scientific guardrails` | Keeps BER, PoD derivation, PBPK execution, and final risk conclusions outside this server while publishing assumption governance and tier semantics on every scenario. |

## Table of contents

1. [Architecture](#architecture)
2. [ToxMCP suite fit](#toxmcp-suite-fit)
3. [What's in v0.1.0](#whats-in-v010)
4. [Why this project exists](#why-this-project-exists)
5. [Capability maturity](#capability-maturity)
6. [Feature snapshot](#feature-snapshot)
7. [Tool catalog](#tool-catalog)
8. [Resource catalog](#resource-catalog)
9. [Quick start](#quick-start)
10. [Release verification](#release-verification)
11. [Repository layout](#repository-layout)
12. [Current limitations](#current-limitations)
13. [Scientific boundaries](#scientific-boundaries)
14. [Contributing](#contributing)
15. [Code of conduct](#code-of-conduct)
16. [License](#license)

## Tool catalog

### Scenario construction

- `exposure_build_screening_exposure_scenario`
- `exposure_build_exposure_envelope`
- `exposure_build_exposure_envelope_from_library`
- `exposure_build_parameter_bounds_summary`
- `exposure_build_probability_bounds_from_profile`
- `exposure_build_probability_bounds_from_scenario_package`
- `exposure_build_inhalation_screening_scenario`
- `exposure_build_inhalation_residual_air_reentry_scenario`
- `exposure_build_inhalation_tier1_screening_scenario`
- `exposure_build_aggregate_exposure_scenario`
- `exposure_compare_exposure_scenarios`

### Evidence fit and enrichment

- `exposure_build_product_use_evidence_from_consexpo`
- `exposure_build_product_use_evidence_from_sccs`
- `exposure_build_product_use_evidence_from_sccs_opinion`
- `exposure_build_product_use_evidence_from_cosing`
- `exposure_build_product_use_evidence_from_nanomaterial`
- `exposure_build_product_use_evidence_from_synthetic_polymer_microparticle`
- `exposure_assess_product_use_evidence_fit`
- `exposure_apply_product_use_evidence`
- `exposure_reconcile_product_use_evidence`
- `exposure_run_integrated_workflow`
- `exposure_route_worker_task`
- `exposure_export_worker_inhalation_tier2_bridge`
- `worker_ingest_inhalation_tier2_task`
- `worker_execute_inhalation_tier2_task`
- `worker_export_inhalation_art_execution_package`
- `worker_import_inhalation_art_execution_result`
- `exposure_export_worker_dermal_absorbed_dose_bridge`
- `worker_ingest_dermal_absorbed_dose_task`
- `worker_execute_dermal_absorbed_dose_task`

### Handoff export

- `exposure_export_pbpk_scenario_input`
- `exposure_export_pbpk_external_import_bundle`
- `exposure_export_toxclaw_evidence_bundle`
- `exposure_export_toxclaw_refinement_bundle`

### Verification and trust

- `exposure_run_verification_checks`

## Resource catalog

### Contracts and examples

- `contracts://manifest`
- `schemas://{schema_name}`
- `examples://{example_name}`
- `defaults://manifest`
- `defaults://curation-report`
- `tier1-inhalation://manifest`
- `archetypes://manifest`
- `probability-bounds://manifest`
- `scenario-probability://manifest`
- `benchmarks://manifest`
- `benchmarks://goldset`
- `validation://manifest`
- `validation://dossier-report`
- `validation://coverage-report`
- `validation://reference-bands`
- `validation://time-series-packs`
- `verification://summary`

### Operator and scientific documentation

- `docs://algorithm-notes`
- `docs://archetype-library-guide`
- `docs://probability-bounds-guide`
- `docs://tier1-inhalation-parameter-guide`
- `docs://inhalation-tier-upgrade-guide`
- `docs://inhalation-residual-air-reentry-guide`
- `docs://defaults-evidence-map`
- `docs://defaults-curation-report`
- `docs://operator-guide`
- `docs://deployment-hardening-guide`
- `docs://provenance-policy`
- `docs://result-status-semantics`
- `docs://uncertainty-framework`
- `docs://validation-framework`
- `docs://validation-dossier`
- `docs://validation-coverage-report`
- `docs://validation-reference-bands`
- `docs://validation-time-series-packs`
- `docs://verification-summary`
- `docs://goldset-benchmark-guide`
- `docs://suite-integration-guide`
- `docs://integrated-exposure-workflow-guide`
- `docs://exposure-platform-architecture`
- `docs://capability-maturity-matrix`
- `docs://repository-slug-decision`
- `docs://cross-mcp-contract-guide`
- `docs://service-selection-guide`
- `docs://worker-routing-guide`
- `docs://worker-tier2-bridge-guide`
- `docs://worker-art-adapter-guide`
- `docs://worker-art-execution-guide`
- `docs://worker-art-external-exchange-guide`
- `docs://worker-dermal-bridge-guide`
- `docs://worker-dermal-adapter-guide`
- `docs://worker-dermal-execution-guide`
- `docs://troubleshooting`

### Release and review artifacts

- `docs://release-notes`
- `docs://conformance-report`
- `docs://release-readiness`
- `docs://release-trust-checklist`
- `docs://security-provenance-review`
- `docs://test-evidence-summary`
- `release://metadata-report`
- `release://readiness-report`
- `release://security-provenance-review-report`

## Prompt catalog

- `exposure_refinement_playbook`
- `exposure_pbpk_handoff_checklist`

## Quick start

```bash
git clone https://github.com/ToxMCP/direct-use-exposure-mcp.git
cd direct-use-exposure-mcp

uv sync --extra dev
uv run generate-exposure-contracts
uv run pytest
uv run exposure-scenario-mcp --transport stdio
```

The public product name is now `Direct-Use Exposure MCP`, while the current GitHub slug,
Python package, import path, CLI, and MCP server IDs remain stable through the `v0.1.x`
line. The current GitHub slug is:

- `ToxMCP/direct-use-exposure-mcp`

See
[docs/adr/0004-repository-slug.md](./docs/adr/0004-repository-slug.md).

Run over Streamable HTTP:

```bash
uv run exposure-scenario-mcp --transport streamable-http --host 127.0.0.1 --port 8001
```

Current published surface from `docs/contracts/contract_manifest.json`:

- `35` tools
- `65` resources
- `2` prompts
- `151` schemas
- `91` examples

Legacy `Exposure_Scenario_MCP_tasks.*` planning artifacts at the repo root are now archived
status notes, not the live implementation backlog.

## Release verification

```bash
uv run ruff check .
uv run pytest
uv build
uv run generate-exposure-contracts
uv run check-exposure-release-artifacts
```

The MCP also publishes a consolidated runtime trust surface through:

- `verification://summary`
- `docs://verification-summary`
- `docs://release-trust-checklist`
- `docs://deployment-hardening-guide`
- `docs://test-evidence-summary`
- `docs://herbal-medicinal-routing-guide`

Current published package version: `0.1.0`

Repository-facing release docs:

- [CITATION.cff](./CITATION.cff)
- [docs/release_trust_checklist.md](./docs/release_trust_checklist.md)
- [docs/deployment_hardening.md](./docs/deployment_hardening.md)
- [docs/test_evidence_summary.md](./docs/test_evidence_summary.md)

## Repository layout

- `src/exposure_scenario_mcp/` - server, models, runtime, defaults, provenance, integrations
- `defaults/` - versioned defaults packs
- `schemas/` - generated schemas and examples
- `docs/contracts/` - published schemas and contract manifest mirrors
- `docs/releases/` - release notes and release metadata
- `docs/` - operator, troubleshooting, provenance, readiness, capability maturity, suite integration, architecture, and adjacent-service design notes
- `evals/` - read-only evaluation bundle
- `tests/` - runtime, contract, integration, and release-artifact tests

## Current limitations

The current `v0.1.0` release is intentionally honest about what it does not do:

- It is deterministic-first and does not ship a probabilistic population engine.
- It does not execute PBPK, estimate internal dose, derive BER or PoD values, or make final risk decisions.
- Some screening factors still resolve from heuristic defaults packs and should be treated as screening-level assumptions.
- Inhalation branches now apply bounded volatility saturation caps and deposition sinks, but they are still screening-scale first-order physics rather than full aerosol dynamics.
- Worker inhalation Tier 2 execution is a governed surrogate plus external ART exchange boundary, not a native ART solver.
- Worker dermal execution is bounded, chemistry/material aware, finite-loading capped, and now includes bounded breakthrough-lag and evaporation-competition logic, but it is not a full glove-permeation or chemical-specific dermal kinetics engine.
- Remote `streamable-http` deployment still requires external authentication and origin hardening.
- PBPK request alignment should be re-validated whenever PBPK MCP changes its published contract version.

## Scientific boundaries

Direct-Use Exposure MCP is the **external-dose construction** layer in the suite.
That means:

- it may infer and default screening inputs
- it may compare and aggregate scenarios
- it may export PBPK-facing and downstream-review handoff objects
- it keeps direct-use and incidental oral inside this repo while leaving diet-mediated oral
  to a sibling Dietary MCP
- it now supports explicit oral routing tags for medicinal, supplement, incidental, and
  non-Direct-Use dietary semantics
- it now supports explicit oral-solid regimen semantics for counted tablets, capsules,
  pills, and similar discrete-dose direct-use products
- it can publish shared suite contracts for future Fate and Dietary handoffs without taking
  ownership of those runtimes

It does **not**:

- claim toxicokinetic authority
- own environmental release or multimedia fate math
- own diet-mediated oral intake workflows
- replace mechanistic or WoE interpretation
- produce final risk judgments
- silently elevate heuristic screening assumptions into decision-ready conclusions

If the suite later adds a dedicated evidence-curation service, see
[docs/literature_mcp_requirements.md](./docs/literature_mcp_requirements.md) for the proposed
boundary and contract requirements.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for local setup, quality gates,
contract-generation expectations, and scientific boundary rules for changes.

## Code of conduct

See [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md).

## License

This project is licensed under the [Apache License 2.0](./LICENSE).
