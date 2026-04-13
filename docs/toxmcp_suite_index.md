# ToxMCP Suite Index

This is the shortest public-facing map of the current ToxMCP service family.

Use it when you need to answer three questions quickly:

1. Which MCP owns this scientific question?
2. Which contract should the handoff use?
3. Which services are released now versus planned siblings?

## Current Service Map

| Service | Primary role | Current status |
| --- | --- | --- |
| `Direct-Use Exposure MCP` | Deterministic direct-use and near-field external-dose construction, evidence reconciliation, bounded worker screening, PBPK-ready handoff packaging | Released |
| `PBPK MCP` | Toxicokinetic simulation, internal-dose translation, downstream TK-facing outputs | Sibling service |
| `Bioactivity-PoD MCP` | Bioactivity normalization, PoD/BER interpretation support, curated downstream qualification | Sibling service |
| `ToxClaw` | Cross-service orchestration, evidence handling, refinement policy, reporting | Sibling orchestrator |
| `Fate MCP` | Environmental release, multimedia transfer, concentration surfaces | Planned sibling |
| `Dietary MCP` | Commodity residues, food-consumption mappings, dietary oral intake | Planned sibling |
| `Literature MCP` | Source normalization, extraction review, evidence-pack curation | Optional future sibling |

## Fast Routing Table

- Product-use, direct-use oral, incidental oral, indoor aerosol, residual-air reentry, and
  near-field worker screening -> `Direct-Use Exposure MCP`
- Herbal medicinal products, TCM regimens, and topical herbal products -> `Direct-Use Exposure MCP`
- Environmental source term or multimedia concentration question -> `Fate MCP`
- Dietary oral intake, food-mediated herbal intake, or food-residue question -> `Dietary MCP`
- Internal dose or TK simulation question -> `PBPK MCP`
- Bioactivity or PoD interpretation question -> `Bioactivity-PoD MCP`
- Case assembly, refinement choice, or final NGRA-facing reporting question -> `ToxClaw`

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
