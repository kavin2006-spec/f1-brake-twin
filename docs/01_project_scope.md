# Telemetry-Based Hidden Degradation State Estimation for 2026 Formula 1 Front Brakes

**Document type:** Project scope and concept definition
**Phase:** 1a — Front brakes (clean physics, no regenerative braking)
**Status:** Draft v1, for review
**Last updated:** 2026-06-14

---

## 1. Project overview

The 2026 Formula 1 regulations introduce the largest power unit and chassis change since the start of the hybrid era. Combustion power is reduced to roughly 400 kW, the MGU-K is uprated to 350 kW, and the resulting near-50/50 hybrid split has fundamentally reshaped how cars decelerate. Rear braking is now a blend of regenerative and friction braking managed by a brake-by-wire system; rear discs have shrunk significantly. Front braking, in contrast, remains purely hydraulic friction.

This project investigates whether the hidden mechanical state of the front brake disc — its temperature evolution and accumulated wear — can be estimated from publicly available kinematic telemetry alone, using a hybrid model that combines first-principles physics with data-driven correction.

Phase 1a addresses the front brake because the absence of regenerative braking on the front axle gives the cleanest possible physics chain. Phase 1b will extend the same framework to the rear axle, where the friction/regen split becomes an additional hidden variable.

---

## 2. Research question

> Can a hybrid physics and data-driven digital twin estimate the hidden thermal and wear states of front brake discs in 2026-specification Formula 1 cars using only publicly available kinematic telemetry?

Three sub-questions follow:

1. How accurately can a first-principles physics model alone reconstruct the per-event braking energy and disc thermal response?
2. Does augmenting the physics model with a data-driven correction layer measurably improve consistency with observable proxies (lap-time stability, sector trends, qualitative track-dependent behavior)?
3. Under what conditions does the hybrid approach fail or become unreliable, and what would be required to close those gaps?

---

## 3. Scope

### 3.1 In scope (Phase 1a)

- 2026-specification single-seater (generic, regulation-derived parameters)
- Front brake disc only (left/right modeled identically; not differentiated)
- Carbon-carbon disc material
- Estimation targets:
  - Per-event braking energy absorbed by the front axle
  - Disc bulk temperature over time
  - Cumulative wear (modeled, not measured)
- Public telemetry sources only (FastF1)
- Race and qualifying session analysis at the lap and event level

### 3.2 Explicitly out of scope (deferred or excluded)

| Item | Status | Reason |
|---|---|---|
| Rear brakes | Phase 1b | Adds regen/friction split as second hidden state |
| Battery degradation | Phase 2 | Different physics, no data exposed |
| Gearbox wear | Phase 2 | Different physics |
| Suspension/tire fatigue | Excluded | Out of project domain |
| Multi-component decision layer | Phase 2 | Requires Phase 1 outputs first |
| Aerodynamic load on brake cooling | Simplified | Modeled as average forced convection |
| Brake bias dynamics within a corner | Simplified | Modeled as fixed bias per stint |
| Driver-to-driver style differences | Out of scope for v1 | May add if results are stable |
| Team-specific brake geometry | Excluded | Generic regulation-derived spec |
| Wet conditions | Excluded for v1 | Adds confounding variables; revisit later |

---

## 4. System definition

### 4.1 Subject vehicle: generic 2026 F1 car

Parameter values are derived from the 2026 FIA Technical Regulations and publicly available Brembo specifications. Where teams differ, the value used is the regulatory minimum or a stated typical value.

| Parameter | Value | Source / note |
|---|---|---|
| Minimum dry car mass | 768 kg | 2026 regs |
| Driver mass (assumed) | 80 kg | Standard assumption |
| Race-start fuel mass | TBD (~80–100 kg) | To pin down |
| ICE peak power | 400 kW | 2026 regs |
| MGU-K peak power | 350 kW | 2026 regs |
| Front disc diameter | 330 mm (modeled) | Brembo: 325–345 mm allowed |
| Front disc thickness | 32 mm (modeled) | Brembo: max 34 mm |
| Front disc mass | 2.0 kg | Brembo published value |
| Disc material | Carbon-carbon | Regulation |
| Disc operating temperature window | 150–1000+ °C | Brembo published range |
| Brake bias (front) | 55–58% (assumed fixed per stint) | F1 typical; not in telemetry |
| Frontal area (estimate) | 1.4–1.5 m² | TBD, from literature |
| Drag coefficient | TBD | Active aero complicates; estimate average |
| Rolling resistance coefficient | TBD | Literature value |

Values marked TBD will be pinned down in the parameter-derivation step before coding the physics model. Each will get its own short justification note.

### 4.2 Hidden states

The states we estimate are not present in any telemetry feed:

- $T_{\text{disc}}(t)$ — bulk disc temperature
- $W(t)$ — cumulative material loss / wear depth
- $E_{\text{brake,front}}(t)$ — front-axle friction-brake energy per event

### 4.3 Observable inputs (FastF1)

- Speed (km/h) — high-frequency
- Throttle (%) — high-frequency
- Brake (boolean) — high-frequency
- Gear (integer) — high-frequency
- RPM — high-frequency
- X, Y, Z position — high-frequency
- Lap and sector times
- Weather: air temperature, track temperature, humidity, wind speed/direction
- Tire compound (per stint)
- Pit stops

### 4.4 Confirmed unavailable

- All ERS / MGU-K signals (deployment, harvest, battery SoC)
- DRS status (deprecated in favor of unexposed active aero)
- Brake pressure, brake bias, brake temperature
- Steering angle, G-forces (must be derived)

---

## 5. Energy balance framework

For each braking event, the change in vehicle kinetic energy is distributed among several dissipation mechanisms. For front-brake-only Phase 1a (i.e., considering the front-axle share):

$$
\Delta E_{\text{kin}} = E_{\text{drag}} + E_{\text{roll}} + E_{\text{eng,brake}} + E_{\text{brake,total}}
$$

with

$$
E_{\text{brake,front}} = \beta_{\text{front}} \cdot E_{\text{brake,total}}
$$

where:

- $\Delta E_{\text{kin}} = \tfrac{1}{2} m (v_1^2 - v_2^2)$ — directly computable from FastF1 speed
- $E_{\text{drag}} = \int \tfrac{1}{2} \rho C_d A v^3 \, dt$ — modeled from speed and weather
- $E_{\text{roll}} = \int C_{rr} m g v \, dt$ — modeled
- $E_{\text{eng,brake}}$ — engine braking; modeled from RPM, gear, throttle-off
- $\beta_{\text{front}}$ — brake bias to the front axle (assumed constant per stint)

The thermal evolution of the disc is modeled as a lumped-capacity body with forced-convection cooling:

$$
m_{\text{disc}} c_p \frac{dT_{\text{disc}}}{dt} = \dot{Q}_{\text{in}} - h(v) A_{\text{surf}} (T_{\text{disc}} - T_{\text{ambient}}) - \varepsilon \sigma A_{\text{surf}} (T_{\text{disc}}^4 - T_{\text{amb}}^4)
$$

where heat input is the braking energy distributed over the event duration, and the convective coefficient $h(v)$ depends on car speed (which drives cooling airflow). Radiation matters only at high temperatures but cannot be neglected for carbon-carbon above ~600 °C.

Wear is modeled with a temperature-dependent rate law of the form:

$$
\frac{dW}{dt} = k(T_{\text{disc}}) \cdot \dot{E}_{\text{brake,front}}
$$

The exact functional form of $k(T)$ will be selected during model development; carbon-carbon literature suggests an Arrhenius-like temperature dependence with a wear-rate minimum in the design operating window.

---

## 6. Data sources and limitations

### 6.1 Primary source

- **FastF1** (Python library, accessing the F1 live timing API)
- Coverage: 2018-present; 2026 data confirmed available from Australia GP onwards
- Availability: 30–120 minutes post-session
- Sampling rate: variable (multiple Hz, interpolated to uniform grid)

### 6.2 Known limitations

1. **No brake pressure** — only on/off boolean. Braking intensity must be inferred from deceleration.
2. **No ERS data** — relevant for Phase 1b but irrelevant for front-brake-only Phase 1a.
3. **No ground truth wear** — there is no public dataset of actual measured brake wear per race. Validation cannot be against measured wear; must rely on physics plausibility and qualitative checks.
4. **Limited 2026 sample** — only ~10 races of 2026 data exist as of the project start.
5. **Brake bias hidden** — driver-adjustable; will be treated as a stint-level constant.

### 6.3 Implication

This is fundamentally a hidden-state estimation problem, not a supervised regression problem. The model does not have wear labels to fit against. Validation must come from internal consistency, physics-plausibility checks, and behavior across known-distinct track types.

---

## 7. Modeling approach

Three model variants will be developed and compared:

### 7.1 Pure physics model

Implements the energy balance and thermal model from Section 5 directly. Parameters fixed from regulation and literature. No learned components. Serves as the baseline and as a sanity check.

### 7.2 Pure data-driven model

A regression / sequence model (e.g., LSTM or transformer over telemetry windows) trained to predict some observable proxy (e.g., lap-time variation, sector time evolution) that we expect to correlate with brake state. Used as a contrast, not as a deployment candidate.

### 7.3 Hybrid model

The physics model produces a structured prior. A learned residual model corrects systematic biases — accounting for effects not captured in the physics (e.g., cooling sensitivity to track orientation, secondary aero effects, driver-style influences). This is the primary candidate.

### 7.4 State estimator

A recursive estimator (initially a simple Kalman filter; later possibly an Extended Kalman Filter or particle filter) propagates the disc temperature and wear states over time, using the hybrid model as the process model and weather / observable lap behavior as measurement updates where applicable.

---

## 8. Key assumptions

These are explicit and will be revisited if results are sensitive to them.

1. The vehicle is treated as a point mass for kinematic energy calculations.
2. Aerodynamic drag is modeled with an average $C_d$; active aero variation is absorbed into model residual.
3. Left and right front brakes are identical.
4. Brake bias is constant per stint.
5. Engine braking contribution is modeled simply from RPM/gear, not from detailed engine maps.
6. The disc is treated as lumped-capacity (uniform temperature). Spatial gradients are ignored in v1.
7. Track and ambient conditions are read from FastF1 weather data and assumed uniform around the lap.
8. The car operates within regulatory mass minimums; fuel burn is approximated linearly over race distance.

---

## 9. Phase 1a deliverables

1. **Parameter derivation note** — short document fixing TBD parameter values with justification.
2. **Physics model module** (Python) — energy balance + thermal + wear, with unit tests.
3. **Hybrid model module** (Python) — physics + learned residual.
4. **State estimator module** (Python) — Kalman filter wrapping the dynamics.
5. **Validation notebook** — physics-plausibility checks, track-type behavior comparison, sensitivity analysis.
6. **Dashboard prototype** — estimated disc temperature, cumulative wear, confidence intervals, per-event energy breakdown.
7. **Technical report / paper draft skeleton** — assumptions, model structure, results, limitations, future work.

---

## 10. Project structure (proposed)

```
f1-brake-twin/
├── README.md
├── docs/
│   ├── 01_project_scope.md            # this document
│   ├── 02_parameter_derivation.md
│   ├── 03_research_findings.md
│   └── decisions/                     # ADR-style decision log
├── data/
│   ├── raw/                           # FastF1 cache
│   └── processed/                     # cleaned per-session datasets
├── src/
│   ├── physics/                       # energy balance, thermal, wear
│   ├── models/                        # ML / hybrid / state estimator
│   ├── telemetry/                     # FastF1 loaders, preprocessing
│   └── utils/
├── notebooks/
│   ├── 01_telemetry_exploration.ipynb
│   ├── 02_energy_balance_validation.ipynb
│   └── ...
├── dashboard/
├── tests/
└── pyproject.toml
```

Validation strategy is deferred to a separate decision (per project agreement).

---

## 11. Glossary

- **MGU-K** — Motor Generator Unit, Kinetic. The 2026 motor/generator that delivers and recovers electrical power at the rear axle.
- **ERS** — Energy Recovery System. The combined electrical recovery and deployment system.
- **Brake-by-wire** — Rear-axle braking system in which driver pedal input becomes a torque request blended between friction brakes and MGU-K regen.
- **Carbon-carbon (C/C)** — Composite material used for F1 brake discs and pads. Requires elevated temperature to develop friction.
- **Hidden state** — A physical quantity relevant to system behavior that is not directly measured by available sensors.
- **Digital twin** — A computational model that mirrors a physical system in real time, used here in its hybrid (physics + data) form.
- **FastF1** — Open-source Python library exposing F1 live timing and telemetry data.

---

## 12. References (initial)

- 2026 FIA Formula 1 Power Unit and Technical Regulations
- Brembo F1 technical publications (brakes, ventilation, 2026 rules)
- FastF1 documentation (docs.fastf1.dev)
- F1 official 2026 regulations explainer (formula1.com)
- Raceteq, Motorsport.com, The Race — for engineering commentary

A formal reference list will be maintained as the project develops.

---

## 13. Open questions for review

1. Are we comfortable treating the car as a point mass in Phase 1a, or do we want to model weight transfer to the front axle during braking? (Weight transfer would meaningfully increase front-brake energy and is not trivial.)
2. For brake bias: assume a fixed 56% front per stint, or treat as an unknown to be estimated?
3. Should the validation notebook include a comparison against 2025-spec cars to show how the 2026 changes manifest? (Could strengthen a paper.)
4. Dashboard: build minimal in Streamlit (fast, basic), or invest in something more polished (Dash/Plotly)?
