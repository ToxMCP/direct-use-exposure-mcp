# Contributing to Exposure Scenario MCP

Exposure Scenario MCP is the deterministic external-dose construction layer in
the ToxMCP suite. Contributions should keep the server explicit, auditable, and
scientifically bounded.

## Local setup

Prerequisites:

- Python 3.12 or newer
- `uv`

Bootstrap a local checkout with:

```bash
uv sync --extra dev
uv run generate-exposure-contracts
uv run pytest
```

Run the server locally with:

```bash
uv run exposure-scenario-mcp --transport stdio
```

## Before you open a change

Run the local quality gate for any behavior change:

```bash
uv run ruff check .
uv run pytest
uv build
uv run generate-exposure-contracts
uv run check-exposure-release-artifacts
```

If your change touches schemas, contracts, examples, or public resources, make
sure the generated assets in `schemas/` and `docs/contracts/` are refreshed in
the same change.

## Engineering rules

- Keep the server bounded to external-dose construction. Do not expand it into
  PBPK execution, BER derivation, PoD derivation, or final risk decision logic.
- Favor deterministic, inspectable behavior over probabilistic or opaque
  screening logic.
- Preserve explicit units, route semantics, defaults provenance, quality flags,
  and limitation notes.
- Do not silently collapse incompatible route, duration, or dose semantics.
- Keep tool outputs, schemas, examples, and MCP resources synchronized.
- Update operator-facing docs when a change affects setup, defaults behavior,
  contracts, release posture, or suite integration.

## Scientific and integration guidelines

When changing defaults, plugins, or runtime behavior:

- keep the assumption ledger explicit and traceable
- add tests for both direct success paths and degraded or invalid-input paths
- document heuristic factors honestly; do not present them as curated evidence
- update `docs/defaults_evidence_map`-backed content when defaults sources change

When changing suite-facing handoffs:

- preserve published request and response schemas
- regenerate examples and contract assets
- update `docs/suite_integration.md`
- verify PBPK and ToxClaw wrapper semantics rather than assuming compatibility

## Testing expectations

At minimum, behavior changes should add or update coverage in `tests/` for:

- runtime and plugin behavior
- contract/schema generation where relevant
- suite handoff packaging where relevant
- failure or invalid-input cases if the new path can degrade

## Security and data handling

- Keep secrets, tokens, and private sponsor data out of the repository, fixtures,
  and generated artifacts.
- Treat remote `streamable-http` deployment as untrusted unless external auth
  and origin controls are in place.
- Keep generated examples synthetic and auditable.

## Release discipline

If you change the public surface for a release:

- update the README
- update release notes under `docs/releases/`
- make sure release metadata and artifact verification still pass

## Attribution

Before importing external code or text, preserve upstream licensing and add any
required attribution beside the imported material or in the appropriate project
documentation.
