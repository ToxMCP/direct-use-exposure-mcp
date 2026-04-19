# ADR 0001: External-Dose Boundary

## Status

Accepted

## Context

Direct-Use Exposure MCP sits between an upstream orchestration/reporting layer and downstream toxicokinetics in PBPK MCP. The largest architecture risk is boundary bleed, where exposure construction, toxicokinetics, and WoE logic become entangled.

## Decision

This module owns only external exposure construction and refinement:

- Deterministic consumer screening scenarios
- Inhalation/aerosol screening scenarios
- Simple aggregate/co-use exposure summaries
- PBPK-ready export objects
- Scenario comparison records and assumption deltas
- Explicit assumption/provenance capture

This module explicitly does not own:

- Internal exposure estimation
- PBPK execution
- PoD derivation
- BER or WoE scoring
- Final risk conclusions
- Large-scale occupational or environmental modeling in `v0.1.0`

## Consequences

- Tool outputs stay route- and dose-focused, not hazard- or risk-focused.
- PBPK export objects include dosing semantics only, not product narratives.
- The future orchestration/reporting layer remains responsible for problem formulation, tier selection, and final scenario choice.
