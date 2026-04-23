# Release Trust Checklist

Use this checklist before treating the current public build as ready for broad external use.

## Required posture

- Keep the release label at `ready` only while heuristic defaults and partial validation
  families remain explicit through warnings, curation reports, and validation gaps.
- Keep worker extension layers described as bounded expert features, not mature solver replacements.
- Keep heuristic defaults and partial validation families visible through warnings
  and validation gaps.

## Required trust resources

- `contracts://manifest`
- `release://metadata-report`
- `release://readiness-report`
- `release://security-provenance-review-report`
- `verification://summary`
- `validation://coverage-report`
- `defaults://curation-report`

## Required release commands

```bash
uv run ruff check .
uv run pytest
uv build
uv run generate-exposure-contracts
uv run validate-evals
uv run check-exposure-release-artifacts
```

## Human sign-off questions

- Which branches are benchmarked versus only context-anchored?
- Which defaults branches remain heuristic?
- Are remote deployment controls configured in the MCP and, where needed, reinforced at the gateway?
- Are any downstream clients hiding warning-level trust findings?
