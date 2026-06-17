"""
energy_balance.py — Per-event energy decomposition for braking events.

For each braking event we have a time series of speed v(t). The car's
kinetic energy decreases over the event. That energy is dissipated through:

    ΔKE = E_drag + E_roll + E_eng + E_brake_total

We compute the first three from physics, then take E_brake_total as the
remainder. The front-axle share is then E_brake_front = β_front × E_brake_total.

This is the Phase 1a energy balance. Engine braking is constant; brake bias
is constant; aero is single-Cd. All assumptions are documented in
docs/02_parameter_derivation.md.
"""

import numpy as np
from src.utils import constants as C


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def air_density(T_celsius: float, P_pa: float = C.P_ATM) -> float:
    """
    Compute air density from temperature and pressure using the ideal gas law.

    ρ = P / (R_specific × T)

    Parameters
    ----------
    T_celsius : air temperature in degrees Celsius (from FastF1 weather)
    P_pa : ambient pressure in Pa, default sea-level standard

    Returns
    -------
    Air density in kg/m³
    """
    T_kelvin = T_celsius + 273.15
    return P_pa / (C.R_AIR * T_kelvin)


# ─────────────────────────────────────────────────────────────────────
# Individual dissipation terms
# ─────────────────────────────────────────────────────────────────────

def drag_energy(v_ms: np.ndarray, t_s: np.ndarray, rho_air: float,
                Cd: float = C.CD, A_f: float = C.A_F) -> float:
    """
    Energy dissipated by aerodynamic drag over a time window.

    Instantaneous power dissipated by drag:
        P_drag(t) = 0.5 × ρ × Cd × A_f × v(t)³

    Total energy:
        E_drag = ∫ P_drag(t) dt

    Note the v³ dependence — drag energy is very speed-sensitive.
    Most drag dissipation happens early in a braking event when v is high.
    """
    P_drag = 0.5 * rho_air * Cd * A_f * v_ms**3
    return np.trapezoid(P_drag, t_s)


def rolling_resistance_energy(v_ms: np.ndarray, t_s: np.ndarray,
                               mass: float = C.M_CAR,
                               Crr: float = C.CRR, g: float = C.G) -> float:
    """
    Energy dissipated by rolling resistance over a time window.

    Rolling resistance force is constant (independent of speed):
        F_roll = Crr × m × g

    Instantaneous power:
        P_roll(t) = F_roll × v(t)

    Linear in v, so rolling dissipation is more uniformly distributed
    across a braking event than drag.
    """
    F_roll = Crr * mass * g
    P_roll = F_roll * v_ms
    return np.trapezoid(P_roll, t_s)


def engine_braking_energy(v_ms: np.ndarray, t_s: np.ndarray,
                           mass: float = C.M_CAR,
                           a_eng: float = C.A_ENG) -> float:
    """
    Energy dissipated by engine braking over a time window.

    Phase 1a approximation: engine braking produces a constant
    equivalent deceleration a_eng when the throttle is off (which is
    always the case during a braking event).

        F_eng = m × a_eng
        P_eng(t) = F_eng × v(t)
        E_eng = ∫ P_eng dt = m × a_eng × ∫ v dt

    ∫ v dt = distance covered. So engine braking energy = force × distance,
    which is the cleanest possible work calculation.
    """
    F_eng = mass * a_eng
    P_eng = F_eng * v_ms
    return np.trapezoid(P_eng, t_s)


# ─────────────────────────────────────────────────────────────────────
# Full per-event decomposition
# ─────────────────────────────────────────────────────────────────────

def decompose_braking_event(v_ms: np.ndarray, t_s: np.ndarray,
                             rho_air: float,
                             mass: float = C.M_CAR,
                             beta_front: float = C.BETA_FRONT) -> dict:
    """
    Decompose a braking event's kinetic energy change into dissipation paths.

    Parameters
    ----------
    v_ms : speed in m/s, sampled at times t_s
    t_s : time stamps in seconds, monotonically increasing
    rho_air : air density (compute from weather using air_density())
    mass : vehicle mass in kg
    beta_front : brake bias to the front axle (0..1)

    Returns
    -------
    Dict with all energy terms in Joules and their fractional shares of ΔKE.
    """
    # Total kinetic energy lost during the event
    delta_KE = 0.5 * mass * (v_ms[0]**2 - v_ms[-1]**2)

    # Each non-brake dissipation term (computed from physics)
    E_drag = drag_energy(v_ms, t_s, rho_air)
    E_roll = rolling_resistance_energy(v_ms, t_s, mass=mass)
    E_eng = engine_braking_energy(v_ms, t_s, mass=mass)

    # What's left went into the brakes (front + rear total)
    E_brake_total = delta_KE - E_drag - E_roll - E_eng

    # Front-axle share
    E_brake_front = beta_front * E_brake_total

    return {
        # Energies in Joules
        'delta_KE_J': delta_KE,
        'E_drag_J': E_drag,
        'E_roll_J': E_roll,
        'E_eng_J': E_eng,
        'E_brake_total_J': E_brake_total,
        'E_brake_front_J': E_brake_front,
        # Fractional shares of ΔKE (should sum to 1 across drag/roll/eng/brake)
        'frac_drag': E_drag / delta_KE if delta_KE > 0 else 0.0,
        'frac_roll': E_roll / delta_KE if delta_KE > 0 else 0.0,
        'frac_eng': E_eng / delta_KE if delta_KE > 0 else 0.0,
        'frac_brake_total': E_brake_total / delta_KE if delta_KE > 0 else 0.0,
    }

"""
Why I used np.trapezoid — it's numerical integration using the trapezoidal rule. Given (t, v) samples, np.trapezoid(v, t) computes ∫v dt by treating each pair of consecutive samples as a trapezoid. With our 7.5 Hz data, this is adequate accuracy for energy calculations. (Older NumPy uses np.trapz — same thing.)
Why drag is v³ and rolling is v¹ — drag force itself is 0.5·ρ·Cd·A·v², and power = force × velocity gives v³. Rolling resistance force is constant (Crr·m·g), so power = force × velocity is linear in v. This is why drag dominates at high speed and rolling dominates at low speed.
Engine braking as work = force × distance — ∫v dt is literally the distance traveled. So engine braking energy is just (constant force) × (distance), the cleanest possible calculation.
The remainder approach — we don't model brake friction directly. We compute everything else and call whatever's left "brake energy." This is valid because we have hard ground truth on ΔKE (from speed measurements) and we have decent confidence in the other three terms. The error in the remainder is the sum of errors in the other three, which is fine for Phase 1a.
"""
