"""
rear_pipeline.py — End-to-end rear-axle analysis for a single qualifying lap.

Mirrors src/analysis/pipeline.py (front-axle, single fast lap) but for the
rear axle, where MGU-K regenerative braking absorbs part of the rear-axle
braking energy and only the remainder reaches the friction brakes.

Computation flow:
    Telemetry
      → Sample-level total brake power
      → Rear-axle share via BETA_REAR
      → Greedy MGU-K power cap: split into P_regen and P_friction_rear
      → Build heat input per rear disc (P_friction_rear / 2)
      → Rear thermal model (forward Euler, steady-state iteration)
      → Rear wear model

For race-condition rear analysis (Phase 1b chunk 2 notebook 08), this
single-lap pipeline is wrapped by analogy with race_pipeline.py — that
extension is deliberately deferred so the qualifying-only model can be
validated in isolation first.
"""

import numpy as np
import pandas as pd
import fastf1

from src.physics.energy_balance import (
    air_density,
    brake_power_instantaneous,
)
from src.physics.regen_model import (
    split_rear_brake_power,
    regen_energy_per_event,
    regen_fraction_per_event,
    mguk_binding_fraction,
)
from src.physics.thermal_model import build_input_power_per_disc, integrate_lap
from src.physics.wear_model import integrate_wear_lap
from src.analysis.pipeline import detect_braking_events
from src.utils import constants as C


# ─────────────────────────────────────────────────────────────────────
# Steady-state iteration (rear-axle version)
# ─────────────────────────────────────────────────────────────────────

def _converge_rear_steady_state(t_s, v_ms, P_in_W, T_amb_K,
                                  T_init_K=673.15,
                                  max_iter=10, tol_K=1.0):
    """Fixed-point iteration to find the rear-disc steady-state lap cycle."""
    T_init = T_init_K
    for n in range(1, max_iter + 1):
        T = integrate_lap(
            t_s, v_ms, P_in_W, T_amb_K, T_init,
            m_disc=C.M_DISC_REAR,
            h_eff_0=C.H_EFF_0_REAR,
            A_disc_geometric=C.A_DISC_GEOMETRIC_REAR,
        )
        delta = T[-1] - T[0]
        if abs(delta) < tol_K:
            return T, n, delta
        T_init = T[-1]
    return T, max_iter, delta


# ─────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────

def run_session_rear(year: int, gp: str, session_type: str = 'Q',
                      lap_selector: str = 'fastest',
                      h_eff_0_rear: float = None,
                      verbose: bool = True) -> dict:
    """
    Run the full rear-axle physics chain on a single session lap.

    Parameters
    ----------
    year, gp, session_type : as for FastF1
    lap_selector : currently only 'fastest' supported
    h_eff_0_rear : override for sensitivity analysis. None = use C.H_EFF_0_REAR.
    verbose : print progress

    Returns
    -------
    Dict with telemetry arrays, events, regen/friction splits, rear thermal
    trace, rear wear breakdown, and binding-fraction diagnostics.
    """
    if h_eff_0_rear is None:
        h_eff_0_rear = C.H_EFF_0_REAR

    # ── Load ─────────────────────────────────────────────────────────
    if verbose:
        print(f"Loading {year} {gp} {session_type} (rear-axle)...")
    session = fastf1.get_session(year, gp, session_type)
    session.load(laps=True, telemetry=True, weather=True, messages=False)

    if lap_selector == 'fastest':
        lap = session.laps.pick_fastest()
    else:
        raise ValueError(f"Unsupported lap_selector: {lap_selector}")

    tel = lap.get_telemetry()

    # ── Telemetry arrays ─────────────────────────────────────────────
    t_lap_s = tel['Time'].dt.total_seconds().values
    v_lap_ms = tel['Speed'].values / 3.6
    dist_lap = tel['Distance'].values
    brake_bool = tel['Brake'].astype(bool).values

    # ── Weather → air density ────────────────────────────────────────
    T_air_C = float(session.weather_data['AirTemp'].mean())
    T_track_C = float(session.weather_data['TrackTemp'].mean())
    T_amb_K = T_air_C + 273.15
    rho_air = air_density(T_air_C)

    # ── Sample-level total brake power, then rear share ──────────────
    P_brake_total = brake_power_instantaneous(
        v_lap_ms, t_lap_s, rho_air=rho_air, brake_bool=brake_bool,
    )
    P_brake_rear = C.BETA_REAR * P_brake_total

    # ── Apply MGU-K power cap ────────────────────────────────────────
    P_regen, P_friction_rear = split_rear_brake_power(P_brake_rear)

    # ── Event detection (for diagnostics; uses Phase 1a logic) ──────
    events = detect_braking_events(t_lap_s, v_lap_ms, brake_bool,
                                     dist_lap, rho_air)
    if verbose:
        print(f"  {len(events)} braking events detected")

    # Per-event regen/friction energies for diagnostics
    E_regen_per_event = regen_energy_per_event(P_regen, t_lap_s, events)
    E_friction_per_event = regen_energy_per_event(P_friction_rear,
                                                    t_lap_s, events)
    regen_frac_per_event = regen_fraction_per_event(
        P_regen, P_friction_rear, t_lap_s, events,
    )

    # ── Build heat input per rear disc ───────────────────────────────
    # Per-disc = half of P_friction_rear (left/right modeled identically)
    P_in_per_rear_disc = P_friction_rear / 2.0

    # ── Rear thermal model (steady-state) ────────────────────────────
    T_disc_rear_K, n_iter, final_delta = _converge_rear_steady_state(
        t_lap_s, v_lap_ms, P_in_per_rear_disc, T_amb_K,
    )
    # If h_eff_0_rear was overridden (sensitivity), redo the integration
    # with the override applied. We had to use the default for the iteration
    # helper's signature, so re-run if needed.
    if h_eff_0_rear != C.H_EFF_0_REAR:
        T_init = T_disc_rear_K[-1]  # warm start from default solution
        for _ in range(10):
            T_disc_rear_K = integrate_lap(
                t_lap_s, v_lap_ms, P_in_per_rear_disc, T_amb_K, T_init,
                m_disc=C.M_DISC_REAR,
                h_eff_0=h_eff_0_rear,
                A_disc_geometric=C.A_DISC_GEOMETRIC_REAR,
            )
            if abs(T_disc_rear_K[-1] - T_disc_rear_K[0]) < 1.0:
                break
            T_init = T_disc_rear_K[-1]

    T_disc_rear_C = T_disc_rear_K - 273.15

    if verbose:
        print(f"  Rear thermal steady state: T_min={T_disc_rear_C.min():.0f}°C, "
              f"T_max={T_disc_rear_C.max():.0f}°C, T_mean={T_disc_rear_C.mean():.0f}°C")

    # ── Rear wear ────────────────────────────────────────────────────
    wear = integrate_wear_lap(
        t_lap_s, P_in_per_rear_disc, T_disc_rear_K,
        disc_outer=C.D_DISC_OUTER_REAR,
        disc_inner=C.D_DISC_INNER_REAR,
    )
    if verbose:
        print(f"  Rear wear per disc: {wear['W_total_mg']:.2f} mg "
              f"(mech {wear['W_mech_kg']/wear['W_total_kg']*100:.1f}%)")

    # ── MGU-K binding diagnostic ─────────────────────────────────────
    binding_frac = mguk_binding_fraction(P_brake_rear, t_lap_s,
                                           brake_bool=brake_bool)
    if verbose:
        print(f"  MGU-K limit binding for {binding_frac*100:.1f}% of brake-on time")

    # ── Aggregate totals ─────────────────────────────────────────────
    E_regen_total = float(np.trapezoid(P_regen, t_lap_s))
    E_friction_rear_total = float(np.trapezoid(P_friction_rear, t_lap_s))
    E_brake_rear_total = E_regen_total + E_friction_rear_total

    return {
        # Metadata
        'year': year, 'gp': gp, 'session_type': session_type,
        'driver': lap['Driver'], 'team': lap['Team'],
        'lap_time_s': lap['LapTime'].total_seconds(),
        'compound': lap['Compound'],
        'h_eff_0_rear_used': h_eff_0_rear,
        # Conditions
        'T_air_C': T_air_C,
        'T_track_C': T_track_C,
        'rho_air_kg_m3': rho_air,
        # Telemetry arrays
        't_lap_s': t_lap_s,
        'v_lap_ms': v_lap_ms,
        'dist_lap_m': dist_lap,
        'brake_bool': brake_bool,
        # Power split arrays
        'P_brake_total_W': P_brake_total,
        'P_brake_rear_W': P_brake_rear,
        'P_regen_W': P_regen,
        'P_friction_rear_W': P_friction_rear,
        'P_in_per_rear_disc_W': P_in_per_rear_disc,
        # Events with regen split
        'events': events,
        'n_events': len(events),
        'E_regen_per_event_J': E_regen_per_event,
        'E_friction_rear_per_event_J': E_friction_per_event,
        'regen_fraction_per_event': regen_frac_per_event,
        # Energy aggregates
        'E_brake_rear_total_J': E_brake_rear_total,
        'E_regen_total_J': E_regen_total,
        'E_friction_rear_total_J': E_friction_rear_total,
        'regen_fraction_lap': E_regen_total / E_brake_rear_total if E_brake_rear_total > 0 else 0.0,
        # Thermal
        'T_disc_rear_K': T_disc_rear_K,
        'T_disc_rear_C': T_disc_rear_C,
        'T_rear_min_C': float(T_disc_rear_C.min()),
        'T_rear_max_C': float(T_disc_rear_C.max()),
        'T_rear_mean_C': float(T_disc_rear_C.mean()),
        'n_iter_steady_state': n_iter,
        # Wear
        'wear_mech_mg_per_rear_disc': wear['W_mech_kg'] * 1e6,
        'wear_ox_mg_per_rear_disc': wear['W_ox_kg'] * 1e6,
        'wear_total_mg_per_rear_disc': wear['W_total_mg'],
        'thickness_loss_um_per_rear_face': wear['thickness_loss_um'],
        # MGU-K binding diagnostic
        'mguk_binding_fraction': binding_frac,
    }

"""
The steady-state iteration is duplicated. Once for the default H_EFF_0_REAR, once for the override case. This is mildly ugly but pragmatic — keeping the helper function's signature simple while still supporting sensitivity sweeps. We could refactor later if it becomes annoying.
No new unit tests yet. run_session_rear is an integration function — like its front-axle siblings, it requires network and FastF1 data. The pieces it composes (brake_power_instantaneous, split_rear_brake_power, integrate_lap, integrate_wear_lap) are all already covered by unit tests. We'll validate this with a smoke test instead.
The output dict is dense by design. Every quantity the notebook might want is there. This way the notebook just unpacks the dict and plots — no recomputation, no re-loading the session.
"""