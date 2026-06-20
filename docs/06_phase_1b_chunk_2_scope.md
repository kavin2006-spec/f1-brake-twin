# Phase 1b — Chunk 2: Rear Brakes with MGU-K Regen Split

**Document type:** Project scope and approach
**Phase:** 1b, chunk 2 of estimated 3 (race extension ✓ → rear brakes → final integration)
**Status:** Draft v1, for review
**Last updated:** 2026-06-18

---

## 1. Purpose and motivation

Phase 1a and 1b chunk 1 modeled only the front brakes. This was the deliberate Phase 1a scope decision: front brakes are purely friction-braked and have no regenerative coupling, giving the cleanest possible physics chain for the initial digital twin. Rear brakes in 2026 F1 cars are fundamentally different: they share braking duty with the MGU-K's regenerative braking, with the split determined by a brake-by-wire control system the car operates in real time.

This makes the rear brakes the most genuinely 2026-specific physics in the project. The 2026 power unit regulations (50/50 ICE/MGU-K split, 350 kW MGU-K, 4 MJ battery, 7 MJ/lap harvest cap) shape how the rear axle decelerates in ways that have no analog in pre-2026 cars. Modeling the rear axle correctly is the core "this is a 2026-specific contribution" claim of the project.

Critically: **we have no telemetry that tells us the regen/friction split**. The MGU-K's deployment and harvest signals are not exposed in FastF1. This means the regen fraction must be inferred from physics + constraints + a strategy assumption, and the rear friction energy (which drives rear thermal load and wear) becomes a second hidden state alongside disc temperature.

A diagnostic done before drafting this document (see `scripts/peak_power_check.py`) checked which of three candidate tracks would most actively exercise the MGU-K's constraints. Result: all three tracks bind the MGU-K's 350 kW power limit for roughly 4-5% of the lap, while none come close to the 7 MJ/lap harvest cap. **The MGU-K power limit is the only meaningfully binding constraint.** This simplifies the strategy model significantly — no battery state tracking or strategic lookahead is needed for chunk 2.

---

## 2. Research questions

**Primary:**

> Given the 2026 MGU-K constraints, how does the rear brake friction energy compare to the front friction energy at the same circuit, and what does this imply for rear vs front thermal load and wear?

**Secondary, in order of importance:**

1. What fraction of total rear-axle braking energy is absorbed by regenerative braking vs friction braking, averaged over a lap?
2. Are rear discs running hotter or cooler than front discs at the same circuit?
3. Does the rear-axle wear distribution across events match the front-axle distribution (same dominant events), or is it shifted by the regen filter?
4. How sensitive is the rear thermal/wear prediction to the 350 kW MGU-K limit? (Sensitivity analysis on the one parameter that actually shapes the regen/friction split.)

---

## 3. Scope

### 3.1 In scope

- Rear brakes (front-axle modeling unchanged)
- MGU-K regen modeled as a greedy instantaneous power cap
- Instantaneous regen/friction split computed at the telemetry sample rate
- Rear thermal model (same structure as front, different geometry)
- Rear wear model (same structure as front, same coefficients)
- Validation on Monaco 2026 Q (continuity with Phase 1a) and Monaco 2026 R (continuity with chunk 1)
- Direct rear-vs-front comparison at Monaco as the primary engineering finding

### 3.2 Explicitly out of scope (for this chunk)

| Item | Status | Reason |
|---|---|---|
| Battery state tracking | Excluded for v1 | Harvest cap (7 MJ/lap) does not bind on any analyzed track |
| MGU-K deployment modeling | Excluded for v1 | Affects brakes only indirectly via shared battery SoC; second-order effect not worth modeling before validating harvest-only behavior |
| Strategic regen lookahead | Excluded for v1 | Adds tuning parameters with no public source; revisit only if greedy v1 shows systematic shortfall |
| Battery SoC initial condition | Excluded for v1 | Not needed when battery never fills |
| MGU-H | Permanently excluded | Eliminated in 2026 regulations |
| Front-axle modifications | Excluded | Front model from Phase 1a unchanged |
| Multi-track rear comparison | Phase 1c | Validate at Monaco first, generalize across precomputed sessions only after rear model is trusted |
| Rear brake bias as separate hidden state | Excluded | Fixed at 0.44 rear (per Phase 1a precedent); revisit in a dedicated chunk |
| Brake-by-wire safety constraint (2500 Nm at 150 bar without PU) | Documented, not modeled | Regulatory; relevant for failure modes, not steady-state operation |

---

## 4. New physics required

### 4.1 Instantaneous power-based regen split

The model computes rear-axle braking power at each telemetry sample, not at the event level:

$$
P_{brake,rear}(t) = \beta_{rear} \cdot m \cdot a_{brake}(t) \cdot v(t)
$$

where $a_{brake}(t)$ is the deceleration *attributable to the brakes* — total deceleration minus drag, rolling resistance, and engine braking contributions at that instant. This is the rear-axle's share of the same physics already implemented in `energy_balance.py`, applied at the sample level rather than the event level.

The regen/friction split is then:

$$
P_{regen}(t) = \min(P_{brake,rear}(t), P_{MGU\text{-}K,max})
$$

$$
P_{friction,rear}(t) = P_{brake,rear}(t) - P_{regen}(t)
$$

Greedy: regen takes everything it can, friction takes the overflow. No strategy, no lookahead, no battery state.

The rear friction energy per event:

$$
E_{friction,rear,event} = \int_{event} P_{friction,rear}(t) \, dt
$$

This becomes the heat input to the rear thermal model.

### 4.2 Rear thermal model

Same structure as the front thermal model, different parameters. The rear disc is geometrically smaller (260-280 mm diameter vs 330 mm front per Brembo specs), thinner, and lighter. Less thermal mass means faster temperature response per unit energy. Cooling is also different: brake-by-wire architecture allows different duct routing on the rear, but in our model this collapses into a different $h_{eff,0}$.

Initial parameter assumptions:

- Rear disc diameter: 270 mm (mid of Brembo range)
- Rear disc thickness: 32 mm (same as front; max 34 mm by reg)
- Rear disc mass: 1.4 kg (proportional scaling from front 2.0 kg)
- Rear lumped convective conductance $h_{eff,0,rear}$: 60 W/K (slightly lower than front 72 W/K, reflecting reduced surface area; same velocity scaling exponent)

All four are M-confidence parameters. Sensitivity analysis on $h_{eff,0,rear}$ will be needed.

### 4.3 Rear wear model

Same as front. Same coefficients ($K_{mech}$, $K_{ox,0}$, $E_a$). The L-confidence calibration gap from Phase 1a carries forward: absolute rear wear magnitudes will be 1-2 orders of magnitude lower than reported real F1; relative comparisons remain defensible.

### 4.4 Diagnostic outputs needed

The model must surface:

- Per-event regen fraction (how much of each braking event's rear energy went to regen vs friction)
- Per-lap total regen energy (so we can sanity-check against the 7 MJ harvest cap and confirm it doesn't bind in race conditions either)
- Per-event peak rear braking power (so we can verify the 350 kW constraint is binding when expected)
- Rear vs front per-event energy comparison

---

## 5. Data sources and limitations

### 5.1 What FastF1 provides

Same channels as front-brake analysis: Speed, Throttle, Brake (boolean), Gear, RPM, X/Y/Z position, lap and sector times, weather, tire compound, pit stops.

### 5.2 What FastF1 does NOT provide (and we must work around)

1. **No MGU-K deployment or harvest data.** This is the entire reason regen is a hidden state.
2. **No battery SoC.** Not needed for chunk 2 (cap doesn't bind), but would be needed for a Phase 1c deployment-aware model.
3. **No brake pressure or bias data.** We assume fixed 0.44 rear bias.
4. **No active-aero state.** Rear aerodynamic load varies with downforce setting; we use fixed Z-mode at Monaco.

### 5.3 Implication for validation

We have no ground truth for rear disc temperature or wear, just as we had no ground truth for the front. Validation comes from:

- **Physics plausibility:** rear temperatures in carbon-carbon operating range, energy balance closes, regen fraction physically bounded (0-1).
- **Front vs rear consistency:** rear disc heat input should be lower than front by roughly (1 - regen_fraction) × (rear_bias/front_bias). If the model produces something wildly different we have a bug.
- **Constraint binding:** model should show MGU-K power limit binding in the same events identified by the diagnostic check (~5/12 events at Monaco Q).
- **No harvest-cap binding:** model should show per-lap regen energy comfortably below 7 MJ. If it doesn't, our greedy assumption is wrong.

---

## 6. Modeling approach

### 6.1 Module architecture

New module `src/physics/regen_model.py` (the strategy + power split). Modified or extended `src/physics/thermal_model.py` to handle rear disc parameters as a function argument rather than hard-coded constants — this lets the same `integrate_lap` function work for both front and rear by passing different parameters. Same for `wear_model.py` if it currently hard-codes disc geometry.

New module `src/analysis/rear_pipeline.py` parallel to `pipeline.py` and `race_pipeline.py`. Front-axle pipelines remain unchanged.

### 6.2 Computation flow

```
Telemetry → Total braking power per sample
         → Rear-axle braking power (×0.44)
         → Apply MGU-K power cap → split into P_regen, P_friction_rear
         → Integrate P_friction_rear over events → E_friction_rear per event
         → Build heat input array (per disc) → thermal model
         → Integrate wear
```

The decisive new computation is the power-cap step. Everything else is recombination of existing modules with different parameters.

### 6.3 Same-lap rear-vs-front comparison

The principal engineering output is a side-by-side rear-vs-front comparison at the same circuit-driver-lap. This is what the chunk 2 validation notebook produces. The interesting numbers:

- Front energy per disc vs rear energy per disc (rear should be lower due to regen)
- Front peak disc T vs rear peak disc T (depends on geometry vs energy trade-off)
- Front per-lap wear vs rear per-lap wear

This is what the paper's "2026 rear brake thermal landscape" claim would be built on.

---

## 7. Key assumptions

1. The greedy power-cap model accurately represents the brake-by-wire system's regen strategy at the instantaneous level. Real systems may add safety margins or use predictive control; we ignore these for v1.
2. The MGU-K is always available (battery never empty, motor never failed). True under normal racing conditions; would break under specific failure modes we don't model.
3. The 350 kW MGU-K power limit applies symmetrically to harvest (regen). This matches the regulation as documented.
4. The 7 MJ harvest cap doesn't bind. Verified by diagnostic across three tracks; will be re-verified in the model output.
5. Rear brake bias is fixed at 0.44 across all conditions.
6. Engine braking is unchanged from the front model; the constant equivalent deceleration still applies.
7. Rear disc thermal and wear parameters are M-confidence; sensitivity analysis on $h_{eff,0,rear}$ is required before claiming any rear-specific result.
8. Both rear discs (left and right) are modeled identically. Asymmetric corner distribution exists but is not modeled in v1.

---

## 8. Deliverables

1. **Scope document** — this document.
2. **Parameter doc extension** — new §5.7 in `02_parameter_derivation.md` with rear-specific parameters.
3. **Regen model module** — `src/physics/regen_model.py` with the instantaneous power-cap split function, plus tests.
4. **Thermal/wear refactor** — make front-axle parameters injectable so the same functions can be reused for the rear axle. No behavioral change for front.
5. **Rear pipeline module** — `src/analysis/rear_pipeline.py` that runs the full rear chain on a session.
6. **Notebook 07** — Monaco 2026 Q rear-brake analysis with rear-vs-front comparison. Single-lap, qualifying, parallel structure to Phase 1a's notebooks 01-04.
7. **Notebook 08** — Monaco 2026 R rear-brake analysis. Race conditions, parallel to chunk 1's notebook 06.
8. **Sensitivity analysis** — short notebook or section within notebook 07 examining how rear thermal/wear predictions change under reasonable variation of $h_{eff,0,rear}$.
9. **Chunk 2 closure document** — milestone summary, parallel to `03_phase_1a_summary.md` and `05_phase_1b_chunk_1_closure.md`.

---

## 9. Decisions log (resolved 2026-06-18)

1. **Engine braking attribution:** kept at whole-car level (same as Phase 1a). Initial instinct was to attribute it specifically to the rear axle because engine braking acts physically *through* the drivetrain to the rear wheels. On review, this was wrong: engine braking energy dissipates in the engine itself (compression and pumping losses in unfueled cycles), not at the brake discs. The rear discs never see that heat regardless of which axle the *force* acts on. The brake bias controls only the friction brake distribution — the brake-by-wire torque command — and engine braking sits outside that distribution by construction. So both axles use the Phase 1a formula structure: $E_{brake,friction,axle} = \beta_{axle} \cdot (\Delta E_{kin} - E_{drag} - E_{roll} - E_{eng})$. No change to constants; no change to where terms are applied. Logged here because the original instinct was a real physics confusion worth documenting.

2. **Rear cooling parameter $h_{eff,0,rear}$:** kept separate from front at 60 W/K (M-confidence). Lumping with front would assume equal heat transfer per unit area across geometrically different ducting systems — a stronger assumption than admitting we don't know the rear value precisely. This is the same philosophy as Phase 1a's $h_0$/$A_{cool,mult}$ lumping: lump only what's *jointly unidentifiable*, keep separate what's merely *uncertain*. Logged as the primary sensitivity-analysis target.

3. **Sample-level computation refactor:** required, not optional. The MGU-K power cap is a clipping operation that only makes physical sense applied continuously. At the event level, you'd either always clip (if event-average power exceeds 350 kW) or never (if it doesn't), erasing exactly the binding-within-events behavior the diagnostic identified as the dominant effect.

4. **Notebook 07 structure:** combined analysis + sensitivity in one notebook. The sensitivity sweep is a few cells, not a full narrative. Split only if it grows (e.g., multi-parameter sweeps).

5. **Notebook 08 scope:** rear-only focus, references but does not duplicate chunk 1's race-vs-Q work. The race-vs-Q wear gap is a driving-style + fuel-mass effect that carries over structurally to the rear axle; re-deriving it is redundant. The valuable rear-specific question is whether MGU-K power-limit binding frequency changes in race vs qualifying — different speeds, different driving style. That's a notebook section on its own merits.

6. **Sensitivity sweep range:** ±50% ($h_{eff,0,rear}$ from 30 to 90 W/K) as the headline range, with brief notes on what happens at 20 W/K and 150 W/K. Narrower would understate the genuine uncertainty in an M-confidence parameter with no public source.
