# Suite Integration

Direct-Use Exposure MCP is intended to act as the external-dose engine inside the ToxMCP stack.

See [exposure_platform_architecture.md](./exposure_platform_architecture.md) for the recommended
multi-MCP architecture and phased build order across exposure, fate, dietary, and worker domains.
See [toxmcp_suite_index.md](./toxmcp_suite_index.md) for the one-page public-facing map of the
current ToxMCP service family.

## Boundary

- Direct-Use Exposure MCP owns external dose construction and refinement only.
- Direct-use oral and incidental oral stay inside Direct-Use Exposure MCP; diet-mediated oral
  belongs in a sibling Dietary MCP.
- Traditional Chinese Medicine, herbal medicine, and supplement cases should be routed by
  pathway semantics rather than by cultural label or dosage form alone.
- Keep environmental release and multimedia fate in a sibling Fate MCP once those workflows are
  added; they should feed concentration surfaces into exposure workflows rather than blur the
  boundary inside this server.
- Keep dietary intake workflows in a sibling Dietary MCP once those workflows are added; they use
  different input taxonomies and regulatory semantics than direct-use exposure.
- A future Literature MCP, if introduced, should own source normalization, parameter-candidate
  extraction, applicability tagging, and evidence-pack curation rather than dose math.
- PBPK MCP owns internal exposure, TK simulation, and downstream biological interpretation.
- A future orchestration/reporting layer should own cross-service coordination, evidence handling,
  refinement choice, and final reporting.

## Published shared contracts

Direct-Use Exposure MCP now publishes the suite-facing schema anchors that sibling services should
build against instead of inventing parallel handoff shapes:

- `chemicalIdentity.v1`
- `productUseEvidenceRecord.v1`
- `exposureScenarioDefinition.v1`
- `routeDoseEstimate.v1`
- `environmentalReleaseScenario.v1`
- `concentrationSurface.v1`
- `pbpkExternalImportBundle.v1`

These contracts are published as machine-readable schemas through `schemas://{schema_name}` and are
summarized in `docs://cross-mcp-contract-guide`.

## Service selection

- Consumer product use, direct-use oral, incidental oral, indoor aerosol, residual-air reentry,
  and near-field worker screening -> Direct-Use Exposure MCP
- Medicinal TCM regimens, topical herbal products, and product-centric supplement dosing ->
  Direct-Use Exposure MCP
- Environmental release and multimedia concentration questions -> Fate MCP
- Food-residue, food-mediated herbal intake, and dietary oral intake questions -> Dietary MCP
- Internal dose and TK simulation -> PBPK MCP
- Cross-service orchestration and final reporting -> planned orchestration/reporting layer

## Environmental-media oral seam

- Environmental-media oral intake from water or soil is intentionally not routed into
  Direct-Use Exposure MCP by default.
- That seam should start from Fate MCP `concentrationSurface.v1` outputs and move into an explicit
  concentration-to-intake consumer rather than silently reusing direct-use or dietary semantics.
- The first bounded implementation now exists as the checked-in
  `Fate surface_water -> Exposure -> WoE` and
  `Fate surface_water -> Exposure -> IVIVE -> WoE` round-trip fixtures.
- A second bounded implementation now also exists as the checked-in
  `Fate agricultural_soil -> Exposure -> WoE` and
  `Fate agricultural_soil -> Exposure -> IVIVE -> WoE` round-trip fixtures.
- That bridge is intentionally narrow: it uses transparent drinking-water screening assumptions
  and preserves `environmental_media` oral context, rather than claiming a full dietary or
  individualized drinking-water model.
- The soil bridge is intentionally just as narrow: it resolves only the soil-contact branch with
  explicit soil-ingestion screening assumptions and does not claim crop-uptake or food-residue
  semantics.
- It should only enter Dietary MCP when the workflow becomes food-mediated residue plus
  consumption rather than generic media ingestion.

## Checked-in cross-suite fixtures

- `tests/fixtures/cross_suite/woe_ngra/direct_use_exposure_handoff.v1.1.0.json`
  freezes the direct `Direct-Use Exposure -> WoE` oral-context lane.
- `tests/fixtures/cross_suite/woe_ngra/fate_inhalation_exposure_handoff.v1.1.0.json`
  freezes the explicit `Fate ambient_air -> Exposure -> WoE` concentration-to-dose lane.
- The ambient-air bridge proves this repo can act as a bounded concentration-to-dose consumer
  without pretending Fate concentration surfaces are already PBPK-ready or product-use scenarios.
- The checked-in bridge preserves:
  - `pathwaySemantics=concentration_to_dose`
  - upstream `ConcentrationSurface` and `EnvironmentalReleaseScenario` refs
  - a typed `RouteDoseEstimate` handoff
  - explicit screening assumptions for inhalation rate, duration, and body weight
- `tests/fixtures/cross_suite/woe_ngra/fate_water_oral_exposure_handoff.v1.1.0.json`
  freezes the explicit `Fate surface_water -> Exposure -> WoE` concentration-to-intake lane.
- That surface-water bridge proves this repo can act as a bounded concentration-to-intake
  consumer without collapsing environmental-media oral context into `food_mediated` dietary
  intake or direct-use oral semantics.
- The checked-in surface-water bridge preserves:
  - `pathwaySemantics=concentration_to_intake`
  - `oralExposureContext=environmental_media`
  - upstream `ConcentrationSurface` and `EnvironmentalReleaseScenario` refs
  - a typed `RouteDoseEstimate` handoff
  - explicit screening assumptions for drinking-water intake and body weight
- `tests/fixtures/cross_suite/woe_ngra/fate_soil_oral_exposure_handoff.v1.1.0.json`
  freezes the explicit `Fate agricultural_soil -> Exposure -> WoE` concentration-to-intake lane.
- That soil bridge proves this repo can resolve the soil-contact branch of the Fate route hint
  into a bounded environmental oral screening dose without collapsing the case into dietary or
  direct-use semantics.
- The checked-in soil-contact bridge preserves:
  - `pathwaySemantics=concentration_to_intake`
  - `oralExposureContext=environmental_media`
  - upstream `ConcentrationSurface` and `EnvironmentalReleaseScenario` refs
  - a typed `RouteDoseEstimate` handoff
  - explicit screening assumptions for soil ingestion and body weight
  - an explicit unresolved boundary for crop uptake / food-mediated intake

## Herbal, TCM, and supplement split

- TCM pills, decoctions, tinctures, and therapeutic powders stay in Direct-Use Exposure MCP
  when the workflow is about product-centric or prescribed direct-use dosing.
- Topical balms, liniments, oils, patches, or inhaled herbal preparations stay in Direct-Use
  Exposure MCP.
- Herbal teas, nutrition-style supplement intake, and other food-mediated herbal consumption
  belong in Dietary MCP.
- Environmental-media oral intake from contaminated water or soil is not a Direct-Use request
  and is not Dietary by default; it should start from Fate MCP concentration outputs and move
  through an explicit concentration-to-intake consumer when the workflow needs a bounded oral
  screening dose. The checked-in soil-contact bridge only resolves incidental soil-contact style
  intake; crop uptake remains a later seam.

See [herbal_medicinal_routing.md](./herbal_medicinal_routing.md) for the detailed routing note.

## Literature MCP (future/optional)

- Direct-Use Exposure MCP should consume only reviewed, machine-readable evidence packs from a
  Literature MCP, not raw extraction candidates.
- Literature MCP should remain optional until the suite needs shared evidence registries or
  repeatable cross-repo review workflows.
- See [literature_mcp_requirements.md](./literature_mcp_requirements.md) for the proposed tool,
  resource, and contract surface.

## CompTox

- Use CompTox identity and supporting metadata to enrich requests when available.
- Keep enrichment additive and provenance-rich rather than making it mandatory.
- Preserve upstream identifiers in request metadata or evidence envelopes.
- Treat CompTox as one optional evidence source, not the only product-use authority.
- For regional or regulatory-context differences such as EU pesticide use patterns, run the
  generic product-use evidence fit workflow before auto-applying category or use-context updates.
- When multiple sources are available, use the product-use reconciliation workflow to rank the
  candidates, surface conflicts, and build a merged request preview with field-level provenance.
- Prefer generic `productUseEvidenceRecord` payloads when the upstream source is a dossier,
  reviewed literature pack, or user-supplied evidence rather than EPA CompTox.

## ConsExpo

- Treat RIVM ConsExpo as a first-class EU consumer product-use source.
- Use the dedicated ConsExpo mapping workflow to translate fact-sheet families into the generic
  `productUseEvidenceRecord` contract before fit, apply, or reconciliation.
- Expect ConsExpo to be especially useful for EU consumer families such as cosmetics,
  cleaning products, disinfecting products, DIY/paint contexts, and pest control products.
- Preserve the underlying fact-sheet identifier, version, and locator in source metadata so
  downstream review can distinguish current and legacy ConsExpo packs.

## SCCS

- Treat SCCS as the primary EU cosmetics evidence and reviewed use-profile source.
- Use the dedicated SCCS mapping workflow to translate Notes of Guidance or opinion-backed
  cosmetic product types into the generic `productUseEvidenceRecord` contract before fit,
  apply, or reconciliation.
- Prefer SCCS over CompTox or generic dossier evidence when the question is specifically about
  EU cosmetic use assumptions such as amount, frequency, leave-on versus rinse-off context,
  or exposed body-surface context.
- Use ConsExpo as a supporting mechanistic consumer-model layer for cosmetics when the workflow
  needs explicit consumer scenario structure in addition to SCCS use-pattern guidance.
- Preserve the underlying guidance identifier, version, locator, and table references in
  source metadata so downstream review can distinguish Notes of Guidance revisions and
  ingredient-specific SCCS opinions.

## SCCS opinions and CosIng

- Use SCCS opinions as the reviewed ingredient-specific cosmetics lane when the workflow needs
  opinion-bound product types, route relevance, nanomaterial context, or other ingredient-level
  constraints in addition to Notes of Guidance defaults.
- Use CosIng as a supporting identity and function source for INCI name, ingredient function,
  Annex references, and nanomaterial flag context. Do not treat CosIng as a quantitative
  use-profile source.
- Preserve opinion IDs, CosIng locators, and any particle-aware material context so downstream
  reviewers can distinguish regulatory use-pattern guidance from identity/function metadata.

## Nanomaterials and microparticles

- Treat EU cosmetic nanomaterials as a first-class direct-use evidence lane, primarily backed by
  SCCS nano guidance, SCCS opinions, CPNP Article 16 context, and the Commission nanomaterials
  catalogue context.
- Treat synthetic polymer microparticles as a separate evidence lane with ECHA restriction and
  reporting context, not as generic cosmetics defaults.
- Treat non-plastic micro/nanoparticles such as TiO2, ZnO, silica, and pigment particles as
  particle-aware material contexts that can inform route relevance and direct-use assumptions
  without expanding this MCP into fate or toxicology interpretation.
- Preserve `particleMaterialContext.v1` when reconciling reviewed evidence so particle class,
  nano status, size-domain, composition family, and regulatory flags survive handoff into the
  built request.

## Pre-release Downstream Evidence Layer

- Exposure outputs can still be wrapped into deterministic evidence envelopes for lightweight
  downstream orchestration.
- The downstream evidence/refinement export surface remains implemented in this repo, but it is
  intentionally treated as pre-release until the downstream consumer ships.
- Use those bundles only for controlled integration work; they are not part of the public release
  narrative yet.

## PBPK

- Export only dosing semantics, route, timing, duration, and population context.
- The MCP now exports an exact PBPK MCP `ingest_external_pbpk_bundle` request payload through
  `toolCall.arguments`, with additive exposure-side metadata kept separately for downstream
  orchestration layers.
- `ready_for_external_pbpk_import=true` means the upstream bundle is mechanically ready to send
  to PBPK MCP. It does not mean PBPK outputs, qualification, or internal-dose estimates already
  exist.
