# ADR 0003: Route, Unit, and Assumption Governance

## Status

Accepted

## Context

Route semantics and units are the main interoperability risk at the handoff boundary with PBPK MCP and the future orchestration/reporting layer.

## Decision

The module enforces:

- Explicit route tags: `dermal`, `oral`, `inhalation`
- Canonical dose units: `mg/day`, `mg/event`, `mg/kg-day`, `mg/m3`
- Route-specific metrics rather than a generic dose blob
- Explicit assumption emission for every user-supplied, defaulted, and derived parameter
- Hard failures for missing essential parameters and incompatible route/unit combinations
- Versioned defaults with source metadata and hashes

## Consequences

- Aggregate summaries will not silently collapse incompatible component units.
- PBPK handoff objects remain normalized and mechanically consumable.
- Defaults remain discoverable and auditable even when they are not overridden by the caller.
