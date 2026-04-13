# Herbal, TCM, and Supplement Routing

This guide defines where Traditional Chinese Medicine, herbal medicine, and supplement
cases belong in the ToxMCP exposure stack.

## Core Rule

Route by **pathway semantics and intended use**, not by cultural label or dosage form alone.

## Direct-Use Exposure MCP

These cases belong in Direct-Use Exposure MCP:

- medicinal oral regimens such as TCM decoctions, pills, tinctures, or therapeutic powders
- topical herbal or TCM balms, liniments, oils, and patches
- inhaled herbal or medicinal vapors when the workflow is still a direct-use near-field case
- product-centric supplement dosing only when the workflow is explicitly about a labeled
  consumer regimen rather than dietary intake, including official-label capsule or tablet
  regimens

Recommended request semantics:

- `productUseProfile.intendedUseFamily=medicinal`
- `productUseProfile.oralExposureContext=direct_use_medicinal` for medicinal oral regimens
- `productUseProfile.intendedUseFamily=supplement` plus
  `productUseProfile.oralExposureContext=direct_use_supplement` when a supplement case is
  intentionally being treated as a direct-use regimen

## Dietary MCP

These cases belong in Dietary MCP:

- food-mediated herbal intake, for example herbal teas or botanicals consumed as part of an
  ordinary diet
- nutrition-style supplement intake when the workflow is dietary-consumption assessment rather
  than product-use dosing
- food-residue or commodity-residue workflows involving herbs, botanicals, or related foods

These cases should not be sent as `exposureScenarioRequest.v1` payloads in Direct-Use Exposure
MCP.

## Fate-Oriented Seam

Environmental-media oral intake from contaminated water or soil is not a Direct-Use request and
is not Dietary by default. Start those workflows from Fate MCP `concentrationSurface.v1`
outputs and move into a future concentration-to-intake consumer.

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
