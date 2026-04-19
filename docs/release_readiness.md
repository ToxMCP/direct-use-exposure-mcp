# Release Readiness

Release gating for `v0.2.0` is benchmark-first, contract-first, and provenance-first.

## Required Gates

- `uv run ruff check .`
- `uv run pytest`
- `uv build`
- `uv run generate-exposure-contracts`
- `uv run validate-evals`
- `uv run check-exposure-release-artifacts`

## Minimum Release Claims

- The MCP surface is machine-readable through the contract manifest and schema resources.
- Defaults are versioned and hashed.
- Defaults curation status is published branch-by-branch through `defaults://curation-report`.
- Packaged Tier 1 inhalation airflow, particle, and product-family screening profiles are
  versioned, hashed, and published as a machine-readable manifest.
- The Tier 1 parameter-pack documentation resource is published so source locators used in the
  Tier 1 manifest resolve to a live MCP guide.
- Packaged Tier B archetype-library sets are versioned, hashed, and published as a machine-readable manifest.
- The archetype library can publish governed Tier 1 inhalation templates when a packaged set is
  explicitly defined around NF/FF screening semantics.
- Packaged Tier C probability-bounds profiles are versioned, hashed, and published as a machine-readable manifest.
- Probability-bounds profiles carry explicit driver-family taxonomy, product family, dependency cluster,
  fixed axes, and handling semantics.
- Packaged Tier C coupled-driver scenario-package profiles are versioned, hashed, and published as a machine-readable manifest.
- Scenario-package probability profiles carry explicit package-family taxonomy, product family,
  dependency axes, and packaged handling semantics.
- Scenario-package probability profiles can evaluate packaged Tier 1 inhalation archetype states
  when a governed near-field/far-field set is published for the target use context.
- A typed validation dossier is published so benchmark domains, cited external validation
  datasets, heuristic source families, open evidence gaps, and executable validation checks are
  machine-readable rather than prose-only.
- Executable validation reference bands are versioned, hashed, and published through
  `validation://reference-bands` so narrow realism checks do not rely on hardcoded thresholds.
- Curated dermal contact defaults are published for personal-care hand application and
  household-cleaner wipe contact, and curated spray airborne-fraction defaults are
  published for household-cleaner and personal-care spray contexts instead of relying
  only on generic transfer, retention, and spray heuristics.
- Scenario, aggregate, comparison, and PBPK export outputs carry provenance.
- Scenario outputs publish Tier A uncertainty diagnostics, and Tier B support is limited to
  deterministic envelopes, packaged archetype-library sets, and explicit parameter-bounds propagation.
- Tier C support is limited to packaged single-driver or scenario-package probability bounds
  without Monte Carlo sampling or joint-distribution claims.
- Inhalation requests expose `requestedTier` and `tierUpgradeAdvisories` as explicit Tier 1
  routing hooks, a dedicated Tier 1 NF/FF tool builds deterministic spray scenarios with
  explicit geometry, timing, airflow-class, and particle-regime inputs, and the packaged
  Tier 1 manifest publishes the governing screening profiles behind those classes.
- Tier 1 NF/FF outputs emit explicit alignment warnings when caller-supplied geometry or regime
  inputs diverge materially from a matched packaged profile anchor.
- Pre-release downstream evidence and refinement bundles emit deterministic content hashes and stable IDs.
- Security and provenance findings are published through `release://security-provenance-review-report`.
- Release metadata is published through `release://metadata-report`.
- Published release metadata includes artifact digests and sizes for the expected wheel and sdist.

## Benchmark Matrix

- `dermal_hand_cream_screening` [scenario] Adult leave-on hand cream screening case with default body weight, surface area, curated hand-application transfer, and route-semantics retention.
- `dermal_face_cream_sccs_screening` [scenario] Adult leave-on face cream screening case aligned to SCCS Notes of Guidance Table 3A daily amount and Table 4 application frequency.
- `inhalation_trigger_spray_screening` [scenario] Adult EU trigger spray inhalation case with explicit room volume and regional default ventilation/duration.
- `inhalation_tier1_trigger_spray_nf_ff` [scenario] Adult EU trigger spray Tier 1 NF/FF case with explicit source distance, spray duration, near-field volume, and airflow class.
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
