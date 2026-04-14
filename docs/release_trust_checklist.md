# Release Trust Checklist

Use this checklist before calling the current public release "ready with known limitations."

## Release posture

- Release label remains `ready_with_known_limitations`.
- Public messaging does not imply decision-grade risk conclusions.
- Worker inhalation and worker dermal surfaces stay described as bounded expert layers.

## Required trust artifacts

- `docs/contracts/contract_manifest.json`
- `docs/releases/v0.1.0.release_metadata.json`
- `docs/release_readiness.md`
- `docs/security_provenance_review.md`
- `docs/test_evidence_summary.md`
- `docs/deployment_hardening.md`

## Required release commands

```bash
uv run ruff check .
uv run pytest
uv build
uv run generate-exposure-contracts
uv run check-exposure-release-artifacts
```

## Human review questions

- What is benchmarked versus only context-anchored?
- Which defaults branches remain heuristic?
- Are any warning-level trust findings being hidden in downstream UX?
- Are remote deployment controls documented and enforced outside the MCP?

## Do not claim

- final risk conclusions
- PBPK execution
- full occupational solver equivalence
- probabilistic population modeling
- broad route-family validation where the validation dossier still marks partial coverage
