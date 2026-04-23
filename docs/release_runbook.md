# Release Runbook

Use this runbook when publishing a release candidate, not just when cutting the final tag.

## Roles

- Release owner: prepares the branch, runs the commands, and drafts notes.
- Release buddy: independently reviews the trust posture, artifact metadata, and docs links.

## Preflight

- Confirm the branch is up to date and the defaults manifest version is intentional.
- Confirm any schema, example, prompt, or resource changes are regenerated and committed.
- Confirm `streamable-http` changes include operator-doc updates and test coverage.

## Required commands

```bash
uv run ruff check .
uv run pytest
uv run python scripts/check_mypy_baseline.py
uv build
uv run generate-exposure-contracts
uv run validate-evals
uv run check-exposure-release-artifacts
uv run exposure-scenario-mcp --healthcheck
```

## Buddy review checklist

- Compare `docs/contracts/contract_manifest.json` counts with the generated release notes.
- Confirm release metadata still matches the built artifacts in `dist/`.
- Confirm any new warnings, limitations, or benchmark-boundary notes are visible in docs.
- Confirm the guided tutorial links still resolve to checked-in examples.

## Publish and verify

- Push the release branch or tag only after the buddy signs off.
- Re-check the public GitHub Actions run for green CI on the exact pushed commit.
- Capture any known limitations in the release notes rather than relying on memory.
