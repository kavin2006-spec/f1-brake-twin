"""Smoke test: run race pipeline on Monaco 2026 R for ANT and print summary."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import fastf1
fastf1.Cache.enable_cache('data/raw')

from src.analysis.race_pipeline import run_race

r = run_race(2026, 'Monaco', 'ANT', verbose=True)

print()
print("=" * 60)
print(f"  Race: {r['year']} {r['gp']} R — {r['driver']}")
print(f"  Analyzed: {r['n_analyzed_laps']} / {r['n_race_laps']} laps "
      f"({r['n_skipped_laps']} skipped)")
print(f"  Conditions: T_air={r['T_air_C']:.1f}°C, T_track={r['T_track_C']:.1f}°C")
print(f"  Final wear: {r['final_wear_total_mg']:.2f} mg "
      f"(mech {r['final_wear_mech_mg']:.2f}, ox {r['final_wear_ox_mg']:.4f})")

if len(r['per_lap']) > 0:
    last = r['per_lap'].tail(5)
    print(f"\n  Last 5 analyzed laps:")
    print(last[['lap_number', 'stint', 'compound', 'm_car_kg',
                 'n_events', 'T_disc_mean_C', 'T_disc_max_C',
                 'wear_total_cum_mg', 'is_bookend_lap']].to_string(index=False))

if len(r['per_stint']) > 0:
    print(f"\n  Per-stint summary:")
    print(r['per_stint'].to_string(index=False))

if r['skipped_laps']:
    print(f"\n  Skipped laps:")
    for s in r['skipped_laps'][:10]:
        print(f"    lap {s['lap']:2d}: {s['reason']}")
    if len(r['skipped_laps']) > 10:
        print(f"    ... and {len(r['skipped_laps']) - 10} more")

        # Full skipped laps list
print(f"\n  Full skipped laps ({len(r['skipped_laps'])}):")
for s in r['skipped_laps']:
    print(f"    lap {s['lap']:2d}: {s['reason']}")

# Stint distribution in raw lap data
print("\n  Raw stint distribution (from session.laps, not filtered):")
import fastf1
fastf1.Cache.enable_cache('data/raw')
session = fastf1.get_session(2026, 'Monaco', 'R')
session.load(laps=True, telemetry=False, weather=False, messages=False)
ant_laps_raw = session.laps.pick_drivers('ANT')
print(ant_laps_raw[['LapNumber', 'Stint', 'Compound', 'PitInTime',
                     'PitOutTime', 'TrackStatus', 'LapTime']].to_string(index=False))