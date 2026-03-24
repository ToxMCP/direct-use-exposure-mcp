# Release Readiness

Release gating for `v0.1.0` is benchmark-first, contract-first, and provenance-first.

## Required Gates

- `uv run ruff check .`
- `uv run pytest`
- `uv build`
- `uv run generate-exposure-contracts`
- `uv run check-exposure-release-artifacts`

## Minimum Release Claims

- The MCP surface is machine-readable through the contract manifest and schema resources.
- Defaults are versioned and hashed.
- Scenario, aggregate, comparison, and PBPK export outputs carry provenance.
- ToxClaw evidence and refinement bundles emit deterministic content hashes and stable IDs.
- Security and provenance findings are published through `release://security-provenance-review-report`.
- Release metadata is published through `release://metadata-report`.
- Published release metadata includes artifact digests and sizes for the expected wheel and sdist.

## Benchmark Matrix

- `dermal_hand_cream_screening` [scenario] Adult leave-on hand cream screening case with default body weight, surface area, retention, and transfer efficiency.
- `inhalation_trigger_spray_screening` [scenario] Adult EU trigger spray inhalation case with explicit room volume and regional default ventilation/duration.
- `oral_direct_oral_screening` [scenario] Child direct-oral liquid case covering oral screening semantics and volume-to-mass conversion defaults.
- `dermal_density_precedence_volume_case` [scenario] Adult dermal cream case covering physical-form density override precedence for mL inputs.
- `cross_route_aggregate_summary` [aggregate] Aggregate summary spanning the canonical dermal and inhalation benchmark scenarios.
- `zero_baseline_comparison` [comparison] Comparison case with a zero baseline dose to lock down undefined percentage-delta handling.
- `dermal_pbpk_export` [pbpk_export] PBPK export case for the canonical dermal screening scenario.
- `dermal_pbpk_external_import_package` [pbpk_external_import_package] Full PBPK external-import package case for the canonical dermal screening scenario.

## Known Cautions

- Remote `streamable-http` deployment requires external authentication and origin controls.
- The module remains deterministic-first and does not ship a probabilistic population engine.
- The module does not own PBPK execution, internal dose estimation, BER, PoD derivation, or final risk decisions.
