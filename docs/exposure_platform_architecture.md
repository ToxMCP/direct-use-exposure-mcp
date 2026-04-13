# Exposure Platform Architecture

Exposure modeling is broader than consumer product use. This project should grow as a
small set of cooperating MCPs with explicit boundaries rather than one server that tries to
wrap every exposure tool directly.

## Design Rule

- Build around shared scenario contracts and harmonized outputs.
- Do not make desktop tools or region-specific calculators the core abstraction.
- Keep PBPK handoff stable even when upstream exposure engines differ.

## Recommended MCP Boundaries

### Direct-Use Exposure MCP

Owns human external-dose construction for direct-use and near-field scenarios.

- Consumer product-use scenarios
- Near-field inhalation and indoor aerosol screening
- Dermal plus direct-use/incidental oral external-dose construction
- Worker exposure routing when the inputs still look like task/use scenarios
- Evidence reconciliation across CompTox, SCCS, SCCS opinions, CosIng, ConsExpo,
  nanomaterial guidance, microplastics regulatory records, dossiers, and user uploads
- PBPK-ready external-dose handoff objects

This is the current repo and should remain the deterministic external-dose backbone.

### Fate MCP

Owns environmental release, multimedia fate, and compartment concentrations.

- Emissions to air, water, soil, sediment
- Multimedia fate and transfer
- Long-term environmental concentration surfaces
- Downstream concentration outputs for human-exposure scenarios

Candidate tool families:

- SimpleBox
- EUSES
- ChemFate-style environmental fate engines

This should be a sibling MCP, not an internal subsystem of Direct-Use Exposure MCP.

### Dietary MCP

Owns food-residue and diet-intake workflows.

- Commodity concentration inputs
- Food-consumption mappings
- Population-specific dietary intake outputs
- Oral exposure distributions or bounded intake summaries

Candidate tool families:

- EFSA PRIMo concepts and templates
- EPA DEEM-aligned workflows

This should also be a sibling MCP because dietary models have different input taxonomies,
different validation regimes, and different regulatory semantics than product-use exposure.

### Worker Exposure Mode or Worker MCP

Start as a bounded domain inside Direct-Use Exposure MCP.

- Tier 1 worker screening
- Tier 2 task refinement
- Shared task/use abstractions with consumer exposure where possible

Candidate tool families:

- ECETOC TRA for Tier 1 screening
- ART for higher-tier task refinement
- Stoffenmanager where licensing and access permit

Split this into a dedicated Worker MCP only if licensing, validation, or workflow differences
make the shared abstractions stop paying off.

## Shared Cross-MCP Contracts

Every MCP should exchange typed objects instead of model-specific blobs.

The shared suite contracts are now published from this repo as governed schemas so sibling MCPs
can build against them before Fate MCP and Dietary MCP are fully implemented.

- `chemical_identity`
  DTXSID, CASRN, preferred name, synonyms, source provenance
- `product_use_evidence_record`
  Existing reviewed evidence contract for use categories, subtype, region, physchem context,
  and particle-aware material context
- `exposure_scenario_definition`
  Product/use, population, route, timing, frequency, environment, and evidence context
- `environmental_release_scenario`
  Source term, media, release duration, and release fractions
- `concentration_surface`
  Medium, location/context, duration, and concentration units
- `route_dose_estimate`
  External dose, absorbed dose when supported, assumptions, provenance, and uncertainty
- `pbpk_external_import_bundle`
  Stable handoff object for PBPK MCP

## Routing Model

Route by domain, not by brand name.

- Consumer spray, cosmetic, cleaner, or particle-aware cosmetic task -> Direct-Use Exposure MCP
  direct-use engine or SCCS/SCCS-opinion/ConsExpo-aligned pack
- Direct-use oral or incidental oral question -> Direct-Use Exposure MCP
- Medicinal TCM regimen, topical herbal product, or product-centric supplement regimen ->
  Direct-Use Exposure MCP
- Worker task with limited data -> Direct-Use Exposure MCP worker router plus current screening/Tier 1 path
- Worker task needing higher-tier refinement -> ART/Stoffenmanager adapter path
- Indoor air or aerosol room problem -> Direct-Use Exposure MCP indoor engine now; CONTAM/IAQX adapter later
- Environmental release or chronic multimedia question -> Fate MCP
- Food-residue, food-mediated herbal intake, or nutrition-style supplement intake question ->
  Dietary MCP

## Integration Principles

- Tool adapters should translate into shared contracts, not leak tool-native schemas.
- Region-specific evidence should remain additive and reviewable.
- Defaults must stay versioned, attributable, and easy to override.
- Internal dose is downstream of exposure; PBPK remains a separate MCP boundary.
- Probabilistic mode should reuse deterministic kernels rather than replace them.

## Build Order

### Phase 1

Strengthen the current Direct-Use Exposure MCP.

- Consumer direct-use coverage
- Indoor aerosol and subtype-aware inhalation
- Evidence reconciliation across CompTox, SCCS, SCCS opinions, CosIng, ConsExpo,
  nanomaterial/microplastics records, and uploaded dossiers
- Stable PBPK export boundary

### Phase 2

Expand human direct-use scope before adding new sibling MCPs.

- Mature the current worker router and Tier 1 worker path
- Add a structured worker Tier 2 bridge export and ART-side ingest boundary before wiring a
  real occupational solver
- Worker Tier 2 hooks
- Better dermal absorbed-dose hooks
- Stronger inhalation/indoor air refinement

### Phase 3

Add Fate MCP.

- Environmental release scenarios
- Multimedia concentration outputs
- Concentration surfaces that Direct-Use Exposure MCP can consume

### Phase 4

Add Dietary MCP.

- Commodity and consumption abstractions
- Population-specific oral intake outputs
- PBPK-ready oral dose handoff

### Phase 5

Add probabilistic orchestration over the shared contracts.

- Distribution-aware scenario packages
- Population variability
- Cross-route uncertainty propagation

## Non-Goals

- Do not merge PBPK into Direct-Use Exposure MCP.
- Do not claim risk conclusions from external-dose outputs.
- Do not make the first version depend on heavyweight desktop models being callable in real time.

## Immediate Recommendation

For this repository:

1. Keep building Direct-Use Exposure MCP as the direct-use and near-field engine.
2. Keep worker routing in this MCP and mature it before splitting worker exposure into a sibling service.
3. Treat environmental fate and dietary as separate MCPs with shared contracts.
4. Keep all regional tools behind evidence packs and model-routing logic rather than exposing
   them as unrelated one-off tools.
