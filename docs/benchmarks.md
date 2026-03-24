# Benchmark Corpus

The deterministic benchmark corpus for `v0.1.0` is stored in `tests/fixtures/benchmark_cases.json`.

## Purpose

- Lock down core screening and inhalation calculations against hand-worked expectations.
- Confirm the defaults pack version used during the calculation.
- Prevent silent numeric drift during later refactors.

## Current Coverage

- Adult dermal leave-on hand cream screening
- Adult inhalation trigger spray screening
- Child direct-oral liquid screening
- Adult dermal cream volume-to-mass conversion with density override precedence
- Cross-route aggregate summary with contributor fractions and limitation flagging
- Zero-baseline scenario comparison with undefined percentage-delta handling
- PBPK export packaging from the canonical dermal screening scenario

## Tolerances

- Numeric regression checks use `pytest.approx(..., rel=1e-6)`.
- Benchmark cases are deterministic and should remain stable unless the algorithm ID or defaults version changes intentionally.

## Provenance Expectation

- Every benchmarked result must carry the current defaults pack version.
- If the defaults pack changes, update both the benchmark fixture and the benchmark notes explicitly.
