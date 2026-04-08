# Exposure Scenario MCP Planning Status

This file replaces the original pre-release TaskMaster backlog.

## Status

The original TaskMaster plan was useful during initial buildout, but it is no longer the
authoritative status source for this repository.

The repo is already released on `main` as:

- release version: `0.1.0`
- release commit: `506df226ec7f0a62af70dbb46ba31f74535aace5`
- readiness status: `ready_with_known_limitations`
- review status: `acceptable_with_warnings`
- defaults version: `2026.04.07.v18`
- published surface: `29` tools, `53` resources, `2` prompts, `132` schemas, `62` examples
- benchmark cases: `22`

Authoritative current-state documents:

- [README.md](./README.md)
- [docs/capability_maturity_matrix.md](./docs/capability_maturity_matrix.md)
- [docs/releases/v0.1.0.md](./docs/releases/v0.1.0.md)
- [docs/exposure_platform_architecture.md](./docs/exposure_platform_architecture.md)
- [docs/release_readiness.md](./docs/release_readiness.md)

## Why the original plan was retired

The original TaskMaster artifact still showed foundational implementation phases as
`pending`, which now conflicts with the released `0.1.0` surface and its benchmarked,
published contract set.

To avoid contradictory status signaling:

- the old plan is retained in git history only
- this file now serves as an archival status note
- live implementation priorities should be tracked through the repository’s release docs,
  issues, and future planning artifacts

## Current next-phase workstreams

These are the active strategic workstreams after the `0.1.0` release, replacing the old
pre-release phase plan:

1. Deepen validation coverage with additional external benchmark datasets and stronger
   time-series anchors.
2. Improve dermal kinetics beyond bounded physchem and barrier-material modifiers.
3. Keep worker high-tier execution as explicit bounded execution plus governed external
   exchange until a native solver integration is justified.
4. Preserve modular boundaries between Exposure MCP, Fate MCP, Dietary MCP, and PBPK MCP.
5. Improve documentation legibility so the released MCP surface is explained as:
   core engine + bounded worker/exchange layers + validation/governance layers.

## Archive note

If the exact original TaskMaster graph is needed for historical review, recover it from git
history rather than treating this file as a live backlog.
