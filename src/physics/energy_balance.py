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
# ─────────────────────────────────────────────────────────────────────
# Sample-level (instantaneous) power functions
# 
# Phase 1b chunk 2 addition. These compute the instantaneous power at each
# telemetry sample, returning arrays parallel to the input speed array.
# Required for the rear-axle regen model, which applies the MGU-K power
# cap continuously rather than at event level.
#
# Phase 1a's event-level integrators (drag_energy, rolling_resistance_energy,
# engine_braking_energy, decompose_braking_event) are unchanged — these new
# functions are additive only.
# ─────────────────────────────────────────────────────────────────────

def drag_power_instantaneous(v_ms: np.ndarray, rho_air: float,
                              Cd: float = C.CD,
                              A_f: float = C.A_F) -> np.ndarray:
    """
    Instantaneous power dissipated by aerodynamic drag at each sample.

        P_drag(t) = 0.5 × ρ × Cd × A_f × v(t)³

    Returns
    -------
    Array of power values in W, same shape as v_ms.
    """
    return 0.5 * rho_air * Cd * A_f * v_ms**3


def rolling_resistance_power_instantaneous(v_ms: np.ndarray,
                                            mass: float = C.M_CAR,
                                            Crr: float = C.CRR,
                                            g: float = C.G) -> np.ndarray:
    """
    Instantaneous power dissipated by rolling resistance.

        P_roll(t) = Crr × m × g × v(t)
    """
    return Crr * mass * g * v_ms


def engine_braking_power_instantaneous(v_ms: np.ndarray,
                                        mass: float = C.M_CAR,
                                        a_eng: float = C.A_ENG) -> np.ndarray:
    """
    Instantaneous power dissipated by engine braking.

        P_eng(t) = m × a_eng × v(t)

    Phase 1a treats a_eng as a constant equivalent deceleration applied
    whenever the car is braking. Per the chunk 2 scope decision, engine
    braking energy is dissipated in the engine and never reaches the
    brake discs — so this term enters the brake-power calculation as
    a subtraction from total kinetic loss, identical to Phase 1a.
    """
    return mass * a_eng * v_ms


def kinetic_power_loss_instantaneous(v_ms: np.ndarray, t_s: np.ndarray,
                                       mass: float = C.M_CAR) -> np.ndarray:
    """
    Instantaneous rate of kinetic energy loss.

        P_kin(t) = -d/dt [0.5 × m × v(t)²] = -m × v(t) × a(t)

    Computed via centered finite differences on speed. Positive when the
    car is decelerating (losing kinetic energy). Same length as v_ms.

    Note: returns 0 at samples where the car is accelerating (kinetic
    energy is increasing, not being lost). The brake-power computation
    downstream only cares about the loss case.
    """
    if len(v_ms) < 2:
        return np.zeros_like(v_ms)

    # Centered differences in the interior, forward/backward at the ends
    dv_dt = np.gradient(v_ms, t_s)
    # Deceleration is -dv/dt (positive when slowing down)
    decel = -dv_dt
    # Instantaneous kinetic power loss
    P_kin_loss = mass * v_ms * decel
    # Clip to zero where the car is actually accelerating
    return np.maximum(P_kin_loss, 0.0)


def brake_power_instantaneous(v_ms: np.ndarray, t_s: np.ndarray,
                                rho_air: float,
                                brake_bool: np.ndarray = None,
                                mass: float = C.M_CAR) -> np.ndarray:
    """
    Total instantaneous brake power (front + rear, friction only).

        P_brake_total(t) = P_kin_loss(t) - P_drag(t) - P_roll(t) - P_eng(t)

    Engine braking is subtracted here because it dissipates in the engine,
    not at the brake discs. This is the total power being absorbed by
    both axles' brakes combined. Apply BETA_FRONT or BETA_REAR downstream
    to get per-axle power.

    Parameters
    ----------
    v_ms, t_s : speed (m/s) and time (s) arrays
    rho_air : air density (kg/m³)
    brake_bool : optional boolean array of brake state. If provided,
                 P_brake is forced to zero where brake_bool is False
                 (suppresses spurious "brake" power during coast).
    mass : vehicle mass (kg)

    Returns
    -------
    Array of brake power (W), same shape as v_ms. Clipped to non-negative.
    """
    P_kin = kinetic_power_loss_instantaneous(v_ms, t_s, mass=mass)
    P_drag = drag_power_instantaneous(v_ms, rho_air)
    P_roll = rolling_resistance_power_instantaneous(v_ms, mass=mass)

    # Engine braking only applies when off-throttle. Phase 1a treats it
    # as always-on during braking events (where throttle is at 0).
    # Sample-level: apply only when brake is on (proxy for off-throttle).
    if brake_bool is not None:
        P_eng = engine_braking_power_instantaneous(v_ms, mass=mass) * brake_bool.astype(float)
    else:
        P_eng = engine_braking_power_instantaneous(v_ms, mass=mass)

    P_brake = P_kin - P_drag - P_roll - P_eng
    P_brake = np.maximum(P_brake, 0.0)  # Can't have negative brake power

    # If brake_bool provided, force brake power to zero where brake is off
    if brake_bool is not None:
        P_brake = P_brake * brake_bool.astype(float)

    return P_brake
"""
Why I used np.trapezoid — it's numerical integration using the trapezoidal rule. Given (t, v) samples, np.trapezoid(v, t) computes ∫v dt by treating each pair of consecutive samples as a trapezoid. With our 7.5 Hz data, this is adequate accuracy for energy calculations. (Older NumPy uses np.trapz — same thing.)
Why drag is v³ and rolling is v¹ — drag force itself is 0.5·ρ·Cd·A·v², and power = force × velocity gives v³. Rolling resistance force is constant (Crr·m·g), so power = force × velocity is linear in v. This is why drag dominates at high speed and rolling dominates at low speed.
Engine braking as work = force × distance — ∫v dt is literally the distance traveled. So engine braking energy is just (constant force) × (distance), the cleanest possible calculation.
The remainder approach — we don't model brake friction directly. We compute everything else and call whatever's left "brake energy." This is valid because we have hard ground truth on ΔKE (from speed measurements) and we have decent confidence in the other three terms. The error in the remainder is the sum of errors in the other three, which is fine for Phase 1a.
"""

"""
np.gradient for the speed derivative. This uses centered differences in the interior of the array and one-sided differences at the endpoints. For our 7.5 Hz data, it's adequate. At higher rates we'd consider smoothing first because raw finite differences amplify noise — but FastF1's resampling already smooths the speed signal somewhat.
The np.maximum(..., 0.0) clipping is essential. Without it, brake power could be slightly negative due to either (a) numerical noise in the derivative, or (b) genuinely small accelerations during what we've called a braking event (e.g., very brief throttle blips). Clipping to zero is honest: you can't have negative friction braking. The very small clipping events are below the noise floor of everything else.
The brake_bool argument is optional but recommended. Without it, the function will compute "brake power" even during coast phases where the driver has lifted but isn't braking. The car is still decelerating from drag + rolling + engine braking, and the kinetic loss exceeds those terms by a small amount due to gradient noise — producing spurious tiny brake powers. Passing brake_bool from FastF1 zeroes these out cleanly.
"""
