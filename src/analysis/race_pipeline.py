"""
race_pipeline.py — Multi-lap race analysis for the F1 brake digital twin.

See docs/04_phase_1b_chunk_1_scope.md for design decisions.
"""

import numpy as np
import pandas as pd
import fastf1

from src.physics.energy_balance import (
    air_density, decompose_braking_event,
)
from src.physics.thermal_model import build_input_power_per_disc, integrate_lap
from src.physics.wear_model import integrate_wear_lap
from src.utils import constants as C

# ─────────────────────────────────────────────────────────────────────
# Telemetry loader (uses car_data only, computes distance)
# ─────────────────────────────────────────────────────────────────────

def _get_lap_telemetry(lap_row):
    """
    Load car telemetry for a lap and compute Distance.

    Uses get_car_data() instead of get_telemetry() to avoid FastF1's
    car-data-to-position-data merge, which fails on some 2026 race laps
    with KeyError on a missing 'Date' column in position data.

    Returns
    -------
    t_s : timestamps in seconds, starting at 0
    v_ms : speed in m/s
    brake_bool : brake on/off
    dist_m : cumulative distance from cumulative integration of speed
    """
    car = lap_row.get_car_data()

    t_s = car['Time'].dt.total_seconds().values
    t_s = t_s - t_s[0]
    v_ms = car['Speed'].values / 3.6
    brake_bool = car['Brake'].astype(bool).values

    if len(t_s) > 1:
        dt = np.diff(t_s)
        increments = 0.5 * (v_ms[1:] + v_ms[:-1]) * dt
        dist_m = np.concatenate([[0.0], np.cumsum(increments)])
    else:
        dist_m = np.zeros(len(t_s))

    return t_s, v_ms, brake_bool, dist_m


# ─────────────────────────────────────────────────────────────────────
# Fuel / car mass evolution
# ─────────────────────────────────────────────────────────────────────

def fuel_mass_at_lap(lap_number: int, n_race_laps: int) -> float:
    """Fuel mass (kg) at the start of a given lap (linear burn-down)."""
    m_start = min(C.FUEL_KG_PER_LAP * n_race_laps, C.FUEL_MAX_KG)
    m_end = C.FUEL_END_KG
    if n_race_laps <= 1:
        return m_start
    frac = max(0.0, min(1.0, (lap_number - 1) / (n_race_laps - 1)))
    return m_start - (m_start - m_end) * frac


def car_mass_at_lap(lap_number: int, n_race_laps: int) -> float:
    """Total car mass (kg): dry + driver + fuel."""
    # C.M_CAR is the Q3 mass which already bakes in ~5 kg fuel; strip it
    m_dry_and_driver = C.M_CAR - 5.0
    return m_dry_and_driver + fuel_mass_at_lap(lap_number, n_race_laps)


# ─────────────────────────────────────────────────────────────────────
# Lap filtering
# ─────────────────────────────────────────────────────────────────────

def is_clean_racing_lap(lap_row) -> tuple:
    """Return (bool, reason) — whether to analyze this lap."""
    lap_num = int(lap_row['LapNumber'])
    if lap_num == 1:
        return False, "lap_1_standing_start"
    if pd.isna(lap_row['LapTime']):
        return False, "no_lap_time"
    track_status = str(lap_row.get('TrackStatus', '1'))
    if track_status != '1':
        return False, f"track_status_{track_status}"
    return True, "clean"


def is_bookend_lap(lap_row) -> bool:
    """True if this is an in-lap or out-lap."""
    return pd.notna(lap_row.get('PitInTime')) or pd.notna(lap_row.get('PitOutTime'))


# ─────────────────────────────────────────────────────────────────────
# Per-lap analysis helper (mass-aware)
# ─────────────────────────────────────────────────────────────────────

def _detect_events_mass_aware(t_s, v_ms, brake_bool, dist, rho_air, mass,
                                min_duration_s=0.1, min_delta_v_kmh=5.0):
    """Event detection + decomposition, with explicit mass parameter."""
    brake_int = brake_bool.astype(int)
    edges = np.diff(brake_int, prepend=0, append=0)
    starts = np.where(edges == 1)[0]
    ends = np.where(edges == -1)[0] - 1

    events = []
    for i, (s, e) in enumerate(zip(starts, ends)):
        v_ev = v_ms[s:e + 1]
        t_ev = t_s[s:e + 1]
        if len(t_ev) < 2:
            continue
        duration = t_ev[-1] - t_ev[0]
        delta_v_kmh = (v_ev[0] - v_ev[-1]) * 3.6
        if duration < min_duration_s or delta_v_kmh < min_delta_v_kmh:
            continue
        decomp = decompose_braking_event(v_ev, t_ev, rho_air=rho_air,
                                           mass=mass)
        events.append({
            'event_id': i + 1,
            'start_idx': int(s),
            'end_idx': int(e),
            'dist_start_m': float(dist[s]),
            'duration_s': float(duration),
            'E_brake_front_J': float(decomp['E_brake_front_J']),
        })
    return events


# ─────────────────────────────────────────────────────────────────────
# Main race entry point
# ─────────────────────────────────────────────────────────────────────

def run_race(year: int, gp: str, driver: str = None,
              verbose: bool = True) -> dict:
    """
    Run the full Phase 1b chunk 1 race-condition pipeline.

    Parameters
    ----------
    year, gp : as for FastF1
    driver : 3-letter code (e.g. 'ANT'); defaults to race winner
    verbose : print per-lap progress

    Returns
    -------
    Dict with per-lap and per-stint results, plus cumulative wear and
    race-level metadata.
    """
    if verbose:
        print(f"Loading {year} {gp} Race...")
    session = fastf1.get_session(year, gp, 'R')
    session.load(laps=True, telemetry=True, weather=True, messages=False)

    # Determine number of race laps (max LapNumber across all drivers)
    n_race_laps = int(session.laps['LapNumber'].max())

    # Pick driver
    if driver is None:
        driver = session.results.iloc[0]['Abbreviation']
        if verbose:
            print(f"  Defaulting to race winner: {driver}")

    driver_laps = session.laps.pick_drivers(driver).reset_index(drop=True)
    if verbose:
        print(f"  {driver}: {len(driver_laps)} laps in data, race had {n_race_laps} laps")

    # Weather → air density
    T_air_C = float(session.weather_data['AirTemp'].mean())
    T_amb_K = T_air_C + 273.15
    rho_air = air_density(T_air_C)

    # Initialize
    T_disc_K = C.T_RACE_START_C + 273.15
    cumulative_W_mech_kg = 0.0
    cumulative_W_ox_kg = 0.0

    per_lap_results = []
    skipped_laps = []

    # Iterate through laps in lap-number order
    for _, lap_row in driver_laps.iterrows():
        lap_num = int(lap_row['LapNumber'])

        is_clean, reason = is_clean_racing_lap(lap_row)
        if not is_clean:
            skipped_laps.append({'lap': lap_num, 'reason': reason})
            continue

        # Per-lap mass
        m_car = car_mass_at_lap(lap_num, n_race_laps)

        # Get telemetry (car_data only, distance computed)
        try:
            t_lap, v_lap_ms, brake_bool, dist_lap = _get_lap_telemetry(lap_row)
        except Exception as ex:
            reason = f'{type(ex).__name__}: {str(ex)[:60]}'
            skipped_laps.append({'lap': lap_num, 'reason': reason})
            continue
        if len(t_lap) < 10:
            skipped_laps.append({'lap': lap_num, 'reason': 'telemetry_too_short'})
            continue

        # Event detection + decomposition, mass-aware
        events = _detect_events_mass_aware(
            t_lap, v_lap_ms, brake_bool, dist_lap, rho_air, m_car)

        # Heat input + thermal integration (forward from T_disc_K)
        P_in = build_input_power_per_disc(t_lap, events)
        T_disc_lap_K = integrate_lap(t_lap, v_lap_ms, P_in,
                                       T_amb_K=T_amb_K, T_init_K=T_disc_K)

        # Wear for this lap
        wear = integrate_wear_lap(t_lap, P_in, T_disc_lap_K)
        cumulative_W_mech_kg += wear['W_mech_kg']
        cumulative_W_ox_kg += wear['W_ox_kg']

        # Update T_disc carrying forward
        T_disc_end_K = T_disc_lap_K[-1]

        # Record
        per_lap_results.append({
            'lap_number': lap_num,
            'stint': int(lap_row.get('Stint', 0)) if pd.notna(lap_row.get('Stint')) else 0,
            'compound': lap_row.get('Compound', None),
            'tyre_age': int(lap_row['TyreLife']) if pd.notna(lap_row.get('TyreLife')) else None,
            'is_bookend_lap': is_bookend_lap(lap_row),
            'm_car_kg': m_car,
            'lap_time_s': lap_row['LapTime'].total_seconds(),
            'n_events': len(events),
            'E_brake_front_J': sum(e['E_brake_front_J'] for e in events),
            'T_disc_start_C': T_disc_K - 273.15,
            'T_disc_end_C': T_disc_end_K - 273.15,
            'T_disc_mean_C': float(T_disc_lap_K.mean() - 273.15),
            'T_disc_max_C': float(T_disc_lap_K.max() - 273.15),
            'wear_mech_lap_mg': wear['W_mech_kg'] * 1e6,
            'wear_ox_lap_mg': wear['W_ox_kg'] * 1e6,
            'wear_total_cum_mg': (cumulative_W_mech_kg + cumulative_W_ox_kg) * 1e6,
        })

        # Carry temperature forward
        T_disc_K = T_disc_end_K

        if verbose:
            tag = ' (bookend)' if is_bookend_lap(lap_row) else ''
            print(f"  L{lap_num:2d} stint {per_lap_results[-1]['stint']}"
                  f" m={m_car:.0f}kg events={len(events):2d}"
                  f" T={per_lap_results[-1]['T_disc_mean_C']:.0f}C"
                  f" cum_wear={per_lap_results[-1]['wear_total_cum_mg']:.1f}mg{tag}")

    # Build per-lap DataFrame
    per_lap_df = pd.DataFrame(per_lap_results)

    # Per-stint aggregation
    if len(per_lap_df) > 0:
        per_stint_df = per_lap_df.groupby('stint').agg(
            n_laps=('lap_number', 'count'),
            n_bookend=('is_bookend_lap', 'sum'),
            compound=('compound', 'first'),
            T_mean_C=('T_disc_mean_C', 'mean'),
            T_max_C=('T_disc_max_C', 'max'),
            wear_mech_mg=('wear_mech_lap_mg', 'sum'),
            wear_ox_mg=('wear_ox_lap_mg', 'sum'),
            E_brake_total_MJ=('E_brake_front_J', lambda x: x.sum() / 1e6),
        ).reset_index()
        per_stint_df['wear_total_mg'] = (per_stint_df['wear_mech_mg']
                                          + per_stint_df['wear_ox_mg'])
    else:
        per_stint_df = pd.DataFrame()

    return {
        'year': year, 'gp': gp, 'driver': driver,
        'n_race_laps': n_race_laps,
        'n_analyzed_laps': len(per_lap_df),
        'n_skipped_laps': len(skipped_laps),
        'T_air_C': T_air_C,
        'T_track_C': float(session.weather_data['TrackTemp'].mean()),
        'per_lap': per_lap_df,
        'per_stint': per_stint_df,
        'skipped_laps': skipped_laps,
        'final_wear_total_mg': (cumulative_W_mech_kg + cumulative_W_ox_kg) * 1e6,
        'final_wear_mech_mg': cumulative_W_mech_kg * 1e6,
        'final_wear_ox_mg': cumulative_W_ox_kg * 1e6,
    }

"""
Why I subtracted 5 kg from C.M_CAR in car_mass_at_lap. Phase 1a's M_CAR = 850 includes ~5 kg of Q3 fuel as part of the qualifying mass. For race-mass modeling we need dry+driver only, then add real fuel separately. Stripping the 5 kg keeps both pipelines internally consistent without changing the original Phase 1a constant.
The _detect_events_mass_aware helper. The existing detect_braking_events in pipeline.py hardcodes the Phase 1a mass via the default arg of decompose_braking_event. For race we need explicit mass per lap. Rather than modify the Phase 1a function and risk breaking the qualifying pipeline, I added a parallel mass-aware version. Slight duplication, but it keeps Phase 1a untouched.
No iteration to steady state. Race integration goes forward, lap by lap, carrying the disc temperature continuously. The initial 350°C condition gets forgotten within ~3 laps because of the thermal time constant.
Verbose output per lap. Will be noisy on a 78-lap race but useful for the first run to verify nothing's going wrong silently.
"""