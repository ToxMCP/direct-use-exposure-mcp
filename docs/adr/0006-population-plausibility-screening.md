# ADR 0006: Population Plausibility Screening Flags Instead Of Failing Closed

- Status: Accepted
- Date: 2026-09-26

## Context

`exposure_build_screening_exposure_scenario` accepted
`population_profile {population_group: "adult", body_weight_kg: 6691.76, region: "EU"}` and
returned an ordinary scenario: `quality_flags: []`, nothing in `validationSummary`, and a
normalized external dose roughly two orders of magnitude too low. `PopulationProfile` only enforced `> 0`, so any
positive value, including unit or decimal-place errors, flowed silently into every
mg/kg-day result and into aggregates, jurisdiction comparisons, and PBPK handoffs built from
it.

Two responses were considered:

- **Fail closed** (raise an `ExposureScenarioError`) above a hard limit.
- **Flag** the value with graded quality flags and keep building.

## Decision

Screen resolved `body_weight_kg`, `exposed_surface_area_cm2`, and
`inhalation_rate_m3_per_hour` against per-population-group bands
(`exposure_scenario_mcp.population_plausibility`, published in
`docs://defaults-evidence-map`), with two tiers:

- outside the **typical band**: `population_<field>_atypical`, severity `warning`;
- outside the **screening review envelope** (for exposed area: above the surface-area review limit):
  `population_<field>_implausible`, severity `error`, plus an `error` limitation (and so an
  uncertainty-register entry), `tier_semantics.assumption_checks_passed = false` with a
  required caveat, a `validationSummary` note, and a notice in the tool-result text.

Adult body weight above 250 kg is in the error tier. Bands are anchored to the shipped
population defaults and the EPA Exposure Factors Handbook 2011 tables behind them; a test
asserts that every shipped default (global and regional) sits inside its typical band, so
defaults can never trip the check. Groups without a registered band are held to a generic
human screening review envelope with no warning tier.

Downstream consumers re-screen the resolved component values rather than trusting component
flags: aggregates re-emit the flags per component and add an `error` limitation
(`aggregate_component_population_implausible`) and register entry; PBPK compatibility
reports and PBPK scenario exports raise `pbpk_population_context_implausible`, which marks
the PBPK handoff not ready.

The build is **not** blocked.

## Rationale

- The repo's governance convention reserves fail-closed errors for structurally invalid or
  non-computable input (non-positive denominators, unsupported units or groups) and uses
  quality flags plus limitations for computable-but-questionable input (heuristic defaults,
  inconsistent dosage units, aerosol volume adjustments).
- The bands are screening heuristics. Failing closed on them would make a heuristic
  authoritative and would break legitimate uses that need extreme values: sensitivity sweeps,
  parameter bounds, and the existing numeric-stability contract in
  `tests/test_input_boundaries.py`.
- The failure mode was silence, not computation. An `error` flag that fails
  `assumption_checks_passed`, attaches a limitation and caveat, names itself in the tool-result
  text, and is re-derived by every aggregate and PBPK handoff removes the silence without
  hiding the audit trail that shows what was actually computed.
- PBPK handoffs are where a physiologically impossible body weight would parameterize a
  physiological model, so that is where the result is marked not ready.

## Consequences

- Scenarios built from implausible population inputs remain available for audit, but their
  normalized results are marked non-interpretable wherever they travel.
- Clients that need a hard stop should treat `population_*_implausible`, or
  `assumption_checks_passed = false`, as blocking in their own orchestration layer.
- Changing a band is a code change with a new `POPULATION_PLAUSIBILITY_VERSION`, and the
  anchoring test must keep every shipped default inside its typical band.

## SDK2 adaptation (2026-10-03)

The error-tier boundaries are input-review policy heuristics, not universal
physiological maxima or limits prescribed by EPA. The reference tables contextualize
the existing defaults; the wider review limits are deliberately separate operator
choices. Specialized populations can legitimately fall outside a band. Review
context and units before interpretation. SDK2 structured content and existing client
compatibility are preserved; text-only summaries also name error flags.
