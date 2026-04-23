# Troubleshooting

## Common Failures

- `comparison_chemical_mismatch`: the compared scenarios do not share the same `chemical_id`.
- `pbpk_body_weight_missing`: the scenario does not resolve `body_weight_kg`.
- `pbpk_inhalation_duration_missing`: inhalation PBPK export needs explicit event duration.
- `aggregate_internal_equivalent_bioavailability_missing`: internal-equivalent aggregation needs
  route bioavailability fractions for each represented route.
- `pbpk_unit_unsupported`: PBPK handoff accepts only canonical external dose units.
- `aggregate_duplicate_component`: aggregate inputs reused the same component scenario.
- `pbpk_transient_profile_duration_missing`: transient inhalation PBPK export needs explicit event
  duration.
- `pbpk_transient_profile_route_metrics_missing`: the source inhalation scenario did not expose
  start and end air concentrations for transient export.
- `probability_bounds_profile_missing`: the selected Tier C driver profile ID is not published in
  the active manifest.
- `scenario_package_probability_template_missing`: a packaged Tier C support point references an
  archetype or template ID that is not available in the active release.

## Scenario Review Checks

1. Confirm the request is reaching the intended route and scenario class.
2. Inspect `assumptions`, `qualityFlags`, and `limitations` before interpreting the dose.
3. Treat `heuristic_default_source` flags as a cue to inspect the cited defaults branch.
4. Check `validationSummary` to see whether executable bands or external anchors were applied.

## Troubleshooting Sequence

1. Validate the request against the published schema resource.
2. Inspect `qualityFlags`, `limitations`, `provenance`, and tool-result `_meta` in the returned object.
3. Check the defaults manifest and defaults evidence map for the active factor source.
4. Re-run contract generation after changing any outward-facing schema or example.

## Error Metadata

- `errorCode` is the domain-specific failure code. Use it for scientific/debug interpretation.
- `mcpErrorCode` is the generic MCP boundary classification. It does not replace the domain code.
- Current mapping is intentionally conservative:
  - `InternalError` -> `-32603` (`INTERNAL_ERROR`)
  - all other current tool-facing failures -> `-32602` (`INVALID_PARAMS`)

## Docker And Deployment Checks

- Rebuild the image after dependency changes so the locked `uv.lock` install is refreshed.
- If the container exits immediately under stdio, verify the client is launching the MCP process
  rather than expecting an HTTP listener.
- If `streamable-http` is exposed, confirm the port mapping and pass
  `--host 0.0.0.0 --port 8000` or your chosen bound port explicitly.
- If `streamable-http` is exposed remotely, set `--http-bearer-token` or
  `EXPOSURE_SCENARIO_MCP_HTTP_BEARER_TOKEN` before binding beyond localhost.
- For browser-based clients, set `--http-allowed-origin` or
  `EXPOSURE_SCENARIO_MCP_HTTP_ALLOWED_ORIGINS`.
- If browser requests return `origin_not_allowed`, add the exact browser origin to the allow-list
  or remove browser access; non-browser MCP clients normally omit `Origin`.
- Keep the default request-size limit unless you have a reviewed reason to widen it with
  `--http-max-request-bytes`.
- The bundled container health check now boots the packaged server, loads defaults, and verifies
  representative tools, resources, and prompts.
- Add gateway or endpoint probes when you need transport-level liveness checks for
  `streamable-http` deployments.

## Remote Deployment Caution

- The server now supports first-party bearer-token auth, fail-closed Origin validation, origin
  allow-lists, and request-size limits for `streamable-http`.
- If you expose `streamable-http` remotely, still keep TLS termination, rate limiting, and network
  scoping at a trusted gateway or host boundary.
