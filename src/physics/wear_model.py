"""
wear_model.py — Disc wear estimation from temperature and braking power.

Phase 1a assumptions (per docs/02_parameter_derivation.md §5.5):
- Two wear mechanisms: mechanical (energy-proportional) + oxidative (Arrhenius)
- Total wear rate: dW/dt = k_mech × P_brake + k_ox_0 × exp(-E_a / (R × T))
- W is in kg (mass lost from one disc); convert to thickness via density × area
- Both coefficients are L-confidence — absolute values are calibration targets,
  relative comparisons (track-to-track, driver-to-driver) are defensible.

Wear is integrated alongside (not coupled into) the thermal model: T_disc drives
wear, but wear does not feed back into T_disc within a single lap. (Over many
laps, mass loss would reduce thermal capacity — Phase 1b concern.)
"""

import numpy as np
from src.utils import constants as C


# ─────────────────────────────────────────────────────────────────────
# Wear rate components
# ─────────────────────────────────────────────────────────────────────

def mechanical_wear_rate(P_brake_W: float) -> float:
    """
    Mechanical wear rate from sliding-contact dissipation.

        dW_mech/dt = k_mech × P_brake

    Only non-zero during braking events (P_brake > 0).

    Units: kg/s
    """
    return C.K_MECH * P_brake_W


def oxidative_wear_rate(T_disc_K: float) -> float:
    """
    Oxidative wear rate from carbon-oxygen reaction at the disc surface.

        dW_ox/dt = k_ox_0 × exp(-E_a / (R × T))

    Arrhenius form: rises exponentially with temperature. Negligible below
    ~700K (425°C), dominant above ~1000K (725°C).

    Units: kg/s

    Note: T_disc must be in KELVIN. Passing Celsius will give wildly wrong
    rates because the exp is extremely sensitive to T.
    """
    if T_disc_K <= 0:
        return 0.0
    return C.K_OX_0 * np.exp(-C.E_A / (C.R_GAS * T_disc_K))


def total_wear_rate(P_brake_W: float, T_disc_K: float) -> float:
    """
    Total instantaneous mass loss rate per disc (kg/s).

    dW/dt = dW_mech/dt + dW_ox/dt
    """
    return mechanical_wear_rate(P_brake_W) + oxidative_wear_rate(T_disc_K)


# ─────────────────────────────────────────────────────────────────────
# Lap integration
# ─────────────────────────────────────────────────────────────────────

def integrate_wear_lap(t_s: np.ndarray, P_brake_W: np.ndarray,
                        T_disc_K: np.ndarray) -> dict:
    """
    Integrate wear over a full lap.

    Parameters
    ----------
    t_s : timestamps (seconds), monotonically increasing
    P_brake_W : input power to the disc at each timestamp (W)
    T_disc_K : disc temperature at each timestamp (K)

    Returns
    -------
    Dict with:
        'W_mech_kg' : total mechanical wear per disc this lap (kg)
        'W_ox_kg'   : total oxidative wear per disc this lap (kg)
        'W_total_kg': sum
        'W_total_mg': sum in milligrams (more legible for per-lap numbers)
        'thickness_loss_um': average thickness loss per disc face (µm)
        'rate_mech_W_per_s' : array of mechanical wear rate over time
        'rate_ox_W_per_s'   : array of oxidative wear rate over time
    """
    # Compute rates pointwise
    rate_mech = np.array([mechanical_wear_rate(P) for P in P_brake_W])
    rate_ox = np.array([oxidative_wear_rate(T) for T in T_disc_K])

    # Integrate
    W_mech = np.trapezoid(rate_mech, t_s)
    W_ox = np.trapezoid(rate_ox, t_s)
    W_total = W_mech + W_ox

    # Thickness loss: mass / (density × area × 2 faces)
    # Each face loses mass uniformly; total volume loss = mass / density;
    # volume = thickness × area × 2 (both faces wear)
    volume_loss_m3 = W_total / C.RHO_CC
    # Wear is distributed between the two friction faces of the annulus
    A_friction_one_face = np.pi * (C.D_DISC_OUTER**2 - C.D_DISC_INNER**2) / 4
    thickness_loss_per_face_m = volume_loss_m3 / (2 * A_friction_one_face)
    thickness_loss_um = thickness_loss_per_face_m * 1e6

    return {
        'W_mech_kg': W_mech,
        'W_ox_kg': W_ox,
        'W_total_kg': W_total,
        'W_total_mg': W_total * 1e6,
        'thickness_loss_um': thickness_loss_um,
        'rate_mech_kg_per_s': rate_mech,
        'rate_ox_kg_per_s': rate_ox,
    }

"""
Why temperature must be in Kelvin — the exp(-E_a / (R·T)) term is enormously sensitive to T. At 1000 K, it's ~1.6 × 10⁻⁸. At 1000 °C (1273 K), it's ~1.7 × 10⁻⁷ — ten times larger. Mixing the two units once would silently give a wrong answer by orders of magnitude. The docstring flags this loudly.
Why the two mechanisms are separate functions — same reasoning as energy_balance: testability and reusability. If we ever decide to add a third mechanism (e.g., fatigue spallation above a certain temperature), it slots in cleanly.
Thickness conversion — the disc has two friction faces. Both wear roughly equally. Total mass loss → total volume loss → divide by 2 × face area → thickness loss per face. Working in µm because per-lap thickness loss is microscopic in absolute terms.
"""