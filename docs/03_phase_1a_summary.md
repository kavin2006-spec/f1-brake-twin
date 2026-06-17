# Phase 1a Closure: Front Brake Hidden State Estimation

**Document type:** Milestone summary
**Phase:** 1a — complete
**Status:** Closed, validated, deployed
**Date:** 2026-06-17

---

## 1. What Phase 1a delivered

A working physics digital twin that estimates two unobservable physical states — front brake disc temperature and wear — from public 2026 F1 telemetry alone, validated across six sessions and deployed as an interactive dashboard.

The full chain runs end-to-end:

```
Public telemetry (FastF1)
    → Event detection & filtering
    → Energy balance decomposition  (ΔKE − drag − rolling − engine = brake energy)
    → Thermal model integration     (lumped-capacity ODE, steady-state iteration)
    → Wear model integration        (mechanical + oxidative, lap-integrated)
    → Per-disc temperature trace + wear estimates
```

Every step is tested, documented, and parameter-sourced.

---

## 2. Artifacts produced

### Code modules (`src/`)

| Module | Purpose | Public API |
|---|---|---|
| `src/utils/constants.py` | Single source of truth for all physical parameters | Constants imported by all other modules |
| `src/physics/energy_balance.py` | Per-event kinetic energy decomposition | `air_density`, `decompose_braking_event`, individual term functions |
| `src/physics/thermal_model.py` | Lumped-capacity disc thermal ODE + integrator | `build_input_power_per_disc`, `integrate_lap`, `h_eff`, `convective_loss`, `radiative_loss` |
| `src/physics/wear_model.py` | Mechanical + oxidative wear, lap-integrated | `integrate_wear_lap`, `mechanical_wear_rate`, `oxidative_wear_rate` |
| `src/analysis/pipeline.py` | End-to-end pipeline wrapping the chain | `run_session(year, gp, sess)` returns a complete result dict |

### Tests (`tests/`)

41 unit tests, all passing. Coverage includes analytical closed-form cases, scaling laws (e.g., drag scales with v³, mechanical wear scales linearly with energy), conservation properties (energy balance closes exactly by construction), and physical sanity bounds (rates non-negative, magnitudes in plausible ranges).

### Notebooks (`notebooks/`)

| Notebook | What it establishes |
|---|---|
| `01_telemetry_exploration` | FastF1 channels available for 2026; 12 braking events on Monaco pole lap; energy magnitudes; 6 events capture 80% of energy |
| `02_energy_balance_validation` | Per-event drag/rolling/engine/brake decomposition; 14.7% reduction from naive upper bound; 2.73 MJ per disc per lap at Monaco |
| `03_thermal_model_validation` | Steady-state disc temperature trace; peak 798°C at Monaco; late-lap accumulation finding (Rascasse > Nouvelle Chicane despite lower event energy) |
| `04_wear_estimation` | Per-lap wear breakdown; 27 mg per disc per lap at Monaco; mechanical regime confirmed at qualifying temperatures |
| `05_multi_track_validation` | Cross-track comparison over 6 sessions; airflow > ambient temperature for cooling; pipeline internal consistency confirmed (wear/MJ constant within 4%) |

### Documentation (`docs/`)

| Document | What it specifies |
|---|---|
| `01_project_scope.md` | What we model, what we assume, what is deferred. Decisions log with rationale. |
| `02_parameter_derivation.md` | Every physical constant with value, units, source, and confidence tag (H/M/L). |
| `03_phase_1a_summary.md` | This document. |

### Dashboard

- `streamlit_app.py` deployed to Streamlit Community Cloud
- Six precomputed sessions for instant exploration; custom sessions loaded live
- Includes honest limitations expander documenting what is and isn't validated
- Public URL for portfolio sharing

---

## 3. Engineering findings

Three findings emerged from the multi-track analysis that are specific enough to be defensible claims:

### 3.1 At qualifying intensity, airflow dominates ambient temperature for brake cooling

Miami at 34°C ambient produces a 477°C mean disc temperature. Monaco at 24°C ambient produces 715°C. The 240°C cooler discs at the hotter circuit are explained by Miami's high-speed flowing layout driving stronger convective cooling between events. The lumped convective conductance `h_eff(v)` model captures this without any track-specific tuning.

Engineering implication: brake cooling design optimization (duct geometry, vent hole pattern) has more leverage than thermal management strategy in hot ambient conditions.

### 3.2 Event density dominates event severity for thermal accumulation

Monaco and Canada absorb similar total front-axle energy per lap (2.73 and 2.60 MJ). Monaco's mean disc temperature is 120°C higher, because Monaco's 12 braking events leave less recovery time between heat inputs than Canada's 6 events. Heat stacks faster than it dissipates.

Engineering implication: peak temperature is set by event clustering, not by the single highest-energy braking event. This argues for cooling design optimized for the worst late-sector cluster, not the worst individual event.

### 3.3 Phase 1a temperature regime is mechanical-wear dominated; the predicted regime flip is not testable with available 2026 data

The wear model predicts that oxidative wear (Arrhenius-driven) overtakes mechanical wear (energy-proportional) above approximately 900°C disc temperature. None of the six 2026 Q sessions reach that threshold; peak temperatures range from 330°C (Miami) to 798°C (Monaco). The model's structural claim about regime crossover remains internally consistent (the Arrhenius mathematics produces it) but is not falsifiable from currently available data.

This is logged as a Phase 1b target requiring either race-condition data (longer thermal soak, higher mean temperatures) or higher-stress upcoming tracks.

---

## 4. Methodological notes

Several decisions made during Phase 1a deserve documenting for future reference, in case they need to be revisited:

**Lumped convective conductance.** `h_eff(v)` combines the heat transfer coefficient and effective cooling area into a single calibration parameter, on the grounds that the two are jointly unidentifiable from available data. Disentangling them would require independent measurement of either quantity, which we do not have. This is the single largest source of model uncertainty in absolute thermal predictions.

**Point-mass vehicle.** Weight transfer to the front axle during heavy braking is not modeled. This is a known systematic bias toward underestimating front-axle energy in the largest braking events. The aggregate effect across the lap is small but the per-event bias on the biggest stops is real. Documented; not corrected in v1.

**Fixed brake bias.** Front bias held at 0.56 across all sessions and events. Drivers adjust bias in reality. Phase 1a.5 enhancement (mentioned in scope document) would estimate bias as a slowly-varying state.

**Wear coefficients uncalibrated.** Absolute wear is approximately 1-2 orders of magnitude smaller than reported real F1 wear. The model's *relative* predictions (track-to-track, event-to-event, mechanism-to-mechanism) are defensible; the absolute "mm per stint" is not. Recalibration against real wear data is Phase 1b.

**Forward Euler integration.** Stable here because the thermal time constant (~36 seconds) is much longer than the sample interval (~133 ms). If we ever extend to sub-event time resolution or stiffer dynamics, swap to `scipy.integrate.solve_ivp`.

**Trapezoidal integration of piecewise-constant pulses.** Produces a small (~1.3% on Monaco) integrated-vs-summed energy discrepancy due to edge artifacts when timestamps aren't perfectly uniform. The forward Euler integrator injects energy exactly correctly; the discrepancy is in the after-the-fact verification using trapezoid. Documented; not a model bug.

---

## 5. Quantitative results, Monaco 2026 Q pole lap (canonical reference)

For future cross-checking against any modifications:

| Quantity | Value |
|---|---|
| Lap time | 72.051 s (ANT, Mercedes) |
| Total ΔKE across braking events | 11.43 MJ |
| Drag dissipation | 1.37 MJ (12.0%) |
| Rolling resistance | 0.12 MJ (1.1%) |
| Engine braking | 0.19 MJ (1.6%) |
| Total brake energy | 9.75 MJ (85.3%) |
| Front-axle brake energy | 5.46 MJ |
| Per-disc brake energy | 2.73 MJ |
| Steady-state convergence | 4 iterations to ±0.8 K |
| Disc T minimum | 567°C (tunnel section, ~1950m) |
| Disc T mean | 715°C |
| Disc T maximum | 798°C (Rascasse, ~2844m) |
| Total wear per disc per lap | 27.0 mg (100% mechanical) |
| Thickness loss equivalent | 0.125 µm per face |

---

## 6. Deferred items (Phase 1b candidates)

In rough order of impact for the paper:

1. **Race-condition extension.** Multi-lap thermal accumulation, fuel-mass evolution, longer thermal time horizons. Tests the regime-flip prediction.
2. **Rear brakes with MGU-K regen split.** The 2026-specific physics that was the original motivation for choosing 2026 cars. Adds a second hidden state (regen fraction).
3. **Wear coefficient recalibration.** Pursue published F1 wear data or develop indirect calibration via observable proxies (tire wear stints, brake duct changes between sessions).
4. **State estimator wrapping.** Kalman filter or particle filter around the physics. Adds recursive estimation character expected of digital twins. Less paper-novel but standard.
5. **Hybrid data-driven correction layer.** Originally promised in scope. Methodologically tricky without ground truth; would need an observable proxy to train against.
6. **Multi-track X/Z-mode handling.** Active aerodynamics produces track-dependent drag coefficients. Needed for tracks with significant straightline mode use (Monza, Baku, Las Vegas).
7. **Brake bias as a slowly-varying hidden state.** Phase 1a.5 enhancement; identifiable from multi-lap data via observability arguments discussed in the scope doc.
8. **2025-spec comparison.** Stretch goal from the scope doc; strengthens the "2026-specific" paper narrative if added.

---

## 7. Phase 1a is closed

The scope document defined Phase 1a as front-brake-only, qualifying-only, generic 2026 car, Monaco initially. All of that is delivered. The model passes physics-plausibility checks, produces engineering insights that energy-balance-only analysis cannot, and is internally consistent across six independent sessions. The dashboard is live.

Phase 1a does not deliver a calibrated wear-per-stint number, a hybrid ML layer, or a state estimator. Those were either explicitly deferred (ML, state estimator) or were never claimed at the Phase 1a deliverable level (calibration). Phase 1b will take them in priority order to be decided next.
