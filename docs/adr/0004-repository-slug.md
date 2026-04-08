# ADR 0004: Public Naming Transition

- Status: Accepted
- Date: 2026-04-08

## Context

The public product name is now:

- `Direct-Use Exposure MCP`

The current technical identifiers are:

- GitHub repository slug: `ToxMCP/direct-use-exposure-mcp`
- Python package: `exposure-scenario-mcp`
- Import path: `exposure_scenario_mcp`
- MCP server name: `exposure_scenario_mcp`

The new product name is a better scientific fit now that the suite boundary is explicit:
this MCP owns direct-use and near-field external-dose construction, while Fate MCP,
Dietary MCP, PBPK MCP, and ToxClaw own adjacent concerns.

At the same time, the package and protocol identifiers are already live in:

- badges
- clone instructions
- package metadata
- generated release artifacts
- contract manifests
- review and validation outputs

## Decision

Adopt `Direct-Use Exposure MCP` as the canonical public product name.

Rename the GitHub repository slug now to `ToxMCP/direct-use-exposure-mcp`.

Keep the Python package name, import path, CLI command, and MCP server identifier stable through
the `v0.1.x` line.

Treat any package- or protocol-level technical rename as a later compatibility-managed change
rather than a silent documentation cleanup.

## Consequences

Positive:

- the public name now matches the actual scientific boundary more closely
- the suite can reserve broader names like `Exposure MCP` for a future orchestrated family
- the public GitHub URL now matches the product name
- package users do not lose import paths or CLI entry points during the first released line

Negative:

- package/protocol identifiers remain temporarily different from the public repo name
- docs must remain explicit about the staged naming policy
- a future package rename will still require release coordination

## Follow-up

If the suite decides to complete the technical rename later, coordinate it with:

- badges and clone instructions
- package metadata and CLI migration notes
- generated release artifacts
- contract manifests and suite-level documentation
