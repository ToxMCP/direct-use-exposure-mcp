# Test Evidence Summary

This repository uses command-level release gates plus typed contract validation.

## Standard gates

```bash
uv run ruff check .
uv run pytest
uv run generate-exposure-contracts
```

## Release gates

```bash
uv run ruff check .
uv run pytest
uv build
uv run generate-exposure-contracts
uv run check-exposure-release-artifacts
```

## What the public evidence shows

- Contract assets are generated and schema-validated
- Release metadata is checked against built artifacts
- Validation coverage, reference bands, time-series packs, and goldset mappings are published
- Wheel-install smoke testing checks packaged manifests against the installed distribution

## What this is not

- a full regulatory validation dossier on its own
- proof that every route family is equally mature
- a substitute for reviewing published limitations and validation gaps
