"""Tests for the deterministic two-zone inhalation solver."""

from __future__ import annotations

import math

import pytest

from exposure_scenario_mcp.solvers.two_zone import (
    TwoZoneParams,
    TwoZoneState,
    _propagate_affine_phase,
    solve_two_zone_piecewise_constant,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rel_err(actual: float, expected: float) -> float:
    if expected == 0.0:
        return abs(actual)
    return abs(actual - expected) / abs(expected)


# ---------------------------------------------------------------------------
# Benchmark A — Classical constant-source exact solution
# ---------------------------------------------------------------------------
# Parameters from the PRD (values in minutes for the benchmark):
#   V_NF = 1 m3, beta = 11.5 m3/min, V_room = 100 m3 -> V_FF = 99 m3
#   Q = 10 m3/min, G = 1000 mg/min
# Expected forms (t in minutes):
#   C_NF(t) = -101.8*exp(-0.10*t) - 85.2*exp(-11.62*t) + 187
#   C_FF(t) = -100.9*exp(-0.10*t) + 0.9*exp(-11.62*t) + 100
# ---------------------------------------------------------------------------

BENCHMARK_A = TwoZoneParams(
    v_nf_m3=1.0,
    v_ff_m3=99.0,
    beta_m3_per_hour=11.5 * 60.0,  # 690 m3/h
    lambda_nf_per_hour=0.0,
    lambda_ff_per_hour=(10.0 * 60.0) / 99.0,  # Q/V_FF = 600/99 h-1
    source_fraction_to_nf=1.0,
)
BENCHMARK_A_EMISSION_RATE_MG_PER_HOUR = 1000.0 * 60.0  # 60000 mg/h


def _benchmark_a_expected(t_minutes: float) -> tuple[float, float]:
    c_nf = -101.8 * math.exp(-0.10 * t_minutes) - 85.2 * math.exp(-11.62 * t_minutes) + 187.0
    c_ff = -100.9 * math.exp(-0.10 * t_minutes) + 0.9 * math.exp(-11.62 * t_minutes) + 100.0
    return c_nf, c_ff


@pytest.mark.parametrize("t_minutes", [1, 5, 15, 60])
def test_benchmark_a_transient_concentrations(t_minutes: float) -> None:
    t_hours = t_minutes / 60.0
    result = _propagate_affine_phase(
        A=(-(BENCHMARK_A.beta_m3_per_hour / BENCHMARK_A.v_nf_m3 + BENCHMARK_A.lambda_nf_per_hour),
           BENCHMARK_A.beta_m3_per_hour / BENCHMARK_A.v_nf_m3,
           BENCHMARK_A.beta_m3_per_hour / BENCHMARK_A.v_ff_m3,
           -(BENCHMARK_A.beta_m3_per_hour / BENCHMARK_A.v_ff_m3 + BENCHMARK_A.lambda_ff_per_hour)),
        u=(BENCHMARK_A_EMISSION_RATE_MG_PER_HOUR / BENCHMARK_A.v_nf_m3, 0.0),
        x0=(0.0, 0.0),
        duration_hours=t_hours,
    )
    expected_nf, expected_ff = _benchmark_a_expected(t_minutes)
    # The benchmark coefficients in the PRD are rounded; tolerance reflects that.
    assert _rel_err(result.end_state.c_nf_mg_per_m3, expected_nf) <= 0.005
    assert _rel_err(result.end_state.c_ff_mg_per_m3, expected_ff) <= 0.005


# ---------------------------------------------------------------------------
# Benchmark B — Classical steady-state identity
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("g", [1000.0, 5000.0, 20000.0])
@pytest.mark.parametrize("q", [10.0, 50.0, 100.0])
@pytest.mark.parametrize("beta", [50.0, 100.0, 500.0])
def test_benchmark_b_steady_state_identity(g: float, q: float, beta: float) -> None:
    """For the classical NF-only source case with no NF-local loss:
    C_FF,ss -> G/Q  and  C_NF,ss - C_FF,ss -> G/beta
    """
    params = TwoZoneParams(
        v_nf_m3=1.0,
        v_ff_m3=50.0,
        beta_m3_per_hour=beta,
        lambda_nf_per_hour=0.0,
        lambda_ff_per_hour=q / 50.0,
        source_fraction_to_nf=1.0,
    )
    # Run a very long spray to reach steady state
    result = solve_two_zone_piecewise_constant(
        params=params,
        emission_rate_mg_per_hour=g,
        spray_duration_hours=100.0,  # long enough for steady state
        total_duration_hours=100.0,
        initial_state=TwoZoneState(),
    )
    # Steady-state identity applies to the end-of-phase concentration, not the time average.
    assert _rel_err(result.far_field_end_concentration_mg_per_m3, g / q) <= 1e-6
    assert _rel_err(
        result.near_field_end_concentration_mg_per_m3
        - result.far_field_end_concentration_mg_per_m3,
        g / beta,
    ) <= 1e-6


# ---------------------------------------------------------------------------
# Benchmark C — Single-zone convergence as beta -> large
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("t_hours", [0.5, 1.0, 2.0])
def test_benchmark_c_single_zone_convergence(t_hours: float) -> None:
    """As beta becomes very large, the room-mass-weighted concentration should
    converge to the single-zone well-mixed solution with the same total loss.
    """
    v_room = 30.0
    v_nf = 1.0
    v_ff = v_room - v_nf
    q = 60.0
    k = 0.5
    g = 1000.0
    lambda_total = k + q / v_room

    # Single-zone exact solution for constant source over [0, t]
    # C_ss = g / (q + k*v_room) = g / (lambda_total * v_room)
    c_ss_single = g / (lambda_total * v_room)
    # C(t) = C_ss * (1 - exp(-lambda * t))
    avg_single = c_ss_single * (
        1.0 - (1.0 - math.exp(-lambda_total * t_hours)) / (lambda_total * t_hours)
    )

    # Two-zone with very large beta
    params = TwoZoneParams(
        v_nf_m3=v_nf,
        v_ff_m3=v_ff,
        beta_m3_per_hour=1e6,  # very large interzonal mixing
        lambda_nf_per_hour=k,
        lambda_ff_per_hour=k + q / v_ff,
        source_fraction_to_nf=1.0,
    )
    result = solve_two_zone_piecewise_constant(
        params=params,
        emission_rate_mg_per_hour=g,
        spray_duration_hours=t_hours,
        total_duration_hours=t_hours,
    )
    # Mass-weighted average concentration
    c_weighted_avg = (
        v_nf * result.near_field_average_concentration_mg_per_m3
        + v_ff * result.far_field_average_concentration_mg_per_m3
    ) / v_room

    assert _rel_err(c_weighted_avg, avg_single) <= 0.01


# ---------------------------------------------------------------------------
# Mass balance residual
# ---------------------------------------------------------------------------

def test_mass_balance_residual_zero_losses() -> None:
    """With no losses, all emitted mass must remain in the room."""
    params = TwoZoneParams(
        v_nf_m3=1.0,
        v_ff_m3=9.0,
        beta_m3_per_hour=50.0,
        lambda_nf_per_hour=0.0,
        lambda_ff_per_hour=0.0,  # Q_room = 0, k_ff = 0
        source_fraction_to_nf=1.0,
    )
    g = 1000.0
    t_spray = 0.5
    t_total = 2.0
    result = solve_two_zone_piecewise_constant(
        params=params,
        emission_rate_mg_per_hour=g,
        spray_duration_hours=t_spray,
        total_duration_hours=t_total,
        q_room_m3_per_hour=0.0,
        k_nf_per_hour=0.0,
        k_ff_per_hour=0.0,
    )
    emitted = g * t_spray
    final_mass = (
        params.v_nf_m3 * result.near_field_end_concentration_mg_per_m3
        + params.v_ff_m3 * result.far_field_end_concentration_mg_per_m3
    )
    assert _rel_err(final_mass, emitted) <= 1e-9
    assert abs(result.mass_balance_residual_mg) <= 1e-9


def test_mass_balance_residual_with_ventilation_and_deposition() -> None:
    """Full mass balance with ventilation and deposition sinks."""
    v_nf = 1.0
    v_ff = 49.0
    q = 100.0
    k = 0.3
    lambda_ff = k + q / v_ff
    params = TwoZoneParams(
        v_nf_m3=v_nf,
        v_ff_m3=v_ff,
        beta_m3_per_hour=80.0,
        lambda_nf_per_hour=k,
        lambda_ff_per_hour=lambda_ff,
        source_fraction_to_nf=1.0,
    )
    g = 5000.0
    t_spray = 0.25
    t_total = 1.0
    result = solve_two_zone_piecewise_constant(
        params=params,
        emission_rate_mg_per_hour=g,
        spray_duration_hours=t_spray,
        total_duration_hours=t_total,
        q_room_m3_per_hour=q,
        k_nf_per_hour=k,
        k_ff_per_hour=k,
    )
    assert abs(result.mass_balance_residual_mg) <= 1e-6


# ---------------------------------------------------------------------------
# Beta -> 0 decoupled exact branch
# ---------------------------------------------------------------------------

def test_beta_zero_decoupled() -> None:
    """When beta is zero, NF and FF evolve independently."""
    params = TwoZoneParams(
        v_nf_m3=2.0,
        v_ff_m3=48.0,
        beta_m3_per_hour=0.0,
        lambda_nf_per_hour=1.0,
        lambda_ff_per_hour=2.0,
        source_fraction_to_nf=0.6,
    )
    g = 1200.0
    t_spray = 1.0
    t_total = 3.0
    result = solve_two_zone_piecewise_constant(
        params=params,
        emission_rate_mg_per_hour=g,
        spray_duration_hours=t_spray,
        total_duration_hours=t_total,
        q_room_m3_per_hour=96.0,  # arbitrary, not used in physics but needed for residual
        k_nf_per_hour=1.0,
        k_ff_per_hour=2.0,
    )
    # Independent scalar checks
    u_n = 0.6 * g / 2.0
    u_f = 0.4 * g / 48.0
    c_ss_n = u_n / 1.0
    c_ss_f = u_f / 2.0

    # After spray phase
    c_nf_spray = c_ss_n * (1.0 - math.exp(-1.0 * t_spray))
    c_ff_spray = c_ss_f * (1.0 - math.exp(-2.0 * t_spray))
    int_nf_spray = c_ss_n * t_spray + (0.0 - c_ss_n) * math.expm1(-1.0 * t_spray) / (-1.0)
    int_ff_spray = c_ss_f * t_spray + (0.0 - c_ss_f) * math.expm1(-2.0 * t_spray) / (-2.0)

    # Decay phase
    t_decay = t_total - t_spray
    c_nf_end = c_nf_spray * math.exp(-1.0 * t_decay)
    c_ff_end = c_ff_spray * math.exp(-2.0 * t_decay)
    int_nf_decay = c_nf_spray * (1.0 - math.exp(-1.0 * t_decay)) / 1.0
    int_ff_decay = c_ff_spray * (1.0 - math.exp(-2.0 * t_decay)) / 2.0

    assert math.isclose(result.near_field_peak_concentration_mg_per_m3, c_nf_spray, rel_tol=1e-9)
    assert math.isclose(result.far_field_peak_concentration_mg_per_m3, c_ff_spray, rel_tol=1e-9)
    assert math.isclose(
        result.near_field_end_concentration_mg_per_m3, c_nf_end, rel_tol=1e-9
    )
    assert math.isclose(
        result.far_field_end_concentration_mg_per_m3, c_ff_end, rel_tol=1e-9
    )
    assert math.isclose(
        result.near_field_time_integral_mg_h_per_m3,
        int_nf_spray + int_nf_decay,
        rel_tol=1e-9,
    )
    assert math.isclose(
        result.far_field_time_integral_mg_h_per_m3,
        int_ff_spray + int_ff_decay,
        rel_tol=1e-9,
    )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_zero_source_zero_duration() -> None:
    result = solve_two_zone_piecewise_constant(
        params=TwoZoneParams(
            v_nf_m3=1.0, v_ff_m3=9.0, beta_m3_per_hour=50.0,
            lambda_nf_per_hour=0.5, lambda_ff_per_hour=1.0,
        ),
        emission_rate_mg_per_hour=0.0,
        spray_duration_hours=0.0,
        total_duration_hours=1.0,
    )
    assert result.near_field_end_concentration_mg_per_m3 == 0.0
    assert result.far_field_end_concentration_mg_per_m3 == 0.0
    assert result.near_field_time_integral_mg_h_per_m3 == 0.0
    assert result.far_field_time_integral_mg_h_per_m3 == 0.0


def test_nonzero_initial_state() -> None:
    """If initial concentration exceeds new steady state and zones are decoupled,
    peak should be the initial concentration."""
    params = TwoZoneParams(
        v_nf_m3=1.0,
        v_ff_m3=9.0,
        beta_m3_per_hour=0.0,  # decoupled so each compartment decays monotonically
        lambda_nf_per_hour=1.0,
        lambda_ff_per_hour=1.0,
        source_fraction_to_nf=1.0,
    )
    # Low emission rate -> steady state is well below initial concentrations
    result = solve_two_zone_piecewise_constant(
        params=params,
        emission_rate_mg_per_hour=10.0,
        spray_duration_hours=1.0,
        total_duration_hours=1.0,
        initial_state=TwoZoneState(c_nf_mg_per_m3=100.0, c_ff_mg_per_m3=50.0),
    )
    assert result.near_field_peak_concentration_mg_per_m3 == 100.0
    assert result.far_field_peak_concentration_mg_per_m3 == 50.0


def test_validation_errors() -> None:
    with pytest.raises(ValueError, match="spray_duration_hours must be non-negative"):
        solve_two_zone_piecewise_constant(
            params=TwoZoneParams(
                v_nf_m3=1.0, v_ff_m3=9.0, beta_m3_per_hour=50.0,
                lambda_nf_per_hour=0.5, lambda_ff_per_hour=1.0,
            ),
            emission_rate_mg_per_hour=100.0,
            spray_duration_hours=-1.0,
            total_duration_hours=1.0,
        )
    with pytest.raises(ValueError, match="total_duration_hours must be >= spray_duration_hours"):
        solve_two_zone_piecewise_constant(
            params=TwoZoneParams(
                v_nf_m3=1.0, v_ff_m3=9.0, beta_m3_per_hour=50.0,
                lambda_nf_per_hour=0.5, lambda_ff_per_hour=1.0,
            ),
            emission_rate_mg_per_hour=100.0,
            spray_duration_hours=2.0,
            total_duration_hours=1.0,
        )


# ---------------------------------------------------------------------------
# Time-integral exactness via algebraic identity
# ---------------------------------------------------------------------------

def test_integral_exactness_against_numeric_quadrature() -> None:
    """Compare the analytical time integral to a simple deterministic quadrature."""
    params = TwoZoneParams(
        v_nf_m3=1.5,
        v_ff_m3=28.5,
        beta_m3_per_hour=120.0,
        lambda_nf_per_hour=0.3,
        lambda_ff_per_hour=0.8,
        source_fraction_to_nf=1.0,
    )
    g = 3000.0
    t_spray = 0.5
    t_total = 2.0

    result = solve_two_zone_piecewise_constant(
        params=params,
        emission_rate_mg_per_hour=g,
        spray_duration_hours=t_spray,
        total_duration_hours=t_total,
    )

    # Deterministic fixed-step quadrature (trapezoid, 10000 steps)
    n_steps = 10000
    dt = t_total / n_steps
    a11, a12, a21, a22 = (
        -(params.beta_m3_per_hour / params.v_nf_m3 + params.lambda_nf_per_hour),
        params.beta_m3_per_hour / params.v_nf_m3,
        params.beta_m3_per_hour / params.v_ff_m3,
        -(params.beta_m3_per_hour / params.v_ff_m3 + params.lambda_ff_per_hour),
    )
    u = (g / params.v_nf_m3, 0.0)
    c_nf = 0.0
    c_ff = 0.0
    sum_nf = 0.0
    sum_ff = 0.0
    for i in range(n_steps + 1):
        t = i * dt
        weight = 0.5 if i == 0 or i == n_steps else 1.0
        sum_nf += weight * c_nf
        sum_ff += weight * c_ff
        # Euler step for next concentration
        du = u if t < t_spray else (0.0, 0.0)
        c_nf_next = c_nf + (a11 * c_nf + a12 * c_ff + du[0]) * dt
        c_ff_next = c_ff + (a21 * c_nf + a22 * c_ff + du[1]) * dt
        c_nf, c_ff = c_nf_next, c_ff_next

    numeric_int_nf = sum_nf * dt
    numeric_int_ff = sum_ff * dt

    assert _rel_err(result.near_field_time_integral_mg_h_per_m3, numeric_int_nf) <= 1e-4
    assert _rel_err(result.far_field_time_integral_mg_h_per_m3, numeric_int_ff) <= 1e-4


def test_mass_balance_residual_with_phi() -> None:
    """Residual must remain exact when ventilation is split between zones."""
    v_nf = 1.0
    v_ff = 49.0
    q = 100.0
    k = 0.3
    phi = 0.25
    lambda_nf = k + phi * q / v_nf
    lambda_ff = k + (1.0 - phi) * q / v_ff
    params = TwoZoneParams(
        v_nf_m3=v_nf,
        v_ff_m3=v_ff,
        beta_m3_per_hour=80.0,
        lambda_nf_per_hour=lambda_nf,
        lambda_ff_per_hour=lambda_ff,
        source_fraction_to_nf=1.0,
    )
    result = solve_two_zone_piecewise_constant(
        params=params,
        emission_rate_mg_per_hour=5000.0,
        spray_duration_hours=0.25,
        total_duration_hours=1.0,
        q_room_m3_per_hour=q,
        k_nf_per_hour=k,
        k_ff_per_hour=k,
        ventilation_allocation_to_near_field_fraction=phi,
    )
    assert abs(result.mass_balance_residual_mg) <= 1e-6


def test_delayed_far_field_peak_after_spray_ends() -> None:
    """Far-field concentration can peak after the spray stops because NF mass
    keeps transferring inward.  The old end-of-spray logic misses this peak.
    """
    params = TwoZoneParams(
        v_nf_m3=1.0,
        v_ff_m3=9.0,
        beta_m3_per_hour=50.0,
        lambda_nf_per_hour=1.0,
        lambda_ff_per_hour=1.0,
        source_fraction_to_nf=1.0,
    )
    result = solve_two_zone_piecewise_constant(
        params=params,
        emission_rate_mg_per_hour=1000.0,
        spray_duration_hours=0.1,
        total_duration_hours=2.0,
    )
    # The spray-on end-state FF concentration is lower than the true FF peak
    # because FF continues to rise during the early decay phase.
    assert (
        result.far_field_peak_concentration_mg_per_m3
        > result.far_field_end_concentration_mg_per_m3
    )
    # And the peak is strictly later than the spray end.
    # We verify by sampling that the maximum is not at t=spray_duration.
    from exposure_scenario_mcp.solvers.two_zone import _build_A, _state_at_time

    A = _build_A(params)
    u_on = (1000.0 / 1.0, 0.0)
    x0 = (0.0, 0.0)
    spray_end = _state_at_time(A, u_on, x0, 0.1)
    assert result.far_field_peak_concentration_mg_per_m3 > spray_end[1]
