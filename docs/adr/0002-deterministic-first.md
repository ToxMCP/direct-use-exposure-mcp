# ADR 0002: Deterministic-First v0.1 Strategy

## Status

Accepted

## Context

The PRD identifies probabilistic modeling as a false-precision risk when defaults and use-pattern evidence are weak. The first release must remain transparent, benchmarkable, and easy for downstream MCPs to audit.

## Decision

`v0.1.0` will be deterministic-first:

- Mandatory support for screening consumer scenarios
- Mandatory support for simple aggregate/co-use summaries
- Mandatory support for inhalation/aerosol screening
- Contract-ready placeholders for later async/distribution workflows
- No Monte Carlo core in the initial release

## Consequences

- The server emits point estimates with explicit assumptions and limitations.
- Job abstractions exist only as compatibility scaffolding for future probabilistic plugins.
- Validation focuses on reproducibility and assumption transparency before sophistication.

