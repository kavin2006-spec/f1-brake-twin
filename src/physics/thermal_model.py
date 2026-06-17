"""
thermal_model.py — Lumped-capacity thermal model for a single front brake disc.

Phase 1a assumptions (per docs/02_parameter_derivation.md):
- Disc treated as one uniform-temperature thermal mass (lumped)
- Three heat fluxes: braking input, convection, radiation
- Convection uses lumped conductance h_eff(v) = H_EFF_0 × (v/V_REF)^N_VEL
- Radiation uses geometric disc area (vent holes don't help radiation)
- Integration: forward Euler at the telemetry sampling rate
- Heat input during a braking event is distributed uniformly over the event
  (matches the event-level energy balance from energy_balance.py)

All temperatures are in KELVIN inside this module. Convert at the boundary
if the caller works in Celsius.
"""

import numpy as np
from src.utils import constants as C


# ─────────────────────────────────────────────────────────────────────
# Heat flux components (per disc)
# ─────────────────────────────────────────────────────────────────────

def h_eff(v_ms: float) -> float:
    """
    Lumped convective conductance as a function of car speed.

    h_eff(v) = H_EFF_0 × (v / V_REF)^N_VEL

    Units: W/K (this already includes effective cooling area; see param doc).
    """
    # Guard against negative/zero speeds (numerical safety)
    v = max(v_ms, 0.0)
    return C.H_EFF_0 * (v / C.V_REF) ** C.N_VEL


def convective_loss(T_disc_K: float, T_amb_K: float, v_ms: float) -> float:
    """
    Convective heat loss rate per disc, in W. Always non-negative when
    T_disc > T_amb (i.e., disc cools, doesn't gain heat from the airflow).
    """
    return h_eff(v_ms) * (T_disc_K - T_amb_K)


def radiative_loss(T_disc_K: float, T_amb_K: float) -> float:
    """
    Radiative heat loss rate per disc, in W.

    Q_rad = ε × σ × A_geometric × (T_disc⁴ - T_amb⁴)

    Note we use A_geometric (the actual disc surface) rather than the
    cooling-enhanced area. Vent holes don't contribute much to radiation
    because they largely radiate into themselves.

    The T⁴ dependence means radiation is small at room temperature but
    significant above ~600°C.
    """
    return (C.EPSILON_DISC * C.SIGMA_SB * C.A_DISC_GEOMETRIC
            * (T_disc_K**4 - T_amb_K**4))


def dT_dt(T_disc_K: float, T_amb_K: float, v_ms: float, P_in_W: float) -> float:
    """
    Right-hand side of the thermal ODE.

    m × c_p × dT/dt = P_in - Q_conv - Q_rad

    Returns dT/dt in K/s.
    """
    P_conv = convective_loss(T_disc_K, T_amb_K, v_ms)
    P_rad = radiative_loss(T_disc_K, T_amb_K)
    return (P_in_W - P_conv - P_rad) / (C.M_DISC * C.CP_CC)


# ─────────────────────────────────────────────────────────────────────
# Heat input construction from event decomposition
# ─────────────────────────────────────────────────────────────────────

def build_input_power_per_disc(t_s: np.ndarray, events: list) -> np.ndarray:
    """
    Construct a per-disc heat input power array (W) over a lap.

    For each braking event, the total front-axle brake energy is split
    50/50 between left and right discs, then distributed uniformly across
    the event duration (matching the event-level energy balance).

    Parameters
    ----------
    t_s : timestamps in seconds (the same time grid the model integrates on)
    events : list of dicts, each with:
        'start_idx' : int, index in t_s where the event starts
        'end_idx'   : int, index in t_s where the event ends (inclusive)
        'E_brake_front_J' : float, front-axle brake energy in Joules

    Returns
    -------
    Array of input power per disc (W), same length as t_s. Zero outside events.
    """
    P_in = np.zeros(len(t_s))
    for ev in events:
        E_per_disc = ev['E_brake_front_J'] / 2.0
        s, e = ev['start_idx'], ev['end_idx']
        duration = t_s[e] - t_s[s]
        if duration > 0:
            # Convention: P_in[i] is the power level held during the interval
            # [t[i], t[i+1]]. A brake-on period covering samples [s, e] inclusive
            # therefore corresponds to intervals starting at indices s..e-1,
            # totaling (e-s) intervals of combined duration t[e]-t[s].
            # This makes forward Euler and trapezoidal integration both exact.
            P_in[s:e] = E_per_disc / duration
    return P_in


# ─────────────────────────────────────────────────────────────────────
# Integrator
# ─────────────────────────────────────────────────────────────────────

def integrate_lap(t_s: np.ndarray, v_ms: np.ndarray,
                   P_in_W: np.ndarray,
                   T_amb_K: float, T_init_K: float) -> np.ndarray:
    """
    Forward-Euler integration of the thermal ODE over a lap.

    Parameters
    ----------
    t_s : timestamps in seconds, monotonically increasing
    v_ms : car speed at each timestamp, m/s
    P_in_W : input power per disc at each timestamp, W
    T_amb_K : ambient temperature in K (constant across the lap)
    T_init_K : initial disc temperature in K

    Returns
    -------
    Array of disc temperatures in K, same length as t_s.

    Notes
    -----
    Forward Euler is stable here because the thermal time constant
    (m × c_p / h_eff ≈ 36 s) is much greater than the sample interval
    (~0.13 s). For 2-3% accuracy that's adequate. If we ever need better,
    swap in scipy.integrate.solve_ivp with the same RHS.
    """
    n = len(t_s)
    T = np.empty(n)
    T[0] = T_init_K

    for i in range(1, n):
        dt = t_s[i] - t_s[i - 1]
        # Evaluate RHS using previous-step values (forward Euler)
        rhs = dT_dt(T[i - 1], T_amb_K, v_ms[i - 1], P_in_W[i - 1])
        T[i] = T[i - 1] + rhs * dt

    return T

"""
Temperatures in Kelvin internally. Radiation requires absolute temperature, and mixing K and °C in the same module is a classic source of bugs. We convert at the boundary in the notebook.
The max(v_ms, 0.0) guard. Speed should never be negative, but if for any reason a sample comes through as a small negative number (interpolation artifact, say), (v/V_REF)^0.7 becomes complex-valued in numpy. The guard prevents that.
build_input_power_per_disc is separate from the integrator. Two reasons. First, you might later want to test different power-distribution strategies (e.g. proportional to instantaneous deceleration instead of uniform), and a separate function makes that swap trivial. Second, the integrator stays pure: it just takes arrays. Easier to test, easier to reuse.
Forward Euler choice. I could have used scipy.integrate.solve_ivp with adaptive stepping. For Phase 1a it's overkill — the thermal dynamics aren't stiff and our time resolution is fixed by the telemetry rate anyway. The docstring notes how to swap if we ever need to.
"""