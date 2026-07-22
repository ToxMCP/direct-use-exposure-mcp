# ToxMCP Suite Index

This is the shortest public-facing map of the current ToxMCP service family.

As of `v0.2.0`, `Direct-Use Exposure MCP` is the public ToxMCP module for auditable,
deterministic external-exposure scenario construction. It is the service to reach for when
the workflow needs a reviewable exposure object before TK, WoE, or final risk interpretation.

Use it when you need to answer three questions quickly:

1. Which MCP owns this scientific question?
2. Which contract should the handoff use?
3. Which modules are public now versus still documented as future seams?

## Current Public Modules

| Module | Primary role | Where it sits relative to this repo |
| --- | --- | --- |
| `Direct-Use Exposure MCP` | Deterministic direct-use and near-field external-dose construction, evidence reconciliation, bounded worker screening, PBPK-ready handoff packaging | This repo |
| `CompTox MCP` | Identity, hazard, and exposure context from EPA CompTox | Upstream enrichment/evidence module |
| `ADMETlab MCP` | Rapid ADMET prediction plus utility workflows | Adjacent prediction module |
| `AOP MCP` | Mechanistic pathway workflows and AOP-centered exploration | Adjacent mechanistic module |
| `O-QT MCP` | OECD QSAR Toolbox workflows and reports | Adjacent modeling module |
| `PBPK MCP` | Toxicokinetic simulation, internal-dose translation, downstream TK-facing outputs | Downstream handoff target |
| `Environmental Fate MCP` | Environmental release, multimedia transfer, and concentration surfaces | Released public sibling ([`v0.5.0`](https://github.com/ToxMCP/environmental-fate-mcp/releases/tag/v0.5.0)) |
| `Dietary Exposure MCP` | Food-mediated oral screening, commodity residues, consumption mappings, and PBPK-ready oral dose handoffs | Released public screening sibling ([`v0.1.0`](https://github.com/ToxMCP/dietary-exposure-mcp/releases/tag/v0.1.0)) |

Choose the exposure module by pathway: product-use and near-field scenarios belong here,
food-mediated intake belongs in `Dietary Exposure MCP`, and environmental source-to-concentration
questions belong in `Environmental Fate MCP`.

## Planned Adjacent Services

These adjacent services remain planned rather than current public modules in the umbrella repo:

| Module | Intended role |
| --- | --- |
| `Literature MCP` | Source normalization, extraction review, evidence-pack curation |
| `Orchestration/reporting layer` | Cross-service orchestration, evidence handling, refinement policy, reporting |

## Fast Routing Table

- Product-use, direct-use oral, incidental oral, indoor aerosol, residual-air reentry, and
  near-field worker screening -> `Direct-Use Exposure MCP`
- Cross-jurisdiction screening comparison with explicit assumptions, provenance, and
  fit-for-purpose metadata -> `Direct-Use Exposure MCP`
- Herbal medicinal products, TCM regimens, and topical herbal products -> `Direct-Use Exposure MCP`
- Identity, hazard, or EPA CompTox-backed enrichment question -> `CompTox MCP`
- Rapid ADMET prediction or utility question -> `ADMETlab MCP`
- Mechanistic pathway or AOP question -> `AOP MCP`
- OECD QSAR Toolbox workflow question -> `O-QT MCP`
- Environmental source term or multimedia concentration question -> `Environmental Fate MCP`
- Dietary oral intake, food-mediated herbal intake, or food-residue question -> `Dietary Exposure MCP`
- Internal dose or TK simulation question -> `PBPK MCP`
- Case assembly, refinement choice, or final reporting question -> planned orchestration/reporting layer

## Shared Cross-MCP Contracts

These are the suite-facing handoff shapes currently published from this repo:

- `chemicalIdentity.v1`
- `productUseEvidenceRecord.v1`
- `exposureScenarioDefinition.v1`
- `routeDoseEstimate.v1`
- `environmentalReleaseScenario.v1`
- `concentrationSurface.v1`
- `pbpkExternalImportBundle.v1`

## Read This Repo In Order

1. [README](../README.md)
2. [Capability Maturity Matrix](./capability_maturity_matrix.md)
3. [Suite Integration](./suite_integration.md)
4. [Exposure Platform Architecture](./exposure_platform_architecture.md)
5. [ADR 0004: Repository Slug Decision](./adr/0004-repository-slug.md)

## MCP-Published Companions

- `docs://toxmcp-suite-index`
- `docs://service-selection-guide`
- `docs://herbal-medicinal-routing-guide`
- `docs://cross-mcp-contract-guide`
- `docs://capability-maturity-matrix`
