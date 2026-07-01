"""Smoke test: run rear pipeline on Monaco 2026 Q and print summary."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import fastf1
fastf1.Cache.enable_cache('data/raw')

from src.analysis.rear_pipeline import run_session_rear

r = run_session_rear(2026, 'Monaco', 'Q', verbose=True)

print()
print("=" * 60)
print(f"  Session: {r['year']} {r['gp']} {r['session_type']} — {r['driver']}")
print(f"  Lap time: {r['lap_time_s']:.3f}s")
print(f"  Conditions: T_air={r['T_air_C']:.1f}°C")
print()
print("  Rear-axle energy budget (per axle):")
print(f"    Total rear braking:  {r['E_brake_rear_total_J']/1e6:.2f} MJ")
print(f"    Regen (MGU-K):       {r['E_regen_total_J']/1e6:.2f} MJ "
      f"({r['regen_fraction_lap']*100:.1f}%)")
print(f"    Friction (rear):     {r['E_friction_rear_total_J']/1e6:.2f} MJ "
      f"({(1-r['regen_fraction_lap'])*100:.1f}%)")
print()
print(f"  MGU-K limit binding for {r['mguk_binding_fraction']*100:.1f}% of brake-on time")
print(f"  (back-of-envelope diagnostic predicted ~4.6%)")
print()
print(f"  Rear disc thermal cycle:")
print(f"    T_min:  {r['T_rear_min_C']:.0f} °C")
print(f"    T_mean: {r['T_rear_mean_C']:.0f} °C")
print(f"    T_max:  {r['T_rear_max_C']:.0f} °C")
print()
print(f"  Rear wear per disc per lap:")
print(f"    Mechanical: {r['wear_mech_mg_per_rear_disc']:.2f} mg")
print(f"    Oxidative:  {r['wear_ox_mg_per_rear_disc']:.4f} mg")
print(f"    Total:      {r['wear_total_mg_per_rear_disc']:.2f} mg "
      f"({r['thickness_loss_um_per_rear_face']:.3f} µm thickness)")
print()
print(f"  Per-event regen fractions:")
for i, ev in enumerate(r['events']):
    print(f"    event {ev['event_id']:2d} at {ev['dist_start_m']:>5.0f}m: "
          f"regen={r['regen_fraction_per_event'][i]*100:>5.1f}%  "
          f"E_friction_rear={r['E_friction_rear_per_event_J'][i]/1000:>5.0f} kJ")