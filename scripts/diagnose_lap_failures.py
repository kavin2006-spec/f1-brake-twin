"""
Diagnostic: try to get telemetry for the laps the smoke test skipped,
WITHOUT swallowing the exception. We want the real traceback.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import traceback
import fastf1
fastf1.Cache.enable_cache('data/raw')

session = fastf1.get_session(2026, 'Monaco', 'R')
session.load(laps=True, telemetry=True, weather=True, messages=False)

driver_laps = session.laps.pick_drivers('ANT').reset_index(drop=True)
print(f"ANT has {len(driver_laps)} laps in session.laps")
print(f"LapNumbers present: {sorted(driver_laps['LapNumber'].dropna().astype(int).tolist())}")

# Try a known-good lap (5) and a known-failing lap (6, 10, 20)
for target_lap in [5, 6, 10, 20, 44, 50]:
    print(f"\n--- Trying lap {target_lap} ---")
    matching = driver_laps[driver_laps['LapNumber'] == target_lap]
    if len(matching) == 0:
        print(f"  Lap {target_lap} not found in driver_laps")
        continue
    lap_row = matching.iloc[0]
    print(f"  LapNumber={lap_row['LapNumber']}, "
          f"LapTime={lap_row['LapTime']}, "
          f"TrackStatus={lap_row.get('TrackStatus')}, "
          f"PitInTime={lap_row.get('PitInTime')}, "
          f"PitOutTime={lap_row.get('PitOutTime')}, "
          f"Compound={lap_row.get('Compound')}")

    try:
        tel = lap_row.get_telemetry()
        print(f"  SUCCESS: telemetry shape {tel.shape}, "
              f"columns {list(tel.columns)[:8]}...")
    except Exception:
        print(f"  FAILURE — full traceback:")
        traceback.print_exc()