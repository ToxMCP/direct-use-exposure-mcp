# Maintainer Operating Model

This repo still operates with a small maintainer pool, so the process has to compensate for bus-factor risk.

## Subsystem ownership

- Runtime and transports: CLI, server startup, HTTP controls, audit logging
- Contracts and release assets: schemas, examples, manifests, release metadata
- Domain engines: screening routes, Tier 1 inhalation, worker bridges, integrated workflow

Treat ownership as accountability for review and release-readiness, not as a private code territory.

## Release-buddy rotation

- Every release candidate should name one buddy who is not the author.
- The buddy verifies CI, artifact metadata, docs links, and boundary/auditability notes.
- If no second maintainer is available, pause the release rather than silently collapsing review.

## Monthly triage cadence

- Run the scheduled `Monthly Maintenance` workflow or trigger it manually after high-churn periods.
- Review dependency audit output, the full-tree mypy baseline, and any drift in prompts/tutorial docs.
- Convert repeated review comments into checklist updates, tests, or prompt/tutorial improvements.

## Default escalation rules

- Any change that widens HTTP exposure, changes release metadata semantics, or alters benchmark-backed routing should receive a second review.
- Any change that hides warnings or limitations from downstream outputs should be treated as release-blocking.
