# Capability Maturity Matrix

This matrix is the short-form answer to "how mature is each part of the released
`0.1.0` surface?"

Direct-Use Exposure MCP is no longer only a small deterministic scenario builder.
It is a governed exposure platform surface with a narrow core engine and several
bounded adjacent layers:

- core deterministic external-dose construction
- evidence normalization and reconciliation
- worker routing, bounded execution, and external exchange
- validation, benchmark, and release-governance publication

Use this document together with:

- [README](../README.md)
- [Exposure Platform Architecture](./exposure_platform_architecture.md)
- [Release Notes v0.1.0](./releases/v0.1.0.md)
- [ADR 0004: Repository Slug Decision](./adr/0004-repository-slug.md)

## Maturity Labels

| Label | Meaning |
| --- | --- |
| `benchmark-regressed` | Governed deterministic behavior with executable benchmark cases and release-gated regression tests. |
| `curated` | Uses reviewed defaults or packaged determinants with explicit applicability and provenance. |
| `external-normalized` | Accepts or reconciles external evidence or external solver artifacts into governed internal contracts. |
| `bounded surrogate` | Deliberately simplified execution path with explicit limitations; useful for screening, not a native high-tier solver. |
| `heuristic screening` | Screening-only behavior that still depends on heuristic defaults, even though those heuristics are surfaced and flagged. |

## Matrix

| Area | What it owns | Current maturity | Main evidence basis | Main caveats |
| --- | --- | --- | --- | --- |
| Core deterministic exposure engine | Dermal, oral, inhalation screening, aggregate summaries, scenario comparison, PBPK-ready export | `benchmark-regressed`, `curated`, `heuristic screening` | Benchmark corpus, defaults registry, executable reference bands | Some branches still depend on heuristic screening defaults, even though inhalation now has bounded saturation/deposition caps plus bounded extrathoracic oral-handoff metrics and worker dermal now has retained-loading, breakthrough-lag, and evaporation-competition bounds. |
| Tier B/Tier C bounded uncertainty | Envelopes, parameter bounds, packaged probability-bounds profiles, scenario packages | `curated`, `heuristic screening` | Packaged archetype/profile registries with explicit manifests | Not a probabilistic population engine; no Monte Carlo claims. |
| Residual-air and Tier 1 NF/FF inhalation | Anchored residual-air reentry, native treated-surface residual-air reentry, Tier 1 screening, packaged Tier 1 profiles | `benchmark-regressed`, `curated`, `heuristic screening` | External reference bands, sparse time-series packs, profile packs | Time-resolved validation is still sparse and product-family selective, native treated-surface reentry is a bounded first-order emission model, and deposition remains a bounded first-order sink rather than full aerosol dynamics. |
| Evidence normalization and workflow | CompTox, SCCS, SCCS opinions, CosIng, ConsExpo, nanomaterial guidance, microplastics regulatory records, user-reviewed evidence, integrated evidence-to-scenario workflow | `external-normalized`, `curated` | Typed evidence records, reconciliation reports, particle-aware material context, provenance rules | This layer normalizes evidence; it does not make final scientific judgments. |
| Worker inhalation routing and execution | Worker routing, Tier 2 bridge, ART-style ingest, bounded execution, ART external exchange | `external-normalized`, `bounded surrogate`, `curated` | Worker determinant templates, external ART package exchange, worker reference bands | Not a native ART solver; external ART results remain imported, not internally solved, and task-intensity physiology is still represented by bounded inhalation-rate factors rather than measured ventilation profiles. |
| Worker dermal execution | Dermal bridge, PPE-aware ingest, absorbed-dose execution | `bounded surrogate`, `curated`, `heuristic screening` | Dermal defaults packs, retained-loading/runoff bounds, barrier-material and physchem modifiers, bounded breakthrough timing, evaporation competition, worker dermal validation anchors | Not certified glove-performance modeling or chemical-specific permeation kinetics. |
| Validation and goldset surface | Validation dossier, coverage report, executable bands, time-series packs, goldset showcase corpus | `benchmark-regressed`, `external-normalized` | Versioned benchmark fixtures, cited external datasets, goldset case curation | Coverage is strong but still selective by domain and product family. |
| Release and provenance governance | Release metadata, readiness, conformance, security/provenance review, contracts/examples/resources | `benchmark-regressed`, `curated` | Release artifact checks, manifest generation, provenance/defaults policy | Strong governance does not by itself replace broader scientific validation. |

## Interpreting The Matrix

Three practical rules matter:

1. `benchmark-regressed` is the strongest current label in this repo. It means the
   behavior is locked to deterministic fixtures and release checks, not that it is a
   universal mechanistic truth.
2. `external-normalized` means the MCP can responsibly ingest or reconcile external
   evidence or solver outputs. It does not mean those external systems are reimplemented
   natively here.
3. `heuristic screening` should be read literally. These branches remain useful, but
   they should stay in screening or triage workflows until stronger curated packs replace
   them.

## Current Direction

The next improvements should favor legibility and evidence depth over surface growth:

- add more external benchmark datasets across recognizable families
- keep replacing unconstrained heuristic behavior with bounded physical caps and sinks before adding wider surface area
- deepen worker dermal kinetics with reviewed material and permeation logic
- keep worker high-tier execution as explicit external exchange until a true solver
  integration is justified
- preserve the clean split between Exposure MCP, Fate MCP, Dietary MCP, and PBPK MCP
