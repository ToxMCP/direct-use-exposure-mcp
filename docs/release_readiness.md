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

## Known Cautions

- Remote `streamable-http` deployment requires external authentication and origin controls.
- The module remains deterministic-first and does not ship a probabilistic population engine.
- The module does not own PBPK execution, internal dose estimation, BER, PoD derivation, or final risk decisions.
