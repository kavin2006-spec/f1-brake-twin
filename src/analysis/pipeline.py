"""
pipeline.py — End-to-end pipeline: load a session, run the full physics chain,
return per-disc temperature and wear results.

This wraps everything from notebooks 01-04 into a single function so that
multi-track analysis is a clean for-loop rather than copy-pasted notebook cells.
"""

import numpy as np
import fastf1

from src.physics.energy_balance import air_density, decompose_braking_event
from src.physics.thermal_model import build_input_power_per_disc, integrate_lap
from src.physics.wear_model import integrate_wear_lap
from src.utils import constants as C


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def detect_braking_events(t_lap_s: np.ndarray, v_lap_ms: np.ndarray,
                           brake_bool: np.ndarray, dist_lap: np.ndarray,
                           rho_air: float,
                           min_duration_s: float = 0.1,
                           min_delta_v_kmh: float = 5.0) -> list:
    """
    Detect braking events in a lap and return them with energy decomposition.

    Returns a list of dicts with keys:
        event_id, start_idx, end_idx, dist_start_m, duration_s,
        E_brake_front_J
    """
    brake_int = brake_bool.astype(int)
    edges = np.diff(brake_int, prepend=0, append=0)
    starts = np.where(edges == 1)[0]
    ends = np.where(edges == -1)[0] - 1

    events = []
    for i, (s_idx, e_idx) in enumerate(zip(starts, ends)):
        v_ev = v_lap_ms[s_idx:e_idx + 1]
        t_ev = t_lap_s[s_idx:e_idx + 1]
        if len(t_ev) < 2:
            continue
        duration = t_ev[-1] - t_ev[0]
        delta_v_kmh = (v_ev[0] - v_ev[-1]) * 3.6
        if duration < min_duration_s or delta_v_kmh < min_delta_v_kmh:
            continue

        decomp = decompose_braking_event(v_ev, t_ev, rho_air=rho_air)
        events.append({
            'event_id': i + 1,
            'start_idx': int(s_idx),
            'end_idx': int(e_idx),
            'dist_start_m': float(dist_lap[s_idx]),
            'duration_s': float(duration),
            'E_brake_front_J': float(decomp['E_brake_front_J']),
        })

    return events


def converge_to_steady_state(t_lap_s: np.ndarray, v_lap_ms: np.ndarray,
                              P_in_W: np.ndarray, T_amb_K: float,
                              T_init_K: float = 673.15,
                              max_iter: int = 10,
                              tol_K: float = 1.0) -> tuple:
    """
    Fixed-point iteration to find the steady-state lap thermal cycle.

    Returns (T_disc_K array, n_iterations, final_delta_K).
    """
    T_init = T_init_K
    for n in range(1, max_iter + 1):
        T = integrate_lap(t_lap_s, v_lap_ms, P_in_W, T_amb_K, T_init)
        delta = T[-1] - T[0]
        if abs(delta) < tol_K:
            return T, n, delta
        T_init = T[-1]
    return T, max_iter, delta


# ─────────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────────

def run_session(year: int, gp: str, session_type: str = 'Q',
                 lap_selector: str = 'fastest',
                 verbose: bool = True) -> dict:
    """
    Run the full Phase 1a physics chain on a single session lap.

    Parameters
    ----------
    year : season year (e.g. 2026)
    gp : Grand Prix name (e.g. 'Monaco', 'Bahrain')
    session_type : 'Q', 'R', 'FP1', etc.
    lap_selector : currently only 'fastest' supported
    verbose : print progress

    Returns
    -------
    Dict with all per-lap results: telemetry arrays, events,
    temperature trace, wear breakdown, metadata.
    """
    # ── Load ─────────────────────────────────────────────────────────
    if verbose:
        print(f"Loading {year} {gp} {session_type}...")
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

    # ── Energy decomposition per braking event ───────────────────────
    events = detect_braking_events(t_lap_s, v_lap_ms, brake_bool,
                                     dist_lap, rho_air)
    if verbose:
        print(f"  Detected {len(events)} braking events")

    # ── Heat input array ─────────────────────────────────────────────
    P_in = build_input_power_per_disc(t_lap_s, events)

    # ── Thermal model (steady-state) ─────────────────────────────────
    T_disc_K, n_iter, final_delta = converge_to_steady_state(
        t_lap_s, v_lap_ms, P_in, T_amb_K)
    T_disc_C = T_disc_K - 273.15
    if verbose:
        print(f"  Thermal steady state in {n_iter} iter, delta={final_delta:.2f}K")
        print(f"  T_disc: min={T_disc_C.min():.0f}°C, "
              f"max={T_disc_C.max():.0f}°C, mean={T_disc_C.mean():.0f}°C")

    # ── Wear ─────────────────────────────────────────────────────────
    wear = integrate_wear_lap(t_lap_s, P_in, T_disc_K)
    if verbose:
        mech_pct = wear['W_mech_kg'] / wear['W_total_kg'] * 100
        print(f"  Wear: total={wear['W_total_mg']:.2f} mg, "
              f"mech={mech_pct:.1f}%, ox={100-mech_pct:.1f}%")

    # ── Aggregate energy stats ───────────────────────────────────────
    total_E_brake_front_J = sum(e['E_brake_front_J'] for e in events)

    return {
        # Metadata
        'year': year, 'gp': gp, 'session_type': session_type,
        'driver': lap['Driver'], 'team': lap['Team'],
        'lap_time_s': lap['LapTime'].total_seconds(),
        'compound': lap['Compound'],
        # Conditions
        'T_air_C': T_air_C,
        'T_track_C': T_track_C,
        'rho_air_kg_m3': rho_air,
        # Telemetry arrays
        't_lap_s': t_lap_s,
        'v_lap_ms': v_lap_ms,
        'dist_lap_m': dist_lap,
        # Events
        'events': events,
        'n_events': len(events),
        # Thermal
        'P_in_W_per_disc': P_in,
        'T_disc_K': T_disc_K,
        'T_disc_C': T_disc_C,
        'T_min_C': float(T_disc_C.min()),
        'T_max_C': float(T_disc_C.max()),
        'T_mean_C': float(T_disc_C.mean()),
        'n_iter_steady_state': n_iter,
        'steady_state_delta_K': float(final_delta),
        # Wear
        'wear_mech_mg_per_disc': wear['W_mech_kg'] * 1e6,
        'wear_ox_mg_per_disc': wear['W_ox_kg'] * 1e6,
        'wear_total_mg_per_disc': wear['W_total_mg'],
        'thickness_loss_um_per_face': wear['thickness_loss_um'],
        'mech_fraction': wear['W_mech_kg'] / wear['W_total_kg'] if wear['W_total_kg'] > 0 else 1.0,
        # Energy aggregate
        'total_E_brake_front_MJ': total_E_brake_front_J / 1e6,
        'E_per_disc_MJ': total_E_brake_front_J / 2 / 1e6,
    }

"""
Why a single function returning a dict, not a class — for a paper/portfolio project we want results to be easy to compare across sessions. A dict per session, collected into a list of dicts → DataFrame, is the cleanest path. A class would be overkill.
Why I exposed detect_braking_events and converge_to_steady_state separately — they encode logic that's currently scattered across notebooks. Even if run_session is the public entry point, having these as separate testable units matters.
lap_selector='fastest' as the only option for now — we may want "pole lap from Q3", "best clean lap from race", etc. later. The parameter is there so adding modes is non-breaking.
No tests yet — run_session requires network and is an integration function, not a unit. We'd test it via a fixture later if we ever package this. The components inside it (energy balance, thermal, wear) are all already covered.
"""