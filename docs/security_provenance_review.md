# Security And Provenance Review

Direct-Use Exposure MCP publishes a machine-readable security and provenance review so
release decisions are tied to the live public surface rather than a static checklist.

## Review Intent

- Confirm the tool and resource surface is fully published and inspectable.
- Verify defaults integrity through explicit versioning and SHA256 hashing.
- Confirm public outputs preserve provenance or deterministic downstream evidence traces.
- Keep remaining remote-deployment and heuristic-default cautions visible as warnings.

## Review Outputs

- `docs://security-provenance-review`: human-readable review derived from the current surface
- `release://security-provenance-review-report`: machine-readable review payload

## Expected Warning Classes In v0.2.0

- Remote `streamable-http` deployment still depends on external auth, TLS, and origin controls.
- Some screening defaults remain heuristic and must be interpreted as flagged screening factors,
  not curated final exposure-factor selections.

## Release Use

- Read the review alongside `release://readiness-report`.
- Treat any `blocked` finding as a release stop.
- Resolve or explicitly accept every `warning` before exposing the server outside a trusted local
  workflow.
