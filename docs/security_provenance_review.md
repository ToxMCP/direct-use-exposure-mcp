# Security And Provenance Review

Direct-Use Exposure MCP publishes a machine-readable security and provenance review so
release decisions are tied to the live public surface rather than a static checklist.

## Review Intent

- Confirm the tool and resource surface is fully published and inspectable.
- Verify defaults integrity through explicit versioning and SHA256 hashing.
- Confirm public outputs preserve provenance or deterministic downstream evidence traces.
- Keep heuristic defaults and deployment boundaries explicit and reviewable.

## Review Outputs

- `docs://security-provenance-review`: human-readable review derived from the current surface
- `release://security-provenance-review-report`: machine-readable review payload

## Current Posture In v0.2.1

- The live review can remain `acceptable` even when some screening branches still use
  heuristic defaults, as long as those branches stay explicit and auditable.
- Heuristic screening branches remain visible through `defaults://curation-report`,
  `docs://defaults-curation-report`, `docs://defaults-evidence-map`,
  `docs://provenance-policy`, and `docs://validation-dossier`.

## Published Remote HTTP Controls

- `streamable-http` now ships first-party support for shared bearer-token auth.
- Browser-facing deployments reject present unconfigured `Origin` headers and can enforce an
  explicit origin allow-list.
- Request bodies are size-limited in-process by default.
- TLS termination and rate limiting still belong at the gateway or host layer.

## Release Use

- Read the review alongside `release://readiness-report`.
- Treat any `blocked` finding as a release stop.
- If a future `warning` appears, keep it explicit in downstream UX before exposing the server
  outside a trusted local workflow.
