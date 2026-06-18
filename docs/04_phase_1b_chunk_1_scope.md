# Phase 1b — Chunk 1: Race-Condition Extension

**Document type:** Project scope and approach
**Phase:** 1b, chunk 1 of estimated 3 (race conditions → state estimator OR rear brakes → final)
**Status:** Draft v1, for review
**Last updated:** 2026-06-17

---

## 1. Purpose and motivation

Phase 1a established the physics chain (telemetry → energy → temperature → wear) on single qualifying laps. The model produces physically plausible disc temperatures and internally consistent results across six tracks, but the practical engineering value of brake life modeling lives at the *stint* level, not the lap level. A driver's biggest concern is whether their brakes will last 30 laps, not whether one push lap is well-modeled.

The Phase 1a multi-track work also surfaced a model prediction that we could not test with the available data: the wear regime should flip from mechanical-dominated to oxidative-dominated above ~900°C disc temperature. Qualifying laps don't reach that threshold. Race conditions plausibly do, due to multi-lap thermal accumulation and the heavier (fuel-laden) car producing more brake energy per event.

This chunk of Phase 1b extends the pipeline to handle race sessions: multi-lap analysis, fuel-mass evolution, stint structure (pit stops break thermal continuity briefly), and lap-by-lap integration. The deliverable is a model that produces *stint-level* brake state evolution from public race telemetry, with the regime-flip prediction either confirmed or refuted from data.

---

## 2. Research questions

**Primary:**

> Does the regime-flip hypothesis (oxidative wear overtaking mechanical wear above ~900°C disc temperature) manifest in 2026 F1 race conditions, given multi-lap thermal accumulation and fuel-laden car mass?

**Secondary, in order of importance:**

1. How does disc temperature evolve over a race stint? Does it reach a quasi-steady cycle after a few laps, or does drift continue throughout?
2. How does fuel-mass burn-down affect brake energy and thermal response across the race?
3. What is the predicted per-stint wear, and how does it compare to qualifying-lap predictions extrapolated naively?
4. Are there observable signatures in the lap-time data that correlate with predicted disc thermal state? (This question pre-positions the state estimator decision in chunk 2.)

---

## 3. Scope

### 3.1 In scope

- Single race session analysis per run (e.g., Monaco 2026 R, all 78 laps, one selected driver)
- Front brake only (rear remains Phase 1b chunk 3)
- Multi-lap thermal and wear integration with fuel-mass evolution
- Stint segmentation (pit stops break thermal continuity)
- Lap-by-lap result aggregation (per-lap energies, per-lap temperatures, per-stint wear)
- Cross-driver comparison within one race (does the model differentiate driving styles?)
- Race-vs-qualifying comparison at the same circuit (does race steady-state differ meaningfully from qualifying single-lap?)

### 3.2 Explicitly out of scope (for this chunk)

| Item | Status | Reason |
|---|---|---|
| Rear brakes | Phase 1b chunk 3 | Different physics; second hidden state |
| State estimator (Kalman filter) | Phase 1b chunk 2 (or later) | Decision deferred to diagnostic review |
| Hybrid ML correction layer | Later | Requires meaningful observable proxy |
| Wear coefficient recalibration | Later | Requires ground truth |
| Safety car / VSC modeling | Mostly excluded | Excluded laps with track status != normal; not modeled positively |
| Driver-style modeling | Excluded | Driver name is a covariate, not a model |
| Tire-brake coupling | Excluded | Tire degradation is a separate problem |
| Weather evolution during race | Excluded for v1 | Use session-mean weather; revisit if results show systematic drift |
| Active aerodynamics state | Excluded | Z-mode assumed; would matter for tracks not currently in scope |
| Multi-race aggregation | Later | One race at a time first |

---

## 4. New physics required

### 4.1 Fuel-mass evolution

The car mass decreases monotonically across the race as fuel burns. 2026 regulations reduced maximum race fuel load to approximately 70 kg (down from ~110 kg in previous eras) due to higher hybrid contribution and active aero. Per-lap fuel consumption is approximately 0.8-1.0 kg/lap depending on circuit and strategy.

Model: linear interpolation from race-start mass to race-end mass over the race distance.

$$
m_{car}(\text{lap}) = m_{dry} + m_{driver} + m_{fuel,start} - \frac{m_{fuel,start} - m_{fuel,end}}{N_{laps,race}} \cdot \text{lap}
$$

Race-end fuel is non-zero by regulation (minimum sample at scrutineering); assume ~3 kg.

This affects:
- Kinetic energy: ΔKE scales linearly with mass; 7% reduction over a race
- Rolling resistance and engine braking forces: also scale with mass
- Aerodynamic drag: unchanged (mass-independent)

**Implication:** late-race braking events absorb less energy than early-race events for the same speed change.

### 4.2 Lap-by-lap integration without steady-state iteration

Phase 1a used fixed-point iteration to find a self-consistent single-lap thermal cycle. Race analysis cannot use this trick because every lap has different conditions (fuel, tire age, fluid conditions). The race model integrates forward through the entire race from an assumed initial condition.

**Initial condition:** brakes warmed by formation lap and grid hold; estimated 300-400°C at race start. This is a parameter we accept as uncertain in absolute terms but largely forgotten after ~3 laps because of the disc's thermal time constant (~36 s) vs lap duration (~80 s).

**Stint handling:** pit stops break thermal continuity for ~2-3 seconds (we exclude the in-lap and out-lap from continuous integration and treat each stint as its own integration window, with the first lap of each stint starting at the disc temperature at the moment of pit entry minus a parameterized cool-down).

### 4.3 Lap segmentation and filtering

Not every race lap is usable. We exclude:

- Laps under safety car or VSC (track status flags from FastF1)
- In-laps and out-laps (different brake usage patterns; the car is also unloading/loading mass at the pit stop)
- The first racing lap (lap 1) if it includes the standing start (brake behavior dominated by initial acceleration, not steady racing)
- Any lap with a yellow flag affecting the driver
- Any lap where telemetry has gaps (FastF1 may have missing samples)

Filtering happens *before* integration; we never integrate through a known-bad lap.

---

## 5. Data sources and limitations

### 5.1 What FastF1 provides for race sessions

Same channels as qualifying: Speed, Throttle, Brake (boolean), Gear, RPM, X/Y/Z position, lap/sector times, weather, tire compound, pit stops. Additionally:

- Track status messages (yellow flag, safety car, VSC, red flag)
- Lap-by-lap tire age
- Stint number

Race telemetry is ~7.5 Hz, same as qualifying. Total samples per race: ~78 laps × 80 s × 7.5 Hz ≈ 47,000 samples per driver per race. Manageable.

### 5.2 Specific race limitations

1. **No fuel mass telemetry.** We model fuel burn linearly; deviations from linear consumption (e.g., fuel-saving stints) are not captured.
2. **No tire pressure or temperature telemetry.** Affects rolling resistance, not modeled.
3. **No brake bias telemetry.** Still treated as constant 0.56; drivers do adjust during a race.
4. **No DRS data for 2026.** Active aero is not telemetered. We treat the car as continuous Z-mode (high downforce) — this is more wrong on high-speed circuits, but Monaco specifically runs Z-mode essentially the entire race.

---

## 6. Modeling approach

### 6.1 Pipeline architecture

A new module `src/analysis/race_pipeline.py` (or extension of the existing `pipeline.py`) that:

1. Loads a full race session
2. For each clean racing lap, runs the energy decomposition and thermal model
3. Integrates wear continuously across the race (with stint breaks)
4. Returns a structured result with per-lap and per-stint summaries

The single-lap pipeline `run_session` stays intact for qualifying analysis; the race pipeline calls into the same physics modules.

### 6.2 Thermal integration across the race

```
Initial T_disc → integrate lap 1 → integrate lap 2 → ... → integrate lap N
                  ↓ (record per-lap stats)
                  ↓ (handle pit stops as discontinuity)
```

No iteration to steady state. The disc temperature trace is whatever the model produces. If it converges to a quasi-steady cycle, that's a finding. If it drifts, that's also a finding.

### 6.3 Wear accumulation

Wear is cumulative across the entire race (not reset between laps or stints). Final wear is the integral of the wear rate over all racing laps. Per-stint wear is reported as a derived metric.

### 6.4 Validation strategy

No direct ground truth. Validation comes from:

- **Monotonicity:** wear must accumulate monotonically; disc temperature should reach quasi-stable cycle.
- **Physics plausibility:** disc temperature in carbon-carbon operating range; no negative values; energy balance closes per lap.
- **Cross-session consistency:** the per-lap wear rate from race lap N should be roughly comparable to a qualifying-lap estimate scaled appropriately.
- **Engineering plausibility:** total race wear estimate should be in the same order of magnitude as published F1 wear figures (15-50 µm/lap), even if our absolute coefficients are uncalibrated.

---

## 7. Key assumptions

1. Vehicle mass evolution is linear in lap number from race-start fuel to race-end fuel. Realistic deviations (fuel-saving stints, varied pace) are absorbed into per-lap variability.
2. The disc cools by ~50°C during a pit stop (engine off, no airflow, but only ~3 seconds). This is a guess and a candidate for sensitivity analysis.
3. Race-start disc temperature is 350°C (warmed up by formation lap, cooled slightly while on grid).
4. Brake bias remains 0.56 throughout the race.
5. Engine braking $a_{eng}$ remains constant; reasonable since engine maps don't change dramatically in a race.
6. The lumped convective conductance $h_{eff,0}$ is the same value calibrated in Phase 1a (72 W/K at $v_0$).
7. Wear coefficients are the same L-confidence values from Phase 1a; absolute magnitudes will remain ~1-2 orders of magnitude low.

---

## 8. Deliverables

1. **Scope document** — this document.
2. **Parameter doc extension** — new race-specific parameters (fuel masses, race-start disc temp, pit-stop cool-down) added to `02_parameter_derivation.md` §6.
3. **Code module** — race pipeline that returns per-lap and per-stint results.
4. **Unit tests** — for fuel-mass evolution, lap filtering, stint segmentation.
5. **Notebook 06** — Monaco 2026 race analysis: full-race temperature trace, lap-by-lap evolution, per-stint wear, regime-flip diagnostic.
6. **Notebook 07** — race-vs-qualifying comparison and cross-driver comparison within the same race.
7. **Diagnostic write-up** — short markdown summarizing what race conditions actually look like in the model and what it tells us about chunk 2 priorities (state estimator vs rear brakes).

---

## 9. Open questions for review

These need decisions before we start writing code:

1. **Which driver?** For the Monaco race specifically, do we analyze the winner (ANT) for narrative cleanness, or do we pick someone running a different strategy (e.g., a one-stopper) for richer telemetry variability? Both? My instinct: ANT for v1, second driver in notebook 07 for cross-comparison.

2. **Race-start fuel mass — fix at 70 kg or treat as a parameter?** 2026 regulations limit max fuel but actual race-start mass varies by circuit (longer races carry more). For Monaco 78 laps × ~0.9 kg/lap = ~70 kg. For Spa (44 laps) ~40 kg. We could either hard-code per circuit or use a heuristic from race length. Heuristic feels cleaner.

3. **Pit-stop cool-down — model or ignore?** Pit stops are ~2.5 seconds. At quasi-steady cycle temperatures (~700°C disc, ~300 K ambient, no airflow), how much does the disc cool in 2.5 seconds? Order-of-magnitude calculation: with no airflow, h_eff drops by ~99%, so cooling is almost entirely radiation. Radiation at 700°C ≈ 1 kW per disc. Heat capacity 2600 J/K. So ~0.4 K/s — about 1°C lost in 2.5 seconds. Negligible. **Recommendation: ignore the pit-stop cool-down. The dominant effect of a pit stop is the new-tire/new-driver-state discontinuity, not the brief cooling.**

4. **What counts as a "stint" for wear reporting?** Strictly: between pit stops. But the first lap (standing start) and last lap (likely VSC/checkered flag pace) are atypical. Do we report stint wear as "stint excluding bookend laps" or "all laps in the stint"? My instinct: all laps in the stint, with bookend laps flagged separately if needed.

5. **First-lap handling — exclude or include?** Lap 1 of a race starts with a standing-start acceleration and is then followed by racing laps. The launch is irrelevant to brakes, but the race-pace portion is. We could either skip lap 1 entirely or include it with a flag noting that race-start dynamics dominate the first ~30 seconds. Excluding seems simpler.

6. **Notebook 06 scope — Monaco only, or Monaco + one other race?** Monaco is the most thoroughly analyzed track from Phase 1a. Adding a second race (Australia or Canada) would generalize findings but doubles the work. My instinct: Monaco only for chunk 1, others added if time and findings warrant.
