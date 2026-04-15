# PRD — Deterministic Two-Zone Tier 1 NF/FF Inhalation Model

## Executive summary

Replace the current heuristic Tier 1 NF/FF inhalation path with a deterministic, mass-conserving two-zone model while preserving the current MCP request/response surface, provenance framework, and benchmark stability strategy.

### Core decisions

- Keep the current `InhalationTier1ScenarioRequest` as the primary request schema.
- Add only optional expert-override fields rather than introducing new mandatory inputs.
- Implement a new pure solver for a two-zone affine linear system with an analytical primary path.
- Keep the current heuristic Tier 1 path as a compatibility fallback during migration.
- Reuse the current airflow classes, deposition defaults, local entrainment floor, and product-profile registry wherever possible.
- Deprecate `distance_factor` and `particle_persistence_factor` as direct concentration multipliers.

## Product goals

### Goals

1. Produce mass-conserving NF and FF concentration trajectories during active spray and post-spray decay.
2. Preserve deterministic execution and auditable assumptions.
3. Preserve the existing `ExposureScenario` response contract.
4. Keep runtime comfortably below 1 second per request.
5. Support dual-path operation during benchmark migration.

### Non-goals

1. Full CFD or plume-resolved jet simulation.
2. Full droplet evaporation and polydisperse aerosol dynamics.
3. Full regional respiratory tract deposition modeling.
4. Multi-room or HVAC-network modeling.
5. Probabilistic uncertainty propagation in the primary production path.

## Current-state problem statement

The current Tier 1 implementation is not a true two-zone mass-balance model. It computes a single-zone far-field room-average concentration and then adds a near-field increment of the form:

`emission_rate / interzonal_mixing_rate * distance_factor * particle_persistence_factor`

This creates a useful screening output, but it does not explicitly solve coupled NF and FF state equations, does not conserve mass across compartments, and uses `source_distance_m` as a heuristic multiplier rather than as part of a physically defined source/zone geometry.

## Physics design

### 1. Governing equations

Let:

- `V_NF` = near-field volume
- `V_FF` = far-field volume = `V_room - V_NF`
- `G(t)` = emission rate into air during spraying
- `η` = source fraction emitted directly into the NF
- `β` = bidirectional interzonal airflow between NF and FF
- `Q_room` = room ventilation exhaust flow
- `φ` = fraction of room ventilation directly assigned to the NF
- `k_NF`, `k_FF` = non-ventilation first-order loss rates (deposition, other governed sinks)
- `C_sup` = supply-air concentration, default 0

General form:

```math
V_{NF}\frac{dC_{NF}}{dt}
=
\eta G(t)
-\beta(C_{NF}-C_{FF})
-k_{NF}V_{NF}C_{NF}
-\phi Q_{room}(C_{NF}-C_{sup})
```

```math
V_{FF}\frac{dC_{FF}}{dt}
=
(1-\eta)G(t)
+\beta(C_{NF}-C_{FF})
-k_{FF}V_{FF}C_{FF}
-(1-\phi)Q_{room}(C_{FF}-C_{sup})
```

Default production simplification:

- `η = 1.0`
- `φ = 0.0`
- `C_sup = 0`

Then:

```math
\frac{dC_{NF}}{dt}
=
\frac{G(t)}{V_{NF}}
-
\left(\frac{\beta}{V_{NF}}+\lambda_{NF}\right)C_{NF}
+
\frac{\beta}{V_{NF}}C_{FF}
```

```math
\frac{dC_{FF}}{dt}
=
\frac{\beta}{V_{FF}}C_{NF}
-
\left(\frac{\beta}{V_{FF}}+\lambda_{FF}\right)C_{FF}
```

with:

```math
\lambda_{NF}=k_{NF}
```

```math
\lambda_{FF}=k_{FF}+\frac{Q_{room}}{V_{FF}}
```

### 2. Matrix form

```math
x(t)=
\begin{bmatrix}
C_{NF}(t)\\
C_{FF}(t)
\end{bmatrix}
,\qquad
\dot x(t)=Ax(t)+u
```

where

```math
A=
\begin{bmatrix}
-a & b\\
c & -d
\end{bmatrix}
```

and

```math
a=\frac{\beta}{V_{NF}}+\lambda_{NF},\quad
b=\frac{\beta}{V_{NF}},\quad
c=\frac{\beta}{V_{FF}},\quad
d=\frac{\beta}{V_{FF}}+\lambda_{FF}
```

For phase 1:

```math
u=
\begin{bmatrix}
G/V_{NF}\\
0
\end{bmatrix}
```

during spray, and `u = 0` after spray stops.

### 3. Steady state under constant emission

For a constant source `u = [u_N, u_F]^T`, the steady-state solution is:

```math
x_{ss}=-A^{-1}u
```

Expanded:

```math
C_{NF,ss}=\frac{d\,u_N+b\,u_F}{ad-bc}
```

```math
C_{FF,ss}=\frac{c\,u_N+a\,u_F}{ad-bc}
```

For the classical NF/FF case with source only in NF, no NF-local loss, and room ventilation applied in FF only:

```math
C_{FF,ss}=\frac{G}{Q_{room}}
```

```math
C_{NF,ss}=\frac{G}{Q_{room}}+\frac{G}{\beta}
```

### 4. Transient analytical solution

For a constant source over one phase:

```math
x(t)=x_{ss}+e^{At}(x_0-x_{ss})
```

Eigenvalues:

```math
r_{1,2}=
-\frac{a+d}{2}
\pm
\frac{1}{2}\sqrt{(a-d)^2+4bc}
```

A practical closed form for the matrix exponential is:

```math
e^{At}
=
\frac{e^{r_1 t}(A-r_2 I)-e^{r_2 t}(A-r_1 I)}{r_1-r_2}
```

The time integral over a phase is:

```math
\int_0^t x(s)\,ds
=
x_{ss}t + A^{-1}(e^{At}-I)(x_0-x_{ss})
```

For the post-spray phase, set `u = 0` and propagate from the end-of-spray state.

### 5. Dose equation

Use the NF as the breathing-zone concentration:

```math
M_{inh,event}
=
IR
\int_0^{T_{event}} C_{NF}(t)\,dt
```

where `IR` is inhalation rate.

Then:

```math
M_{inh,day}=M_{inh,event}\times \text{events/day}
```

```math
Dose_{ext}=\frac{M_{inh,day}}{BW}
```

The existing extrathoracic swallowed-fraction handoff can remain as a post-processor on inhaled mass.

## Mapping from current heuristic to the true two-zone model

### Current terms that can be retained

- `released_mass_mg_event / spray_duration_hours` → `G`
- `near_field_volume_m3` → `V_NF`
- `room_volume_m3 - near_field_volume_m3` → `V_FF`
- `air_exchange_rate_per_hour * room_volume_m3` → `Q_room`
- `deposition_rate_per_hour` → baseline `k_NF` / `k_FF`
- `airflow_directionality` profile → default interzonal exchange driver
- `thermal_plume_rate_m3_per_hour + spray_jet_rate_m3_per_hour` → lower bound for `β`

### Terms to deprecate as direct concentration multipliers

- `distance_factor`
- `particle_persistence_factor`

These should not appear directly in the concentration equation. They may still influence defaults or quality flags.

### Key new physics

- explicit state variables `C_NF(t)` and `C_FF(t)`
- explicit bidirectional mass transfer `β(C_NF - C_FF)`
- explicit zone-specific loss rates
- transient source-on / source-off dynamics
- auditable mass-balance accounting

## Parameterization and defaults

## 1. No new mandatory fields

The new model can ship without breaking the request contract by deriving the new parameters from existing fields.

### Optional new fields for expert override

- `interzonalFlowRateM3PerHour`
- `nearFieldLossRatePerHour`
- `farFieldLossRatePerHour`
- `sourceAllocationToNearFieldFraction`
- `ventilationAllocationToNearFieldFraction`
- `solverVariant`

## 2. Default derivation

### Interzonal flow

Default:

```text
β = max(V_NF * exchange_turnover_per_hour,
        local_entrainment_rate_m3_per_hour)
```

> **Note:** `air_exchange_rate_per_hour` (ACH) is intentionally *not* added to `β`. Room ventilation is already represented explicitly as an exhaust term via `Q_room = ACH * V_room` in the ODE. Adding ACH to `β` would double-count ventilation removal from the system.

where:

```text
local_entrainment_rate_m3_per_hour
=
thermal_plume_rate_m3_per_hour + spray_jet_rate_m3_per_hour
```

### Room ventilation

```text
Q_room = air_exchange_rate_per_hour * room_volume_m3
```

### Zone losses

Phase 1 default:

```text
k_NF = deposition_rate_per_hour
k_FF = deposition_rate_per_hour
```

and therefore:

```text
lambda_NF = k_NF
lambda_FF = k_FF + Q_room / V_FF
```

### Source allocation

Phase 1 default:

```text
η = 1.0
```

Rationale: the active emitter is assumed to operate within the NF control volume around the user. This is conservative for self-use sprays and avoids introducing an under-supported geometric split in the initial production release.

## 3. Product-family handling

### Trigger sprays

- retain current profile defaults for source distance, NF volume, and spray duration
- default source split to NF
- keep current deposition and airflow defaults
- preferred initial path for migration

### Pump sprays

- same two-zone solver
- retain packaged NF defaults
- keep particle regime mapping, but use it to affect loss/deposition assumptions rather than a direct NF concentration multiplier

### Aerosol sprays

- same two-zone solver
- migrate only when product-family profile includes a defensible `η` default or a governing rationale for `η = 1.0`
- if volatility diagnostics indicate likely vapour-dominated behavior, keep legacy fallback until a hybrid droplet/vapour path is implemented

## 4. Existing defaults to retain vs deprecate

### Retain

- airflow-directionality class pack
- local entrainment floor
- deposition-rate defaults
- extrathoracic swallow fraction logic
- product profile alignment warnings

### Deprecate or reinterpret

- `particle_persistence_factor` → deprecate as direct multiplier
- `distance_factor` → remove from concentration math; keep only for profile alignment / quality checks

## Numerical implementation plan

## 1. Solver choice

Use an analytical primary path, not a general ODE integrator.

Reason:

- the production use case is piecewise constant source on a 2x2 linear system
- exact state and time-integral solutions exist
- runtime is effectively O(1)
- reproducibility is better than stepwise numerical integration

## 2. Singular / near-singular fallback

Use a deterministic fixed-step RK4 fallback only when the matrix becomes numerically ill-conditioned, for example:

- `β → 0`
- `det(A) → 0`
- repeated eigenvalue with unstable cancellation in the matrix-exponential branch

This fallback remains deterministic because:

- step count is fixed
- tolerances are fixed
- no adaptive stepper is used

## 3. Edge cases

### `β → 0`

Solve as decoupled scalar ODEs and emit a warning-quality flag.

### `V_NF >= V_room`

Keep the current hard validation error.

### `V_FF` extremely small

Reject or warn when the far-field control volume becomes numerically meaningless.

### very short spray duration

Analytical solver handles this cleanly; use `expm1`-style numerics in implementation to avoid cancellation.

### saturation-cap cases

Do not silently clip the internal state in the true mass-balance path. Instead:

- compute a volatility consistency diagnostic
- emit a warning when the calculated zone concentration exceeds a thermodynamic ceiling
- optionally fall back to the legacy path for backward-compatible capped outputs until a hybrid vapour/aerosol model exists

## Code architecture

## 1. Recommended structure

### New solver module

`src/exposure_scenario_mcp/solvers/two_zone.py`

Responsibilities:

- 2x2 analytical propagation
- phase stitching for spray-on / spray-off
- mass-balance residual accounting
- deterministic fallback branch

### New thin plugin wrapper

`src/exposure_scenario_mcp/plugins/inhalation_two_zone.py`

Responsibilities:

- resolve defaults and profiles
- map request to solver inputs
- record assumptions/provenance/quality flags
- return `ExposureScenario`

### Existing compatibility façade

Keep `build_inhalation_tier_1_screening_scenario(...)`, but make it a router:

- `heuristic_v1`
- `two_zone_v1`
- `auto`

This preserves the current tool surface while enabling controlled migration.

## 2. Suggested request-model extension

```python
class InhalationTier1ScenarioRequest(ExposureScenarioRequest):
    solver_variant: Literal["auto", "heuristic_v1", "two_zone_v1"] = "auto"
    interzonal_flow_rate_m3_per_hour: float | None = None
    near_field_loss_rate_per_hour: float | None = None
    far_field_loss_rate_per_hour: float | None = None
    source_allocation_to_near_field_fraction: float | None = None
    ventilation_allocation_to_near_field_fraction: float | None = None
```

## 3. Suggested solver API

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class TwoZoneParams:
    v_nf_m3: float
    v_ff_m3: float
    beta_m3_per_hour: float
    lambda_nf_per_hour: float
    lambda_ff_per_hour: float
    source_fraction_to_nf: float = 1.0

@dataclass(frozen=True)
class TwoZoneState:
    c_nf_mg_per_m3: float = 0.0
    c_ff_mg_per_m3: float = 0.0

def solve_two_zone_piecewise_constant(
    *,
    params: TwoZoneParams,
    emission_rate_mg_per_hour: float,
    spray_duration_hours: float,
    total_duration_hours: float,
    initial_state: TwoZoneState = TwoZoneState(),
) -> dict[str, float]:
    ...
```

## 4. Core-body pseudocode

```python
def solve_two_zone_piecewise_constant(...):
    validate_inputs(...)

    # Build A matrix for both phases.
    a = params.beta_m3_per_hour / params.v_nf_m3 + params.lambda_nf_per_hour
    b = params.beta_m3_per_hour / params.v_nf_m3
    c = params.beta_m3_per_hour / params.v_ff_m3
    d = params.beta_m3_per_hour / params.v_ff_m3 + params.lambda_ff_per_hour
    A = ((-a, b), (c, -d))

    # On-phase source vector.
    u_on = (
        params.source_fraction_to_nf * emission_rate_mg_per_hour / params.v_nf_m3,
        (1.0 - params.source_fraction_to_nf) * emission_rate_mg_per_hour / params.v_ff_m3,
    )

    on = propagate_affine_phase(
        A=A,
        u=u_on,
        x0=(initial_state.c_nf_mg_per_m3, initial_state.c_ff_mg_per_m3),
        duration_hours=spray_duration_hours,
    )

    off = propagate_affine_phase(
        A=A,
        u=(0.0, 0.0),
        x0=on.end_state,
        duration_hours=total_duration_hours - spray_duration_hours,
    )

    c_nf_integral = on.integral[0] + off.integral[0]
    c_ff_integral = on.integral[1] + off.integral[1]

    c_nf_avg = c_nf_integral / total_duration_hours
    c_ff_avg = c_ff_integral / total_duration_hours

    # For zero initial concentrations and a positive constant source,
    # the phase-1 peak occurs at end-of-spray.
    c_nf_peak = on.end_state[0]
    c_ff_peak = on.end_state[1]

    return {
        "near_field_average_concentration_mg_per_m3": c_nf_avg,
        "far_field_average_concentration_mg_per_m3": c_ff_avg,
        "near_field_peak_concentration_mg_per_m3": c_nf_peak,
        "far_field_peak_concentration_mg_per_m3": c_ff_peak,
        "near_field_end_concentration_mg_per_m3": off.end_state[0],
        "far_field_end_concentration_mg_per_m3": off.end_state[1],
        "near_field_time_integral_mg_h_per_m3": c_nf_integral,
        "far_field_time_integral_mg_h_per_m3": c_ff_integral,
    }
```

## 5. AssumptionTracker / quality-flag updates

### New assumption records

- `interzonal_flow_rate_m3_per_hour`
- `room_ventilation_flow_rate_m3_per_hour`
- `near_field_loss_rate_per_hour`
- `far_field_loss_rate_per_hour`
- `source_fraction_to_near_field`
- `near_field_equivalent_radius_m`
- `near_field_free_surface_area_m2`
- `mass_balance_residual_mg`
- `ventilation_removed_mass_mg`
- `deposition_removed_mass_mg`

### New quality flags

- `two_zone_mass_balance_active`
- `two_zone_user_beta_override`
- `two_zone_source_outside_nf_volume`
- `two_zone_far_field_volume_small`
- `two_zone_degenerate_matrix_fallback`
- `two_zone_volatility_consistency_warning`
- `two_zone_legacy_fallback_applied`

## Validation and benchmark strategy

## 1. Published / external benchmarks

### Benchmark A — Classical constant-source NF/FF exact solution

Replicate the constant-source scenario with:

- `V_NF = 1 m3`
- `β = 11.5 m3/min`
- `V_room = 100 m3`
- `Q = 10 m3/min`
- `G = 1000 mg/min`

Expected exact forms:

```text
C_NF(t) = -101.8*exp(-0.10*t) - 85.2*exp(-11.62*t) + 187
C_FF(t) = -100.9*exp(-0.10*t) + 0.9*exp(-11.62*t) + 100
```

Validate at `t = 1, 5, 15, 60 min`.

### Benchmark B — Classical steady-state identity

For the classical NF-only source case:

- `C_FF,ss -> G/Q`
- `C_NF,ss - C_FF,ss -> G/β`

### Benchmark C — Single-zone convergence

As `β` becomes very large, the room-mass-weighted concentration should converge to the single-zone well-mixed solution with the same total room loss.

### Benchmark D — ConsExpo chamber-style product archetypes

Use at least three spray archetypes that differ in mass generation rate and airborne fraction, for example:

- insecticide / fly spray
- all-purpose cleaner
- deodorant or hair spray

Validate room-average or FF-average time courses and time integrals against published chamber data or digitized curves.

### Benchmark E — Internal dual-path harness

Run all existing internal benchmark scenarios under:

- `heuristic_v1`
- `two_zone_v1`

Classify each result:

- `migrate_now`
- `expected_divergence_requires_review`
- `legacy_lock`

## 2. Tolerance targets

### Exact analytic / algebraic checks

- relative error `<= 1e-6`

### Limit / convergence checks

- relative error `<= 1%`

### Experimental / literature calibration checks

- peak concentration within factor `<= 2`
- event-integrated concentration within `<= 25%` where numeric references exist
- otherwise document and review rather than silently tune

### Internal migration checks

- no benchmark case changes solver family without an explicit migration decision
- every changed case must store old output, new output, delta ratio, and scientific rationale

## 3. Metrics to validate

- `C_NF_peak`
- `C_NF_avg`
- `C_FF_peak`
- `C_FF_avg`
- end concentrations
- inhaled mass per event
- inhaled mass per day
- normalized external dose
- mass-balance residual

## Risk and caveat assessment

|Missing physics|Phase-1 handling|
|---|---|
|Droplet evaporation / vapour partitioning|Defer to future hybrid Tier 2 path; use volatility diagnostic and optional legacy fallback|
|Polydisperse particle-size evolution|Approximate only via current regime-specific defaults; no dynamic size evolution|
|Directional jet geometry / cone angle|Do not solve explicitly; approximate only through `β` defaults and future optional source-split parameter|
|Thermal plume / body wake / user movement|Approximate through retained entrainment floor|
|Surface sorption / re-emission|Ignore in active spray model; leave to dedicated residual-air reentry path|
|Regional lung deposition|Retain current swallowed-fraction screening logic; full deposition model deferred|
|Multi-room / door opening / HVAC short-circuiting|Out of scope for Tier 1 production path|

## Migration path

## 1. Keep the heuristic model

Yes. Keep `heuristic_v1` during migration.

## 2. Auto-selection logic

`solver_variant="auto"` should choose `two_zone_v1` only when all of the following are true:

1. Tier 1 spray scenario is otherwise valid.
2. Feature flag `tier1_two_zone_enabled` is on.
3. No volatility-cap fallback condition is triggered.
4. The matched product profile is marked `supports_two_zone`.
5. No migration lock exists for the benchmark family.

Otherwise, route to `heuristic_v1` and emit `two_zone_legacy_fallback_applied`.

## 3. Registry and docs changes

### `Tier1InhalationProfileRegistry`

Keep existing fields and add optional v2 fields:

- `supports_two_zone`
- `source_fraction_to_nf_default`
- `ventilation_fraction_to_nf_default`
- `nf_geometry_kind`
- `nf_free_surface_area_m2` or `nf_equivalent_radius_m`
- `two_zone_validation_status`
- `deposition_mapping_version`

### `docs://tier1-inhalation-parameter-guide`

Add:

- governing two-zone equations
- mapping from legacy heuristics to physical parameters
- retained vs deprecated fields
- benchmark summary and validation status
- solver family and algorithm IDs
- manifest version bump and hash

## Acceptance criteria

1. A valid current `InhalationTier1ScenarioRequest` produces a valid `ExposureScenario` through `two_zone_v1` without breaking the schema.
2. The solver reports NF and FF transient metrics, integrated concentration metrics, and a mass-balance residual.
3. The classical published benchmark is reproduced within `1e-6` relative error.
4. `heuristic_v1` remains available and selectable explicitly.
5. `auto` routing emits a clear provenance record of which solver was applied and why.
6. The parameter guide documents retained defaults, deprecated heuristics, and validation coverage.
7. All migrated benchmark cases have signed review notes.

## Sprint plan

## Sprint 1

- implement pure two-zone solver
- add solver tests and exact benchmark tests
- add mass-balance residual accounting

## Sprint 2

- integrate into Tier 1 builder behind `solverVariant`
- extend `AssumptionTracker`, `route_metrics`, and provenance
- update docs and profile manifest schema

## Sprint 3

- run dual-path benchmark harness
- classify and review benchmark cases
- enable `auto -> two_zone_v1` for approved product profiles

## Final recommendation

Implement the true two-zone model as a new deterministic solver core plus a thin routing façade, not as an in-place rewrite of the current heuristic concentration increment. Reuse the current profile pack and defaults where they naturally map to physical parameters, but remove the heuristic distance and persistence multipliers from the concentration equation itself. This yields a scientifically defensible, auditable, deterministic NF/FF model that can be adopted incrementally without breaking the MCP surface.
