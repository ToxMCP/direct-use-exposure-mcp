"""Deterministic analytical two-zone inhalation solver.

Implements the standard AIHA near-field/far-field mass-balance model as a
piecewise-constant-source affine 2x2 system.  The primary path is an exact
analytical solution; degenerate cases (beta -> 0, repeated eigenvalues,
singular A) are handled by closed-form branches rather than general
numerical integration.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class TwoZoneParams:
    """Physical parameters for the two-zone model."""

    v_nf_m3: float
    v_ff_m3: float
    beta_m3_per_hour: float
    lambda_nf_per_hour: float
    lambda_ff_per_hour: float
    source_fraction_to_nf: float = 1.0


@dataclass(frozen=True)
class TwoZoneState:
    """Concentration state vector."""

    c_nf_mg_per_m3: float = 0.0
    c_ff_mg_per_m3: float = 0.0


@dataclass(frozen=True)
class TwoZonePhaseResult:
    """Result of propagating one constant-source phase."""

    end_state: TwoZoneState
    c_nf_integral_mg_h_per_m3: float
    c_ff_integral_mg_h_per_m3: float


@dataclass(frozen=True)
class TwoZoneResult:
    """Full event result with on-phase + off-phase stitched together."""

    near_field_average_concentration_mg_per_m3: float
    far_field_average_concentration_mg_per_m3: float
    near_field_peak_concentration_mg_per_m3: float
    far_field_peak_concentration_mg_per_m3: float
    near_field_end_concentration_mg_per_m3: float
    far_field_end_concentration_mg_per_m3: float
    near_field_time_integral_mg_h_per_m3: float
    far_field_time_integral_mg_h_per_m3: float
    mass_balance_residual_mg: float


def _phi(r: float, t: float) -> float:
    """∫_0^t exp(r*s) ds = expm1(r*t) / r, with limit r->0 equal to t."""
    rt = r * t
    if abs(rt) < 1e-14:
        return t * (1.0 + rt * (0.5 + rt / 6.0))
    return math.expm1(rt) / r


def _psi(r: float, t: float) -> float:
    """∫_0^t s*exp(r*s) ds, with limit r->0 equal to t^2/2."""
    rt = r * t
    if abs(rt) < 1e-14:
        return t * t * 0.5 * (1.0 + rt * (2.0 / 3.0 + rt * 0.5))
    phi = math.expm1(rt) / r
    return (t * math.exp(rt) - phi) / r


def _chi(r: float, t: float) -> float:
    """∫_0^t ∫_0^s exp(r*τ) dτ ds = ∫_0^t phi(r,s) ds, limit r->0 = t^2/2."""
    rt = r * t
    if abs(rt) < 1e-14:
        return t * t * 0.5 * (1.0 + rt / 3.0 + rt * rt / 12.0)
    return (math.expm1(rt) - rt) / (r * r)


def _omega(r: float, t: float) -> float:
    """∫_0^t psi(r,s) ds, with limit r->0 equal to t^3/6."""
    rt = r * t
    if abs(rt) < 1e-14:
        return t * t * t / 6.0 * (1.0 + 0.5 * rt + rt * rt / 10.0)
    psi = _psi(r, t)
    chi = _chi(r, t)
    return (psi - chi) / r


def _mat_mul_2x2(
    A: tuple[float, float, float, float], v: tuple[float, float]
) -> tuple[float, float]:
    a11, a12, a21, a22 = A
    v1, v2 = v
    return (a11 * v1 + a12 * v2, a21 * v1 + a22 * v2)


def _build_A(params: TwoZoneParams) -> tuple[float, float, float, float]:
    """Build the 2x2 system matrix A = [[-a, b], [c, -d]]."""
    a = params.beta_m3_per_hour / params.v_nf_m3 + params.lambda_nf_per_hour
    b = params.beta_m3_per_hour / params.v_nf_m3
    c = params.beta_m3_per_hour / params.v_ff_m3
    d = params.beta_m3_per_hour / params.v_ff_m3 + params.lambda_ff_per_hour
    return (-a, b, c, -d)


def _build_source_vector(
    params: TwoZoneParams, emission_rate_mg_per_hour: float
) -> tuple[float, float]:
    u_n = params.source_fraction_to_nf * emission_rate_mg_per_hour / params.v_nf_m3
    u_f = (1.0 - params.source_fraction_to_nf) * emission_rate_mg_per_hour / params.v_ff_m3
    return (u_n, u_f)


def _affine_matrices_at_time(
    A: tuple[float, float, float, float],
    t: float,
) -> tuple[
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
]:
    """Compute M(t), I_mat(t), and J_mat(t) for the affine propagator.

    Returns the matrix exponential M = exp(A*t), its time integral I_mat,
    and the double time integral J_mat, using the same spectral branches as
    _propagate_affine_phase.
    """
    a11, a12, a21, a22 = A
    # Physical coefficients: a = -a11, d = -a22, b = a12, c = a21
    a_val = -a11
    d_val = -a22
    b_val = a12
    c_val = a21

    trace = a_val + d_val
    disc = (a_val - d_val) * (a_val - d_val) + 4.0 * b_val * c_val
    if disc < 0.0:
        disc = 0.0

    sqrt_disc = math.sqrt(disc)
    r_big = -0.5 * trace + 0.5 * sqrt_disc
    r_small = -0.5 * trace - 0.5 * sqrt_disc
    delta_r = r_big - r_small

    # Threshold for "repeated" eigenvalues relative to scale.
    if abs(delta_r) < 1e-12 * max(abs(r_big), abs(r_small), 1.0):
        # Repeated eigenvalue (Jordan form)
        r = r_big
        ert = math.exp(r * t)
        # M = exp(rt) * (I + (A - rI) * t)
        M = (
            ert * (1.0 + (a11 - r) * t),
            ert * a12 * t,
            ert * a21 * t,
            ert * (1.0 + (a22 - r) * t),
        )
        phi_rt = _phi(r, t)
        psi_rt = _psi(r, t)
        chi_rt = _chi(r, t)
        omega_rt = _omega(r, t)
        # I_mat = phi * I + psi * (A - rI)
        I_mat = (
            phi_rt + psi_rt * (a11 - r),
            psi_rt * a12,
            psi_rt * a21,
            phi_rt + psi_rt * (a22 - r),
        )
        # J_mat = chi * I + omega * (A - rI)
        J_mat = (
            chi_rt + omega_rt * (a11 - r),
            omega_rt * a12,
            omega_rt * a21,
            chi_rt + omega_rt * (a22 - r),
        )
    else:
        # Distinct eigenvalues — numerically stable spectral formulas.
        # Safe exp that returns 0.0 on underflow instead of raising.
        exp_big = math.exp(r_big * t) if r_big * t > -745 else 0.0
        exp_small = math.exp(r_small * t) if r_small * t > -745 else 0.0

        # M(t) using the stable identity:
        # exp(r_small*t) * expm1(delta_r*t) = exp(r_big*t) - exp(r_small*t)
        term = (exp_big - exp_small) / delta_r
        M = (
            term * (a11 - r_small) + exp_small,
            term * a12,
            term * a21,
            term * (a22 - r_small) + exp_small,
        )

        phi_big = _phi(r_big, t)
        phi_small = _phi(r_small, t)
        I_mat = (
            (phi_big * (a11 - r_small) - phi_small * (a11 - r_big)) / delta_r,
            (phi_big * a12 - phi_small * a12) / delta_r,
            (phi_big * a21 - phi_small * a21) / delta_r,
            (phi_big * (a22 - r_small) - phi_small * (a22 - r_big)) / delta_r,
        )

        chi_big = _chi(r_big, t)
        chi_small = _chi(r_small, t)
        J_mat = (
            (chi_big * (a11 - r_small) - chi_small * (a11 - r_big)) / delta_r,
            (chi_big * a12 - chi_small * a12) / delta_r,
            (chi_big * a21 - chi_small * a21) / delta_r,
            (chi_big * (a22 - r_small) - chi_small * (a22 - r_big)) / delta_r,
        )

    return M, I_mat, J_mat


def _state_at_time(
    A: tuple[float, float, float, float],
    u: tuple[float, float],
    x0: tuple[float, float],
    t: float,
) -> tuple[float, float]:
    """Evaluate x(t) for x' = A x + u using the exact spectral propagator."""
    M, I_mat, _ = _affine_matrices_at_time(A, t)
    x_t = _mat_mul_2x2(M, x0)
    i_u = _mat_mul_2x2(I_mat, u)
    return (x_t[0] + i_u[0], x_t[1] + i_u[1])


def _peak_in_phase(
    A: tuple[float, float, float, float],
    u: tuple[float, float],
    x0: tuple[float, float],
    duration_hours: float,
    compartment: int,
) -> float:
    """Find the maximum of one compartment over a constant-source phase.

    Because the trajectory is a sum of at most two exponentials, it is
    unimodal.  We evaluate the derivative at the boundaries; if it changes
    sign we bisect to the unique interior critical point and return the
    maximum over {start, end, interior}.
    """
    if duration_hours <= 0.0:
        return x0[compartment]

    x_end = _state_at_time(A, u, x0, duration_hours)

    def _deriv(t: float) -> tuple[float, float]:
        xt = _state_at_time(A, u, x0, t)
        dx0 = A[0] * xt[0] + A[1] * xt[1] + u[0]
        dx1 = A[2] * xt[0] + A[3] * xt[1] + u[1]
        return (dx0, dx1)

    d0 = _deriv(0.0)[compartment]
    d1 = _deriv(duration_hours)[compartment]

    peak = max(x0[compartment], x_end[compartment])

    # Opposite signs => exactly one interior extremum.
    if d0 * d1 < 0.0:
        lo, hi = 0.0, duration_hours
        for _ in range(60):
            mid = (lo + hi) * 0.5
            dm = _deriv(mid)[compartment]
            if d0 * dm <= 0.0:
                hi = mid
                d1 = dm
            else:
                lo = mid
                d0 = dm
        t_peak = (lo + hi) * 0.5
        x_peak = _state_at_time(A, u, x0, t_peak)[compartment]
        peak = max(peak, x_peak)

    return peak


def _propagate_affine_phase(
    A: tuple[float, float, float, float],
    u: tuple[float, float],
    x0: tuple[float, float],
    duration_hours: float,
) -> TwoZonePhaseResult:
    """Propagate x' = A x + u for a constant source over one phase.

    Uses the exact analytical solution expressed without A^{-1}:
        x(t)   = exp(A t) x0 + ∫_0^t exp(A s) u ds
        ∫_0^t x(s) ds = ∫_0^t exp(A s) x0 ds + ∫_0^t ∫_0^s exp(A τ) u dτ ds

    Both the state and its time integral are computed exactly via the matrix
    exponential (M), its time integral (I_mat), and the double time integral
    (J_mat).  This formulation remains valid even when A is singular.
    """
    if duration_hours <= 0.0:
        return TwoZonePhaseResult(
            end_state=TwoZoneState(c_nf_mg_per_m3=x0[0], c_ff_mg_per_m3=x0[1]),
            c_nf_integral_mg_h_per_m3=0.0,
            c_ff_integral_mg_h_per_m3=0.0,
        )

    M, I_mat, J_mat = _affine_matrices_at_time(A, duration_hours)

    # x(t) = M @ x0 + I_mat @ u
    x_t = _mat_mul_2x2(M, x0)
    i_u = _mat_mul_2x2(I_mat, u)
    x_t = (x_t[0] + i_u[0], x_t[1] + i_u[1])

    # ∫_0^t x(s) ds = I_mat @ x0 + J_mat @ u
    integral = _mat_mul_2x2(I_mat, x0)
    j_u = _mat_mul_2x2(J_mat, u)
    integral = (integral[0] + j_u[0], integral[1] + j_u[1])

    return TwoZonePhaseResult(
        end_state=TwoZoneState(c_nf_mg_per_m3=x_t[0], c_ff_mg_per_m3=x_t[1]),
        c_nf_integral_mg_h_per_m3=integral[0],
        c_ff_integral_mg_h_per_m3=integral[1],
    )


def solve_two_zone_piecewise_constant(
    *,
    params: TwoZoneParams,
    emission_rate_mg_per_hour: float,
    spray_duration_hours: float,
    total_duration_hours: float,
    initial_state: TwoZoneState | None = None,
    q_room_m3_per_hour: float | None = None,
    k_nf_per_hour: float | None = None,
    k_ff_per_hour: float | None = None,
    ventilation_allocation_to_near_field_fraction: float = 0.0,
) -> TwoZoneResult:
    """Solve the two-zone model for a single spray-on / spray-off event.

    Parameters
    ----------
    params
        Physical zone parameters.
    emission_rate_mg_per_hour
        Constant mass emission rate into air during the spray phase.
    spray_duration_hours
        Duration of the active spray phase (must be >= 0).
    total_duration_hours
        Total event duration including post-spray decay (must be >= spray_duration_hours).
    initial_state
        Initial concentrations at t=0.
    q_room_m3_per_hour
        Room ventilation exhaust flow, used only for the mass-balance residual check.
    k_nf_per_hour
        Near-field non-ventilation loss rate, used only for the mass-balance residual check.
    k_ff_per_hour
        Far-field non-ventilation loss rate, used only for the mass-balance residual check.
    ventilation_allocation_to_near_field_fraction
        Fraction of room ventilation directly assigned to the NF (phi), used only
        for the mass-balance residual check.

    Returns
    -------
    TwoZoneResult with average/peak/end concentrations, time integrals, and a
    mass-balance residual.  The residual is computed only when all optional
    loss/ventilation terms are supplied; otherwise it is set to ``NaN``.
    """
    if spray_duration_hours < 0.0:
        raise ValueError("spray_duration_hours must be non-negative")
    if total_duration_hours < spray_duration_hours:
        raise ValueError("total_duration_hours must be >= spray_duration_hours")
    if params.v_nf_m3 <= 0.0:
        raise ValueError("v_nf_m3 must be positive")
    if params.v_ff_m3 <= 0.0:
        raise ValueError("v_ff_m3 must be positive")
    if params.beta_m3_per_hour < 0.0:
        raise ValueError("beta_m3_per_hour must be non-negative")
    if not (0.0 <= params.source_fraction_to_nf <= 1.0):
        raise ValueError("source_fraction_to_nf must be between 0 and 1")
    if initial_state is None:
        initial_state = TwoZoneState()

    A = _build_A(params)
    u_on = _build_source_vector(params, emission_rate_mg_per_hour)
    x0 = (initial_state.c_nf_mg_per_m3, initial_state.c_ff_mg_per_m3)

    # Phase 1: source on
    on = _propagate_affine_phase(A, u_on, x0, spray_duration_hours)

    # Phase 2: source off
    off_duration = total_duration_hours - spray_duration_hours
    x_spray_end = (on.end_state.c_nf_mg_per_m3, on.end_state.c_ff_mg_per_m3)
    off = _propagate_affine_phase(A, (0.0, 0.0), x_spray_end, off_duration)

    c_nf_integral = on.c_nf_integral_mg_h_per_m3 + off.c_nf_integral_mg_h_per_m3
    c_ff_integral = on.c_ff_integral_mg_h_per_m3 + off.c_ff_integral_mg_h_per_m3

    c_nf_avg = c_nf_integral / total_duration_hours
    c_ff_avg = c_ff_integral / total_duration_hours

    # True compartment peaks: maximum over both phases, including any
    # post-spray rise in the far field caused by NF-to-FF mass transfer.
    c_nf_peak = max(
        _peak_in_phase(A, u_on, x0, spray_duration_hours, 0),
        _peak_in_phase(A, (0.0, 0.0), x_spray_end, off_duration, 0),
    )
    c_ff_peak = max(
        _peak_in_phase(A, u_on, x0, spray_duration_hours, 1),
        _peak_in_phase(A, (0.0, 0.0), x_spray_end, off_duration, 1),
    )

    # Mass-balance residual
    mass_balance_residual: float
    if q_room_m3_per_hour is not None and k_nf_per_hour is not None and k_ff_per_hour is not None:
        emitted_mass = emission_rate_mg_per_hour * spray_duration_hours
        final_mass = (
            params.v_nf_m3 * off.end_state.c_nf_mg_per_m3
            + params.v_ff_m3 * off.end_state.c_ff_mg_per_m3
        )
        initial_mass = params.v_nf_m3 * x0[0] + params.v_ff_m3 * x0[1]
        ventilation_removed = q_room_m3_per_hour * (
            ventilation_allocation_to_near_field_fraction * c_nf_integral
            + (1.0 - ventilation_allocation_to_near_field_fraction) * c_ff_integral
        )
        deposition_removed = (
            k_nf_per_hour * params.v_nf_m3 * c_nf_integral
            + k_ff_per_hour * params.v_ff_m3 * c_ff_integral
        )
        mass_balance_residual = (
            emitted_mass - (final_mass - initial_mass) - ventilation_removed - deposition_removed
        )
    else:
        mass_balance_residual = float("nan")

    return TwoZoneResult(
        near_field_average_concentration_mg_per_m3=c_nf_avg,
        far_field_average_concentration_mg_per_m3=c_ff_avg,
        near_field_peak_concentration_mg_per_m3=c_nf_peak,
        far_field_peak_concentration_mg_per_m3=c_ff_peak,
        near_field_end_concentration_mg_per_m3=off.end_state.c_nf_mg_per_m3,
        far_field_end_concentration_mg_per_m3=off.end_state.c_ff_mg_per_m3,
        near_field_time_integral_mg_h_per_m3=c_nf_integral,
        far_field_time_integral_mg_h_per_m3=c_ff_integral,
        mass_balance_residual_mg=mass_balance_residual,
    )
