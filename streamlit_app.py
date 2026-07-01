"""
F1 Brake Twin — Phase 1a dashboard.

Run locally: streamlit run streamlit_app.py
Deploy:      share.streamlit.io, point at this repo, main file = streamlit_app.py
"""
import pickle
import sys
from pathlib import Path

import fastf1
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

# Make src/ importable when Streamlit runs this file
sys.path.insert(0, str(Path(__file__).parent))

from src.analysis.pipeline import run_session


# ── Page setup ────────────────────────────────────────────────
st.set_page_config(
    page_title="F1 Brake Twin",
    page_icon="🏎️",
    layout="wide",
)

PRECOMPUTED_DIR = Path('data/precomputed')
CACHE_DIR = Path('data/raw')
CACHE_DIR.mkdir(parents=True, exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))

PRECOMPUTED_SESSIONS = [
    (2026, 'Australia', 'Q'),
    (2026, 'China',     'Q'),
    (2026, 'Japan',     'Q'),
    (2026, 'Miami',     'Q'),
    (2026, 'Monaco',    'Q'),
    (2026, 'Canada',    'Q'),
]


# ── Data loading (cached by Streamlit per-session) ────────────
@st.cache_data(show_spinner=False)
def load_session_result(year: int, gp: str, sess: str):
    """Read from pickle if precomputed, otherwise run the pipeline live."""
    pkl = PRECOMPUTED_DIR / f"{year}_{gp.replace(' ', '_')}_{sess}.pkl"
    if pkl.exists():
        with open(pkl, 'rb') as f:
            return pickle.load(f)
    return run_session(year, gp, sess, verbose=False)


# ── Sidebar: session selection ────────────────────────────────
st.sidebar.title("🏎️ F1 Brake Twin")
st.sidebar.markdown("---")

mode = st.sidebar.radio(
    "Session source",
    options=["Quick pick (precomputed)", "Custom session (live)"],
    index=0,
)

if mode == "Quick pick (precomputed)":
    selected = st.sidebar.selectbox(
        "Session",
        options=PRECOMPUTED_SESSIONS,
        format_func=lambda x: f"{x[0]} {x[1]} {x[2]}",
        index=4,  # Monaco
    )
    year, gp, sess = selected
else:
    st.sidebar.caption(
        "Live FastF1 — first load can take 30-90 seconds while data downloads."
    )
    year = st.sidebar.number_input("Year", min_value=2018, max_value=2026, value=2026)
    gp = st.sidebar.text_input("Grand Prix", value="Monaco",
                                help="e.g. Monaco, Italy, Belgium, Australia")
    sess = st.sidebar.selectbox("Session", ['Q', 'R', 'FP1', 'FP2', 'FP3'], index=0)
    if not st.sidebar.button("Load custom session"):
        # Don't run until user explicitly clicks
        st.info("Configure a custom session in the sidebar and click "
                "'Load custom session', or switch back to a precomputed quick pick.")
        st.stop()


# ── Header ────────────────────────────────────────────────────
st.title("F1 Brake Twin")
st.markdown(
    "**Hidden brake disc state estimation for 2026 Formula 1 cars** — "
    "temperature and wear, estimated from public telemetry using a hybrid "
    "physics digital twin."
)

with st.expander("What is this?"):
    st.markdown("""
    Modern F1 brakes operate at over 800°C and wear by millimeters per race —
    but neither temperature nor wear is directly measurable in publicly
    available data. This dashboard estimates both from telemetry that FastF1
    exposes (speed, throttle, brake on/off, gear, RPM, weather).
    
    The pipeline runs three sequential physical models:
    
    1. **Energy balance** — decompose kinetic energy lost per braking event
       into drag, rolling resistance, engine braking, and brake-friction
       components.
    2. **Thermal model** — lumped-capacity disc with convective and radiative
       cooling, integrated over the lap to find a self-consistent steady-state
       thermal cycle.
    3. **Wear model** — mechanical (energy-proportional) + oxidative
       (Arrhenius) wear, integrated over the lap.
    
    Built for the 2026 F1 regulations specifically (50/50 hybrid power unit,
    redesigned brake architecture). Front brakes only in Phase 1a; rear brakes
    with MGU-K regen split deferred to Phase 1b.
    """)


# ── Load the selected session ─────────────────────────────────
try:
    with st.spinner(f"Loading {year} {gp} {sess}..."):
        r = load_session_result(year, gp, sess)
except Exception as e:
    st.error(f"Failed to load {year} {gp} {sess}: {type(e).__name__}: {e}")
    st.info("Possible causes: session doesn't exist yet, GP name typo, "
            "or transient FastF1 issue.")
    st.stop()


# ── Headline ──────────────────────────────────────────────────
st.header(f"{r['year']} {r['gp']} — {r['session_type']} — {r['driver']} ({r['team']})")
st.caption(
    f"Lap time: {r['lap_time_s']:.3f}s  ·  "
    f"Air: {r['T_air_C']:.1f}°C  ·  Track: {r['T_track_C']:.1f}°C  ·  "
    f"Compound: {r['compound']}"
)


# ── Top-line metrics ──────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Mean disc T", f"{r['T_mean_C']:.0f} °C")
c2.metric("Peak disc T", f"{r['T_max_C']:.0f} °C")
c3.metric("Wear per disc", f"{r['wear_total_mg_per_disc']:.1f} mg")
c4.metric("Braking events", f"{r['n_events']}")


# ── Plot 1: temperature over the lap ──────────────────────────
st.subheader("Disc temperature along the lap")

fig, ax = plt.subplots(figsize=(12, 4))
ax.plot(r['dist_lap_m'], r['T_disc_C'], color='crimson', linewidth=1.4)
for ev in r['events']:
    ax.axvspan(r['dist_lap_m'][ev['start_idx']],
                r['dist_lap_m'][ev['end_idx']],
                color='crimson', alpha=0.12)
ax.axhline(200, color='gray', linestyle='--', alpha=0.5, linewidth=1)
ax.axhline(1000, color='gray', linestyle='--', alpha=0.5, linewidth=1)
ax.set_xlabel('Distance along lap (m)')
ax.set_ylabel('Front disc temperature (°C)')
ax.grid(True, alpha=0.3)
st.pyplot(fig)
st.caption(
    "Shaded = braking events. Dashed lines = carbon-carbon operating window "
    "(200-1000°C). Trace shown is steady-state (iterated until the lap returns "
    "to its starting temperature within 1K)."
)


# ── Plot 2: per-event energy ──────────────────────────────────
st.subheader("Front-axle brake energy per event")

events_df = pd.DataFrame([{
    'event': ev['event_id'],
    'dist_m': ev['dist_start_m'],
    'duration_s': ev['duration_s'],
    'E_brake_front_kJ': ev['E_brake_front_J'] / 1000,
} for ev in r['events']])
events_df = events_df.sort_values('E_brake_front_kJ', ascending=True)

fig2, ax2 = plt.subplots(figsize=(12, max(3, 0.4 * len(events_df))))
ax2.barh([f"#{e}" for e in events_df['event']],
          events_df['E_brake_front_kJ'],
          color='steelblue', alpha=0.85, edgecolor='black')
ax2.set_xlabel('Front-axle brake energy per event (kJ)')
ax2.set_ylabel('Event')
ax2.grid(True, alpha=0.3, axis='x')
st.pyplot(fig2)
st.caption(
    "Per-event energy reaching the front discs after subtracting drag, "
    "rolling resistance, engine braking, and rear-bias share."
)


# ── Multi-track comparison ────────────────────────────────────
st.subheader("Cross-track comparison")
st.caption(
    "All six precomputed 2026 Q sessions overlaid (steady-state pole laps). "
    "Distance normalized to lap fraction."
)

all_results = []
for s in PRECOMPUTED_SESSIONS:
    try:
        all_results.append(load_session_result(*s))
    except Exception:
        pass

if len(all_results) >= 2:
    fig3, ax3 = plt.subplots(figsize=(12, 5))
    colors = plt.cm.viridis(np.linspace(0, 1, len(all_results)))
    for r_other, color in zip(all_results, colors):
        d_norm = r_other['dist_lap_m'] / r_other['dist_lap_m'][-1]
        ax3.plot(d_norm, r_other['T_disc_C'], color=color, linewidth=1.2,
                  label=f"{r_other['gp']} ({r_other['T_air_C']:.0f}°C amb)")
    ax3.axhline(200, color='gray', linestyle='--', alpha=0.5)
    ax3.axhline(1000, color='gray', linestyle='--', alpha=0.5)
    ax3.set_xlabel('Lap fraction')
    ax3.set_ylabel('Front disc temperature (°C)')
    ax3.legend(loc='upper left', ncol=2, fontsize=9)
    ax3.grid(True, alpha=0.3)
    st.pyplot(fig3)


# ── Limitations ───────────────────────────────────────────────
with st.expander("⚠️ Limitations and honest caveats"):
    st.markdown("""
    **What's modeled well:**
    - Energy balance closes by construction
    - Disc temperatures fall in the published F1 operating range (200-1000°C)
    - Steady-state thermal cycle converges in ~4 iterations
    - Relative comparisons across tracks and events are defensible
    
    **What's not validated:**
    - **Absolute wear** is 1-2 orders of magnitude lower than reported real F1
      wear (~0.1 µm/lap vs ~15-50 µm/lap). The wear coefficients need
      recalibration against real measurements, which aren't publicly available.
    - **Cooling parameter (h_eff_0)** is the single largest source of
      uncertainty; absolute temperature levels are roughly matched to
      published F1 data but the calibration is implicit, not measured.
    - **Brake bias** assumed fixed at 56% front; drivers adjust in reality.
    - **Engine braking** modeled as constant; reasonable at high speed,
      weaker at coast phases.
    - **No race-condition data** yet: fuel-mass evolution and multi-lap
      thermal accumulation are Phase 1b targets.
    
    **What's structurally untested:**
    - The model predicts a regime flip from mechanical-dominated wear to
      oxidative-dominated wear at higher disc temperatures. None of the
      available 2026 Q sessions reach that regime, so this prediction is
      not yet falsifiable from data.
    
    **What's Phase 1b:**
    Race-condition data, multi-lap thermal accumulation, calibration against
    real F1 wear, rear-brake analysis with MGU-K regen split as a second
    hidden state.
    """)

st.divider()
st.caption(
    "Phase 1a — front brakes only, qualifying only. "
    "Built with FastF1, NumPy, SciPy, Matplotlib, Streamlit."
)
