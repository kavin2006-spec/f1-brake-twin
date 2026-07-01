# F1 Brake Twin

**Hidden brake disc state estimation for 2026 Formula 1 cars.**

A hybrid physics digital twin that estimates front brake disc temperature and wear from public telemetry alone. Built for the 2026 F1 regulations (50/50 hybrid power unit, redesigned brake architecture).

## Live dashboard

[f1-brake-twin.streamlit.app](https://f1-brake-twin.streamlit.app)

## What this project does

Modern F1 brakes operate at over 800°C and wear by millimeters per race — but neither temperature nor wear is directly measurable in public data. This project estimates both from telemetry that FastF1 exposes (speed, throttle, brake on/off, gear, RPM, weather).

The pipeline runs three sequential physical models:

1. **Energy balance** — decompose kinetic energy lost per braking event into drag, rolling resistance, engine braking, and brake friction
2. **Thermal model** — lumped-capacity disc with convective and radiative cooling, integrated over the lap to find a self-consistent steady-state thermal cycle
3. **Wear model** — mechanical (energy-proportional) + oxidative (Arrhenius) wear, integrated over the lap

## Live dashboard

[Link will go here once deployed]

## What's been validated

- Energy balance closes by construction (drag/rolling/engine + brake = ΔKE)
- Disc temperatures fall in the published F1 operating range (200-1000°C)
- Steady-state thermal cycle converges in ~4 fixed-point iterations
- Pipeline produces consistent results across 6 different 2026 tracks
- Engineering insights surfaced: airflow > ambient temperature for cooling; event density > event severity for thermal accumulation

## What's not validated (yet)

- Absolute wear magnitudes are 1-2 orders of magnitude lower than reported real F1 wear; coefficients are calibration targets, not measured values
- The model's prediction of a mechanical → oxidative wear regime flip is not testable with available 2026 Q data (peak temperatures stay below the threshold)
- Race-condition data (fuel-mass evolution, multi-lap thermal accumulation) is Phase 1b
- Rear brakes with MGU-K regen split is Phase 1b

## Project structure

docs/ # Scope and parameter derivation documents

src/

physics/ # Energy balance, thermal, and wear modules

analysis/ # Pipeline that runs the full chain

utils/ # Physical constants

notebooks/ # 01-05: exploration, validation, multi-track analysis

tests/ # Unit tests (41 passing)

scripts/ # Precompute sessions for the dashboard

data/precomputed/ # Pickled pipeline results for known-good sessions

streamlit_app.py # Dashboard entry point

## Running locally

```bash
git clone https://github.com/yourusername/f1-brake-twin
cd f1-brake-twin
python -m venv venv
venv\Scripts\Activate.ps1   # Windows
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Status

Phase 1a (front brakes, qualifying, single-lap) complete. Phase 1b (race conditions, rear brakes, calibration) is in progress and tracks the 2026 season as races happen.

## Project documentation

- `docs/01_project_scope.md` — what we model, what we assume, what's deferred
- `docs/02_parameter_derivation.md` — every physical parameter with source and confidence tag

A technical paper is in preparation. Public links will appear here when published.

## Author

Kavin Sagar — 2nd-year Mechanical Engineering, HAN University of Applied Sciences
[LinkedIn link] · [Email]

## License

MIT
