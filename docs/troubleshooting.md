# Troubleshooting

## Common Failures

- `comparison_chemical_mismatch`: the compared scenarios do not share the same `chemical_id`.
- `pbpk_body_weight_missing`: the scenario does not resolve `body_weight_kg`.
- `pbpk_inhalation_duration_missing`: inhalation PBPK export needs explicit event duration.
- `pbpk_unit_unsupported`: PBPK handoff accepts only canonical external dose units.
- `aggregate_component_duplicate`: aggregate inputs reused the same component scenario.

## Troubleshooting Sequence

1. Validate the request against the published schema resource.
2. Inspect `qualityFlags`, `limitations`, and `provenance` in the returned object.
3. Check the defaults manifest and defaults evidence map for the active factor source.
4. Re-run contract generation after changing any outward-facing schema or example.

## Remote Deployment Caution

- The server does not add authentication or origin enforcement on its own.
- If you expose `streamable-http`, put it behind trusted network controls or a gateway.
