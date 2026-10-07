# Reviewing aggregate exposure and source applicability

The MCP constructs deterministic exposure calculations. Interpret the result
together with its quality flags, limitations, uncertainty register and validation
summary.

## Aggregate boundaries

- Supply one bioavailability fraction per route. Duplicate entries fail with
  `aggregate_duplicate_bioavailability_route`, including identical fractions.
  Product-specific absorption fractions require their own evidenced derivation;
  duplicate route entries cannot represent different products.
- `aggregate_population_mismatch` is an error finding for different population
  groups, regions, cohort tags or resolved body-weight denominators.
- `aggregate_component_population_inconsistent` identifies disagreement between
  the calculation denominator and the population profile.
- `aggregate_population_context_incomplete` means the denominator cannot be
  recovered. Original calculation assumptions take precedence over rewritten
  profile fields.
- These error findings retain arithmetic for inspection. The sum cannot represent
  one compatible population aggregate. Rebuild components on a common basis, or
  keep population-specific results separate.
  The spine projection emits no legitimate downstream-use authorization tokens
  when the aggregate carries error findings; its overclaim diagnostics remain active.
- `aggregate_component_overlap_unresolved` warns when matching declared use and
  population profiles appear under different scenario IDs. Review source/event
  correspondence. The MCP does not automatically deduplicate: identical profiles
  can also describe genuinely independent uses.
- `aggregate_scope_unverified` identifies an accounted-contribution sum whose
  source inventory, material correspondence, period and complete coverage have
  not been verified by this contract.

Keep an accompanying inventory with the source/event identifier, material,
population and region, assessment period and duration, dose basis and endpoint,
source locator, and the relationship to other contributions. Label relationships
as additive, alternative, overlapping or unresolved. Record omitted sources and
their bounds; unknown quantities stay unknown. This worksheet is review metadata,
not a new producer artifact or qualified TTC exposure descriptor.

Alternative manufacturer/use scenarios are not additive. Repeated records and
already-accounted intake should not be counted again. Separate marginal P95s do
not establish a joint aggregate P95. Scenario packages and deterministic
sensitivity calculations are not population probability distributions.

No compatible sum by itself establishes complete aggregate exposure. For oral
food-mediated intake use Dietary; for relevant kinetic refinement use PBPK/IVIVE.
Retain each producer's dose basis and contracts when composing workflows.

## Evidence fit and review state

Matching technical fields do not establish scientific sufficiency.

`provisional` and `unreviewed` product-use records remain technically compatible
when their input fields fit, but return `auto_apply_safe: false` and a review
warning. Strict application raises `product_use_evidence_requires_review`.
Strict reconciliation returns `manual_review`. Exploratory application remains
available and preserves the original review label in provenance.

A caller-supplied `reviewed` label is not an authenticated reviewer approval,
signature or safety decision. Source publication, material/formulation
correspondence, population/use applicability and scientific appraisal must be
examined separately.

Check evidence against the intended product formulation, concentration, stability,
contact conditions, population, use frequency, assessment period and dose basis.
A broad cream/liquid category match cannot establish absorption correspondence.
External skin loading, absorbed systemic dose, skin-sensitisation consumer
exposure level and local inhalation concentration are distinct quantities.

## Primary-source benchmarks

These records are public interpretation/arithmetic references. They do not add
default factors, calibrate the exposure models or establish current legal
adoption. Source hashes, RegLens IDs and printed-page locators are pinned in
`tests/fixtures/regulatory_exposure_review_cases.v1.json`.

| Record | Review lesson |
| --- | --- |
| [Tea tree oil, SCCS/1681/25](https://health.ec.europa.eu/document/download/827f8a57-c6f2-4d6d-9bbd-2ef12384ffbf_en?filename=sccs_o_303.pdf), pp. 3, 32-33, 50; [E77164] | Restricted favourable uses and the submitted sensitisation QRA shortcoming are separate findings. Its four displayed SEDs sum to 0.0144 mg/kg/day; SCCS corrects a printed 0.144 total. Product absorption fractions differ within the dermal route. |
| [Kojic acid, SCCS/1481/12](https://health.ec.europa.eu/document/download/cc3e2773-03b7-4bc8-8666-d2d03c5b6296_en?filename=sccs_o_098.pdf), pp. 13-14; [E104502] | The historical lower absorption result did not establish formulation representativeness. Preserve its area-based units and applicability judgment. |
| [Methyl salicylate, SCCS/1676/25](https://health.ec.europa.eu/document/download/c0d2bb4f-87c2-4fff-978d-1ed3af73de1a_en?filename=sccs_o_298.pdf), pp. 11-13, 21; [E1335] | Children-specific exposure inputs and the explicit fallback need their own provenance. Generic child defaults do not recreate a particular age-band assessment. |
| [Cannabidiol, SCCS/1685/25](https://health.ec.europa.eu/document/download/c7b0b685-a9d4-4ccb-8b90-388f59850c0e_en?filename=sccs_o_307.pdf), p. 29; [E77229] | The discussed single-product CEL did not cover the expected multiple-product sensitisation exposure. Keep endpoint-specific exposure scope. |

Decimal reconstruction from displayed tea tree oil inputs gives 0.014309516
before each row is rounded. Summing the displayed rounded rows gives 0.0144.
Both rounding stages are retained. Neither sum is an aggregate P95, complete
cross-sector exposure, a new Exposure artifact or TTC qualification.

## Reproduction

```sh
uv run pytest tests/test_aggregate_review.py tests/test_asset_provenance.py tests/test_regulatory_exposure_review_cases.py -q
uv run pytest tests/test_population_plausibility.py tests/governance -q
```

The new controls are explicitly artificial. Existing compatible calculation
equations and tool/schema identifiers are retained; new review findings expose
previously implicit limitations. Broader source-ledger or adapter changes need
their own contract review.
