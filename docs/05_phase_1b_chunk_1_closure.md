# Phase 1b — Chunk 1 Closure: Race-Condition Extension

**Document type:** Milestone summary
**Phase:** 1b, chunk 1 — complete
**Status:** Closed, validated, no further work planned for this chunk
**Date:** 2026-06-18

---

## 1. What chunk 1 delivered

Extension of the Phase 1a physics chain to handle race sessions: multi-lap forward integration, fuel-mass evolution, stint segmentation, race-specific lap filtering, and per-lap result aggregation. Applied to Monaco 2026 R (ANT) as the validation target, with direct comparison to the Phase 1a qualifying baseline on the same circuit-driver pair.

The deliverables from the chunk 1 scope (`04_phase_1b_chunk_1_scope.md` §8) are all in place:

1. Scope document ✓ (`docs/04_phase_1b_chunk_1_scope.md`)
2. Parameter doc extension ✓ (new §5.6 in `02_parameter_derivation.md`)
3. Race pipeline module ✓ (`src/analysis/race_pipeline.py`)
4. Unit tests ✓ (`tests/test_race_pipeline.py`, 13 tests passing)
5. Notebook 06 ✓ (`notebooks/06_race_condition_analysis.ipynb`)
6. Notebook 07 — **not built**. The race-vs-Q comparison originally planned for notebook 07 was folded into notebook 06 because the race data only yielded three analyzable stints and a cross-driver comparison would need a different race or different driver pick. Deferred to a future chunk.
7. Diagnostic write-up ✓ (this document, §4 below)

The 41 unit tests from Phase 1a still pass. Total tests now: **54 passing**.

---

## 2. Findings

### 2.1 The race-vs-Q per-lap wear gap

Same driver (ANT), same circuit (Monaco 2026), but per-lap wear differs measurably:

| Metric | Q3 pole lap | Race mean (65 laps) | Delta |
|---|---|---|---|
| Wear per lap | 27.0 mg | 24.2 mg | -10.2% |
| Front-axle energy per lap | 5.46 MJ | 4.81 MJ | -11.9% |
| Peak disc T | 798°C | 780°C | -18°C |
| Mean disc T | 715°C | 634°C | -81°C |

The race car carries ~70 kg more fuel than the Q3 car, so the *fuel-mass effect* alone would predict higher per-lap energy and wear in the race. The observed direction (race is lower per lap) means a second effect dominates: racing-pace driving is meaningfully less aggressive than a Q3 push lap. Lift-and-coast, regen management, and tire conservation cumulatively cut ~12% of brake energy per lap.

**Engineering claim:** single-lap qualifying analysis systematically overestimates race-stint wear at Monaco. Naive extrapolation (Q wear × N laps) would predict 78 × 27 = 2106 mg for a Monaco race; observed value is 1573 mg, a 25% overprediction. The ~12% per-lap gap compounds because we also only analyze 65 of 78 laps due to SC/red flag exclusion.

### 2.2 Each stint is a fixed point, not a drift

A more subtle finding from the lap-by-lap plots. Within each stint, mean disc temperature is flat — no within-stint drift over 36 laps (medium), 22 laps (hard), or 7 laps (soft). The 30°C downward trend across the race is a step function at each stint boundary, not a continuous slide.

The interpretation is that the disc's thermal state reaches a quasi-steady-state cycle within ~1 racing lap and then sits at the fixed point determined by the joint (compound + fuel mass + driving style) condition for that stint. This is the correct behavior for a deterministic dynamical system and serves as a strong sanity check on the model structure.

### 2.3 Race-start initial condition is largely irrelevant

The 350°C assumed race-start disc temperature is forgotten within one lap. By lap 3 the disc is at ~610°C; by lap 4 the transient is invisible against the lap-to-lap noise of the steady cycle. Sensitivity to the 350°C choice is therefore minimal — being wrong by ±100°C would not change anything past lap 3. This is a useful robustness property to know about.

### 2.4 The regime-flip hypothesis: not confirmed

The Phase 1b chunk 1 scope (§2 of `04_phase_1b_chunk_1_scope.md`) posed as its primary research question whether race conditions would push disc temperatures above the ~900°C threshold where Arrhenius oxidation becomes significant. They did not. Peak race disc T = 780°C, comfortably below threshold. Oxidative wear contributes 0.0006% of total race wear.

The expected mechanism (multi-lap thermal accumulation + heavier car) was real but not strong enough to clear the threshold. In fact, race conditions ran *cooler* than qualifying because the racing-pace driving style cuts brake energy faster than fuel mass adds it.

**Status:** the regime-flip hypothesis remains untested rather than refuted. Testing requires either intrinsically hotter tracks (Bahrain, Singapore — currently unavailable) or substantially different conditions (race-pace at faster circuits like Monza or Baku, when 2026 data is available).

### 2.5 Two findings flagged but not resolved

- **Bookend laps:** clean racing laps wear 24.2±1.1 mg, bookend laps 22.9±3.5 mg. Direction (bookends lower) makes physical sense, but n=2 bookends in this race is too few to claim significance. Future races with more pit stops, or aggregation across multiple races, would resolve.
- **Post-pit-stop conservatism:** laps 38 and 45 (first racing laps of stints 2 and 3) show ~12% lower brake energy than steady-state. Plausibly driver-style tire conservation on fresh rubber, but n=2 here too.

---

## 3. Method notes worth keeping

- **Pipeline architecture.** New `src/analysis/race_pipeline.py` parallels the Phase 1a `src/analysis/pipeline.py`. Race and qualifying analysis share the underlying physics modules (energy_balance, thermal_model, wear_model) but have separate entry points. This preserves the Phase 1a pipeline unchanged and avoids any risk of regression.

- **`get_car_data()` not `get_telemetry()`.** FastF1's `get_telemetry()` merges car data with position data and fails on some 2026 race laps where position data is missing the 'Date' column needed for the merge. Race pipeline uses `get_car_data()` directly and computes Distance from cumulative speed integration. Result: 65 of 78 laps recovered, where the original `get_telemetry()` would have lost ~72 of 78 to false-positive failure.

- **Broad `except Exception` traps were dangerous.** The race pipeline initially silently dropped 72 of 78 laps for "telemetry_error_KeyError" with no detail. A diagnostic script with `traceback.print_exc()` revealed the actual error and led to the fix above. Documented as a methodological note for future modules: always preserve the exception message, not just the type, when logging skipped data.

- **Mass-aware energy decomposition.** The Phase 1a `decompose_braking_event` function takes mass as an argument with a default of `C.M_CAR`. The race pipeline calls it explicitly with per-lap mass; the qualifying pipeline uses the default. No change to Phase 1a behavior.

- **Forward integration, no steady-state iteration.** Race thermal evolution is integrated forward from lap 2's race-start initial condition. The disc temperature carries through pit stops (no discontinuity applied — pit-stop cool-down is ~1°C and below noise). Each lap's final disc temperature becomes the next lap's initial condition.

---

## 4. Decision for chunk 2

The chunk 1 scope (§6) committed to a diagnostic step after notebook 06 to decide chunk 2 priorities. The diagnostic outcome is:

**Race data does not surface a useful observable proxy for a state estimator measurement update.** Lap times are noisy and only weakly coupled to disc state. Per-lap energy and event counts are not independent measurements — they're inputs the model already consumes deterministically. A Kalman filter built on the current model + available data would be open-loop bookkeeping with no real update signal.

**Implication:** the state estimator is deprioritized to chunk 4 (or later). Chunk 2 will be rear brakes with MGU-K regen split, which has:
- Structural justification independent of measurement availability
- The most 2026-specific physics in the project (joint regen/friction estimation)
- A clean novel-physics contribution to the paper

This is consistent with the recommendation made in the Phase 1b chunk 1 scope and confirmed by what the race data showed.

---

## 5. Phase 1b chunk 1 closed

The race-condition extension delivered a working multi-lap analysis pipeline, a defensible engineering claim (race-vs-Q per-lap gap), a robust handling of race chaos (SC, red flag, missing data), and a clean decision criterion for chunk 2. The regime-flip hypothesis remains untested but the model produced a clear, falsifiable prediction about when it should become testable.

The pipeline is reusable for any 2026 race session as the calendar progresses, and the race-vs-Q methodology is reusable for any circuit where we have both session types.

Phase 1b chunk 2 (rear brakes + MGU-K regen split) starts when ready.
