## Summary

- What changed?
- Why now?

## Boundary Checks

- [ ] Public MCP tool names remain unchanged, or any additive surface is documented.
- [ ] Screening-first and external-dose-only boundaries remain explicit.
- [ ] No hidden live external API calls were added to integrated evidence workflows.

## Auditability Checks

- [ ] New warnings, limitations, manual-review gates, or provenance changes are called out.
- [ ] `streamable-http` changes preserve first-party controls and operator-facing docs.
- [ ] Tutorial, prompt, schema, or example drift is covered by tests or regenerated artifacts.

## Review Notes

- [ ] At least one reviewer outside the author validated the intended behavior.
- [ ] Release-buddy impact is noted if this PR touches release, CI, or packaging paths.
