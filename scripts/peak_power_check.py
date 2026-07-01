"""
Quick diagnostic: estimate peak braking power per event for Canada vs Monaco
vs Miami. Looks for sustained-power-above-MGU-K-limit (350 kW) on rear axle.
"""
import sys
import pickle
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

# Constants for the back-of-envelope
PEAK_TO_AVG_RATIO = 1.7   # F1 deceleration profile is roughly triangular-falling
REAR_BIAS = 0.44          # 1 - 0.56 front
MGUK_LIMIT_KW = 350       # 2026 regs

tracks = ['Canada', 'Monaco', 'Miami']

for gp in tracks:
    pkl_path = Path(f'data/precomputed/2026_{gp}_Q.pkl')
    if not pkl_path.exists():
        print(f"No precomputed data for {gp}")
        continue

    with open(pkl_path, 'rb') as f:
        r = pickle.load(f)

    print(f"\n=== {gp} 2026 Q ({r['driver']}, lap {r['lap_time_s']:.2f}s) ===")
    print(f"  {r['n_events']} events, {r['E_per_disc_MJ']:.2f} MJ/disc front-axle")

    # For each event:
    # avg power per event = E_brake_front_J / (2 * duration)  [per disc]
    # But we want REAR-AXLE peak power, not per-disc front-axle average.
    # Rear axle gets (0.44 / 0.56) * front_total_brake_energy
    # Actually rear gets directly from the energy balance: bias_rear * E_brake_total
    # We can derive: E_rear = (rear_bias / front_bias) * E_front
    rear_to_front_ratio = REAR_BIAS / (1 - REAR_BIAS)

    events = r['events']
    summary = []
    for ev in events:
        E_front_J = ev['E_brake_front_J']
        E_rear_J = E_front_J * rear_to_front_ratio
        duration = ev['duration_s']
        avg_power_rear_kW = E_rear_J / duration / 1000
        peak_power_rear_kW = avg_power_rear_kW * PEAK_TO_AVG_RATIO
        exceeds = peak_power_rear_kW > MGUK_LIMIT_KW
        summary.append({
            'event': ev['event_id'],
            'duration_s': duration,
            'E_rear_kJ': E_rear_J / 1000,
            'avg_P_rear_kW': avg_power_rear_kW,
            'peak_P_rear_kW': peak_power_rear_kW,
            'exceeds_MGUK': exceeds,
        })

    df = pd.DataFrame(summary)
    print(df.to_string(index=False))

    n_exceed = df['exceeds_MGUK'].sum()
    if n_exceed > 0:
        # Rough estimate of duration above threshold
        # If peak is at start and falls linearly, duration above threshold
        # is duration * (peak - threshold) / peak
        df_exceed = df[df['exceeds_MGUK']].copy()
        df_exceed['dur_above_threshold_s'] = (
            df_exceed['duration_s']
            * (df_exceed['peak_P_rear_kW'] - MGUK_LIMIT_KW)
            / df_exceed['peak_P_rear_kW']
        )
        total_dur_above = df_exceed['dur_above_threshold_s'].sum()
        print(f"\n  Events with peak rear power > {MGUK_LIMIT_KW} kW: {n_exceed}/{len(df)}")
        print(f"  Total estimated duration above MGU-K limit: {total_dur_above:.2f} s per lap")
        print(f"  As fraction of lap: {total_dur_above / r['lap_time_s'] * 100:.1f}%")
    else:
        print(f"\n  No events exceed MGU-K {MGUK_LIMIT_KW} kW limit")