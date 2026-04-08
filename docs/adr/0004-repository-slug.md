# ADR 0004: Repository Slug Stability

- Status: Accepted
- Date: 2026-04-08

## Context

The public GitHub repository slug is currently:

- `ToxMCP/expossure-scenario-mcp`

The spelling is awkward, but it is also already live in:

- badges
- clone instructions
- local setup scripts
- published release metadata
- external notes and review artifacts

Changing the slug immediately would improve polish, but it would also create avoidable
churn for the released `0.1.0` line.

## Decision

Keep the current repository slug through the `v0.1.x` series.

Do not silently rename the GitHub repository as part of documentation cleanup. Revisit a
rename only as an explicit release-management decision for a future minor release or for a
broader ToxMCP suite naming pass.

## Consequences

Positive:

- avoids breaking clone URLs, badges, and existing references during the first released line
- keeps release and review artifacts stable
- avoids creating unnecessary GitHub and packaging churn while the platform surface is still
  settling

Negative:

- the public-facing name remains awkward for now
- documentation must be explicit that the current slug is intentional, not an unnoticed typo

## Follow-up

If the suite adopts a naming normalization pass later, the rename should be coordinated with:

- README and badge updates
- release-note callouts
- clone and onboarding guidance
- any suite-level orchestrator or cross-MCP documentation
