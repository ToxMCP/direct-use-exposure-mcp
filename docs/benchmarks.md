# Benchmark Corpus

The deterministic benchmark corpus for `v0.1.0` is stored in `tests/fixtures/benchmark_cases.json`.
The showcase goldset is stored separately in `tests/fixtures/goldset_cases.json`.

## Purpose

- Lock down core screening and inhalation calculations against hand-worked expectations.
- Confirm the defaults pack version used during the calculation.
- Prevent silent numeric drift during later refactors.
- Keep the goldset separate so externally anchored showcase cases do not destabilize the
  deterministic regression fixture.

## Current Coverage

- Adult dermal leave-on hand cream screening
- Adult dermal leave-on face cream screening aligned to SCCS Notes of Guidance
- Adult inhalation trigger spray screening
- Adult inhalation trigger spray screening linked to a narrow aerosol room-decay half-life anchor
- Adult inhalation volatility stress case proving thermodynamic saturation capping of impossible room-air concentrations
- Adult air-space insecticide aerosol screening linked to a narrow indoor-air validation band
- Adult air-space insecticide aerosol screening linked to a sparse 0.75-hour to 6-hour
  indoor-air decay series
- Adult indoor-surface insecticide residual-air reentry screening linked to a narrow
  chlorpyrifos post-application start-concentration benchmark band
- Adult indoor-surface insecticide residual-air reentry screening linked to a sparse
  chlorpyrifos 4-hour to 24-hour room-air time-series benchmark
- Adult indoor-surface insecticide residual-air reentry native treated-surface screening
  locking the bounded same-room surface-emission branch into the deterministic regression corpus
- Adult indoor-surface insecticide residual-air reentry screening linked to a sparse
  diazinon 24-hour to 48-hour office room-air time-series benchmark
- Adult indoor-surface insecticide residual-air reentry screening linked to a narrow
  diazinon consumer home-use indoor-air anchor through the native treated-surface branch
- Adult inhalation Tier 1 trigger spray near-field/far-field screening
- Adult inhalation Tier 1 trigger spray case where a bounded local entrainment floor prevents unrealistically weak interzonal mixing in a very small near-field compartment
- Adult inhalation Tier 1 coarse-spray settling sensitivity case locking bounded deposition loss into the deterministic regression corpus
- Adult inhalation Tier 1 disinfectant trigger spray screening linked to a narrow
  externally anchored inhaled-dose benchmark
- Child direct-oral liquid screening
- Child medicinal-liquid direct-oral screening linked to a narrow ready-to-use dosing benchmark
- Adult Traditional Chinese Medicine pill screening covering medicinal direct-use oral routing
  semantics
- Adult product-centric botanical supplement capsule screening covering direct-use supplement
  routing semantics
- Adult Traditional Chinese Medicine topical balm screening covering direct-use leave-on dermal
  semantics
- Adult dermal cream volume-to-mass conversion with density override precedence
- Cross-route aggregate summary with contributor fractions and limitation flagging
- Cross-route internal-equivalent aggregate summary using route-specific bioavailability fractions
- Zero-baseline scenario comparison with undefined percentage-delta handling
- PBPK export packaging from the canonical dermal screening scenario
- PBPK export packaging from the canonical inhalation screening scenario with transient concentration points
- Full PBPK external-import package semantics for the canonical dermal screening scenario
- Tier 1 personal-care pump spray scenario-package probability bounds over governed NF/FF support points
- Worker inhalation surrogate execution for a controlled janitorial disinfectant trigger spray
- Worker inhalation surrogate execution for a study-like handheld BAC trigger spray linked to a narrow occupational concentration benchmark band
- Worker dermal absorbed-dose execution for a study-like handheld BAC trigger spray linked to a narrow occupational dermal loading benchmark band
- Worker dermal extreme-loading execution case proving retained surface-loading limits and runoff reporting

## Tolerances

- Numeric regression checks use `pytest.approx(..., rel=1e-6)`.
- Benchmark cases are deterministic and should remain stable unless the algorithm ID or defaults version changes intentionally.
- Physical-cap regression cases are intended to lock bounded screening behavior, not to claim full aerosol dynamics or dermal permeation kinetics.

## Provenance Expectation

- Every benchmarked result must carry the current defaults pack version.
- If the defaults pack changes, update both the benchmark fixture and the benchmark notes explicitly.
- Goldset entries must carry at least one external source anchor and should identify whether the
  case is benchmark-regressed, integration-only, or still a challenge case.
