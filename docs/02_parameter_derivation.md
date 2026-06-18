# Parameter Derivation for the 2026 F1 Front-Brake Hybrid Twin (Phase 1a)

**Document type:** Numerical parameter specification with sources
**Phase:** 1a — Qualifying-only, front brakes only, single-lap analysis
**Status:** Draft v1, for review
**Last updated:** 2026-06-14

---

## 1. Purpose

The scope document (`01_project_scope.md`) defined what we model, what we assume, and what we defer. This document fixes the _numerical values_ of every constant used in the Phase 1a physics model, with a sourced justification for each. Once approved, the physics model becomes a deterministic function of these numbers and the FastF1 telemetry — no further parameter discussion required during implementation.

Race-mass modeling (fuel burn) and multi-lap thermal/wear accumulation are deferred to Phase 1b alongside the rear-brake extension.

## 2. How to read this document

Every parameter is tagged with a **confidence level**:

- **H (High)** — value is fixed by regulation or by a published manufacturer specification; uncertainty under ~5%.
- **M (Medium)** — value is taken from published literature in adjacent domains (other racing, aerospace, automotive engineering) and is reasonable but not directly measured for 2026 F1; uncertainty 10-30%.
- **L (Low)** — value is an engineering estimate without strong public-source backing; uncertainty potentially large. These are the parameters most likely to drive model error and should be the first candidates for sensitivity analysis.

For the hybrid model later, **low-confidence parameters are the ones the data-driven residual layer is most likely to need to correct.** The L flags here will resurface as the most informative diagnostics.

---

## 3. Vehicle parameters

### 3.1 Total mass (qualifying)

| Component                           | Value      | Confidence | Source / note                                                         |
| ----------------------------------- | ---------- | ---------- | --------------------------------------------------------------------- |
| Minimum dry car mass                | 768 kg     | H          | 2026 FIA Technical Regulations                                        |
| Driver + safety equipment           | 80 kg      | M          | Standard F1 assumption; FIA driver minimum is 82 kg including ballast |
| Fuel (Q3 stint)                     | ~5 kg      | M          | Q3 outlap + 1 push lap + inlap; minimal fuel load                     |
| **Total qualifying mass $m_{car}$** | **853 kg** | **M**      | Sum; round to **850 kg** for modeling                                 |

Symbol: $m_{car} = 850$ kg

### 3.2 Geometric and aerodynamic parameters

| Symbol       | Parameter                                | Value       | Confidence | Source                                                                                                                                     |
| ------------ | ---------------------------------------- | ----------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| $L$          | Wheelbase                                | 3.40 m      | H          | 2026 FIA regs (3600 → 3400 mm)                                                                                                             |
| $W$          | Vehicle width                            | 1.90 m      | H          | 2026 FIA regs (2000 → 1900 mm)                                                                                                             |
| $A_f$        | Frontal area                             | **1.40 m²** | M          | Engineering estimate; F1 2022-2025 cars ~1.5 m², 2026 ~5% narrower body                                                                    |
| $C_d$        | Drag coefficient (Z-mode, max downforce) | **0.95**    | M          | Public F1 estimates: $C_d$ = 0.7-1.0 for F1; Monaco runs maximum downforce, upper end of range                                             |
| $C_{rr}$     | Rolling resistance coefficient           | **0.020**   | M          | Generic racing slick on smooth asphalt; F1-specific value not publicly published                                                           |
| $\rho_{air}$ | Air density                              | computed    | H          | From FastF1 weather: $\rho = P / (R_{specific} \cdot T)$. P assumed 101325 Pa at sea-level Monaco. Will use measured air temp per session. |

**Important caveat on $C_d$ and 2026:** 2026 cars feature active aerodynamics (X-Mode = low drag, Z-Mode = high downforce). Public targets quoted include "55% drag reduction in X-mode vs Z-mode" and "18% drag reduction with up to 25% downforce reduction" depending on source. For Phase 1a at Monaco (where X-mode is barely used due to the short straights), modeling a single fixed $C_d = 0.95$ is defensible. For tracks with long straights (Monza, Baku) this assumption breaks; that will need addressing later.

### 3.3 Power unit parameters (for engine braking)

| Symbol            | Parameter               | Value  | Confidence | Source                             |
| ----------------- | ----------------------- | ------ | ---------- | ---------------------------------- |
| $P_{ICE,max}$     | ICE peak power          | 400 kW | H          | 2026 FIA regs                      |
| $P_{MGUK,max}$    | MGU-K peak power        | 350 kW | H          | 2026 FIA regs                      |
| $E_{bat,usable}$  | Battery usable capacity | 4.0 MJ | H          | 2026 FIA regs                      |
| $E_{harvest,lap}$ | Harvest cap per lap     | 7.0 MJ | H          | 2026 FIA regs (post 2025 revision) |

These are used only indirectly in Phase 1a — to bound the engine braking model and to confirm regen does not happen at the front axle.

---

## 4. Brake disc parameters (front)

### 4.1 Geometry

| Symbol         | Parameter                                    | Value                  | Confidence | Source                                                               |
| -------------- | -------------------------------------------- | ---------------------- | ---------- | -------------------------------------------------------------------- |
| $D_{disc}$     | Outer diameter                               | 0.330 m                | H          | Brembo published range 325-345 mm for fronts; 330 chosen as midpoint |
| $D_{inner}$    | Inner diameter                               | 0.180 m                | M          | Typical F1 inner: ~180 mm (estimated from disc geometry photos)      |
| $t_{disc}$     | Disc thickness                               | 0.032 m                | H          | Brembo published range up to 34 mm; teams typically use 32 mm        |
| $m_{disc}$     | Disc mass                                    | 2.0 kg                 | H          | Brembo published value for 2026 spec front disc                      |
| $A_{surf}$     | Geometric surface area (both faces, annulus) | computed               | H          | $2 \pi (D_{disc}^2 - D_{inner}^2)/4$                                 |
| $A_{cool,eff}$ | Effective cooling area                       | not separately modeled | —          | Folded into $h_{eff}$ in §5.1 (joint identifiability)                |

**On disc inner diameter:** 180 mm is an engineering estimate. The Brembo photographic references show clearly visible inner-radius regions, but precise dimensions are not publicly published. This is L-confidence in principle, but it only enters through the surface area calculation, so its impact is moderated.

**On the cooling area:** F1 discs have on the order of 1000-1400 ventilation holes per disc that multiply effective convective area by ~2-4×. In v1 this multiplier and the convective coefficient $h$ are folded into a single lumped parameter (see §5.1) because they only ever appear as a product in the model. A 2× multiplier is used as the implicit basis when computing the default lumped value (conservative on cooling, biased toward overestimating disc temperature — diagnostically asymmetric in our favor).

### 4.2 Material properties (carbon-carbon composite)

C/C properties are temperature-dependent. For Phase 1a we use constant values evaluated at ~600°C (mid operating range) and accept the approximation; if needed, Phase 1b can introduce temperature-dependent properties.

| Symbol        | Parameter              | Value         | Confidence | Source / note                                                                                                                                                                                                   |
| ------------- | ---------------------- | ------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| $\rho_{cc}$   | Density                | 1800 kg/m³    | H          | Published C/C composite range 1700-1900 kg/m³                                                                                                                                                                   |
| $c_p$         | Specific heat capacity | 1300 J/(kg·K) | M          | C/C published ~2.4× steel's value; varies with T from ~700 (room temp) to ~1800 (1000°C). 1300 chosen as ~600°C value                                                                                           |
| $k$           | Thermal conductivity   | 100 W/(m·K)   | L          | C/C published range 30-450 W/(m·K) radially, anisotropic. 100 is a working assumption; matters for in-disc gradients but Phase 1a uses lumped-capacity (so this parameter does not enter the v1 model directly) |
| $\varepsilon$ | Emissivity             | 0.85          | M          | Oxidized carbon emissivity typically 0.8-0.9 at high temperature                                                                                                                                                |

**Note for the lumped-capacity assumption:** $k$ does not appear in the v1 thermal equation (because the lumped model treats the disc as uniform-temperature). It's listed here so the assumption is explicit and so it can be reintroduced if we move to a spatial model.

### 4.3 Effective thermal mass

The product $m_{disc} \cdot c_p$ governs how much energy raises the disc temperature by 1 K:

$$
m_{disc} \cdot c_p = 2.0 \text{ kg} \times 1300 \text{ J/(kg·K)} = 2600 \text{ J/K}
$$

**Sanity check using the values from our telemetry exploration:** if the biggest Monaco braking event deposits ~720 kJ into a single disc (Nouvelle Chicane upper bound), and _none_ of it were carried away, the disc temperature would rise by 720000 / 2600 ≈ 277 K in 3 seconds. This is within the realistic operating window. Some heat _is_ carried away, so the real rise is lower — but the order of magnitude is correct, which is reassuring.

---

## 5. Cooling parameters

### 5.1 Lumped convective heat transfer term $h_{eff}$

The original physics has two parameters: a convective heat transfer coefficient $h(v)$ and an effective cooling area $A_{cool,eff}$. They appear in the energy balance only as a product:

$$
\dot{Q}_{conv} = h(v) \cdot A_{cool,eff} \cdot (T_{disc} - T_{amb})
$$

Without an independent observation that separates them, they are **jointly unidentifiable** — many ($h$, $A$) pairs give the same predicted disc temperature trace. We therefore collapse them into a single lumped parameter with units of thermal conductance:

$$
\dot{Q}_{conv}(v) = h_{eff}(v) \cdot (T_{disc} - T_{amb})
$$

with the velocity dependence preserved as:

$$
h_{eff}(v) = h_{eff,0} \left( \frac{v}{v_0} \right)^n
$$

| Symbol      | Parameter                              | Value      | Confidence | Source / note                                                                                                                                    |
| ----------- | -------------------------------------- | ---------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| $h_{eff,0}$ | Lumped convective conductance at $v_0$ | **72 W/K** | L          | Computed from $h_0$ = 300 W/(m²·K), $A_{cool,mult}$ = 2.0, $A_{geometric}$ ≈ 0.12 m² as a starting point; will be the primary calibration target |
| $v_0$       | Reference velocity                     | 80 m/s     | M          | ~290 km/h reference                                                                                                                              |
| $n$         | Velocity exponent                      | 0.7        | M          | Forced-convection turbulent flow; standard                                                                                                       |

**The 2.0 cooling area multiplier basis is a deliberate choice on the conservative side** (less cooling, hotter disc predicted). The reasoning is diagnostic asymmetry: if the model predicts physically implausible temperatures we know exactly which direction to adjust. The opposite bias would leave us unable to distinguish "cooling overestimated" from "heat input underestimated."

**This single parameter ($h_{eff,0}$) is the primary calibration target for Phase 1a.** Sensitivity analysis priority #1.

### 5.2 Radiation

At carbon-carbon operating temperatures above ~600°C, radiative heat loss is non-negligible. The radiative term in the energy balance is:

$$
\dot{Q}_{rad} = \varepsilon \sigma A_{surf} (T_{disc}^4 - T_{amb}^4)
$$

| Symbol        | Parameter                 | Value                 | Confidence | Source            |
| ------------- | ------------------------- | --------------------- | ---------- | ----------------- |
| $\sigma$      | Stefan-Boltzmann constant | 5.67 × 10⁻⁸ W/(m²·K⁴) | H          | Physical constant |
| $\varepsilon$ | Emissivity                | 0.85                  | M          | See §4.2          |

**Sanity check:** at $T_{disc}$ = 1000 K (727°C) and $T_{amb}$ = 300 K, with geometric $A_{surf}$ ≈ 0.12 m²:

$$
\dot{Q}_{rad} = 0.85 \times 5.67 \times 10^{-8} \times 0.12 \times (1000^4 - 300^4) \approx 5.8 \text{ kW per disc}
$$

That is a meaningful fraction of typical event-average power. Including radiation in v1 is correct.

### 5.3 Ambient temperature

| Symbol    | Parameter           | Value               | Confidence | Source                            |
| --------- | ------------------- | ------------------- | ---------- | --------------------------------- |
| $T_{amb}$ | Ambient temperature | from FastF1 weather | H          | `session.weather_data['AirTemp']` |

For the Monaco 2026 Q reference lap, $T_{amb}$ ≈ 297 K (24°C average). For each session-specific run, the actual value will be read from the weather feed.

---

### 5.5 Wear model parameters

Carbon-carbon disc wear follows a dual mechanism: mechanical (energy-proportional) and oxidative (Arrhenius temperature dependence). Total wear rate:

$$
\frac{dW}{dt} = k_{mech} \cdot P_{brake}(t) + k_{ox,0} \cdot e^{-E_a / (R \cdot T_{disc})}
$$

| Symbol     | Parameter                       | Value       | Confidence | Source / note                                                                                             |
| ---------- | ------------------------------- | ----------- | ---------- | --------------------------------------------------------------------------------------------------------- |
| $k_{mech}$ | Mechanical wear coefficient     | 1.0 × 10⁻¹¹ | L          | kg/J. Calibrated so total stint wear is in plausible F1 range (~1-2 mm per stint); no public ground truth |
| $k_{ox,0}$ | Oxidative wear pre-exponential  | 5.0 × 10⁻⁴  | L          | kg/s. Order-of-magnitude estimate from aerospace C/C literature                                           |
| $E_a$      | Activation energy for oxidation | 150         | M          | kJ/mol. Standard for carbon oxidation in air; published range 120-180                                     |
| $R$        | Universal gas constant          | 8.314       | H          | J/(mol·K). Physical constant                                                                              |

**This model is structurally correct but absolute-magnitude uncalibrated.** Relative comparisons (track A vs track B, driver A vs driver B, mechanical vs oxidative share) are defensible. Absolute wear-per-lap is approximately 1-2 orders of magnitude smaller than reported F1 wear (~15-50 µm per disc per lap in real F1; our default produces single-digit µm). Recalibrating $k_{mech}$ and $k_{ox,0}$ to match published F1 wear is deferred to Phase 1b when we'll need it for race-stint life prediction. For Phase 1a, the model's value is in showing where wear concentrates on the lap and how the two mechanisms split, not in absolute mm-per-stint predictions.

**Why two mechanisms matter:** mechanical wear concentrates during braking events; oxidative wear accumulates whenever the disc is hot, which at Monaco means _most of the lap_. The split between mechanisms tells us whether brake life is limited by usage intensity or by sustained operating temperature — different engineering implications.

### 5.6 Race-specific parameters (Phase 1b chunk 1)

For race-condition extension. These supersede the Phase 1a constant-mass assumption when running race sessions; qualifying analysis continues to use the single-mass model.

| Symbol            | Parameter                            | Value | Confidence | Source / note                                                                                                                                      |
| ----------------- | ------------------------------------ | ----- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `FUEL_KG_PER_LAP` | Per-lap fuel consumption (heuristic) | 0.9   | M          | kg/lap. 2026 regs limit max race fuel; 0.9 chosen as round-number consensus; varies ±20% by circuit                                                |
| `FUEL_MAX_KG`     | Maximum race-start fuel              | 70.0  | H          | kg. 2026 FIA regulation cap                                                                                                                        |
| `FUEL_END_KG`     | Required race-end fuel               | 3.0   | M          | kg. Scrutineering sample minimum; 3 kg conservative                                                                                                |
| `T_RACE_START_C`  | Disc temperature at start of lap 2   | 350.0 | L          | °C. Warmed by formation lap, slightly cooled on grid. Initial condition uncertainty washes out within ~3 racing laps due to thermal time constant. |

**Race-start fuel mass heuristic.** For a race of $N_{laps}$ laps:

$$
m_{fuel,start} = \min(\text{FUEL\_KG\_PER\_LAP} \cdot N_{laps},\; \text{FUEL\_MAX\_KG})
$$

The min protects against absurdly long races (none in 2026, but defensive). The cap reflects the regulatory limit.

**Linear burn-down.** Fuel mass at the start of racing lap $k$ (where $k=2$ is the first analyzed lap):

$$
m_{fuel}(k) = m_{fuel,start} - \frac{m_{fuel,start} - m_{fuel,end}}{N_{race} - 1} \cdot (k - 1)
$$

Real fuel consumption varies lap-to-lap (fuel saving, traffic, pace management), but in aggregate the linear model captures the dominant effect — total car mass declining by 60-80 kg across a race.

## 6. Engine braking model

When the driver is off-throttle but not braking (coast-down phase), the car still decelerates due to drag, rolling resistance, **and** engine braking from the ICE. Phase 1a uses a simple constant-deceleration model:

| Symbol    | Parameter                              | Value     | Confidence | Source / note                                                                                                                                                                                                                                       |
| --------- | -------------------------------------- | --------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| $a_{eng}$ | Engine braking equivalent deceleration | 0.30 m/s² | L          | Engineering estimate; F1 ICE engine braking when off-throttle is typically 0.3-0.5 g equivalent (3-5 m/s²) — but most of that is split between gear, RPM, and drag. Pure engine braking contribution is much smaller. Will likely need calibration. |

**This is a known weak spot in the model.** Engine braking on a high-revving F1 ICE with the MGU-K in regen mode is genuinely complex and not publicly characterized. The constant approximation is defensible only because:

1. Engine braking is a small fraction of total deceleration during heavy braking (brakes dominate).
2. During coast phases (throttle=0, brake=0), drag is the largest decelerator at high speed, not engine.

For Phase 1a we use the constant. If validation shows systematic bias in the energy balance during coast phases, this is the first parameter to revisit.

---

## 7. Energy split and brake bias

| Symbol               | Parameter                                                  | Value           | Confidence | Source                                                         |
| -------------------- | ---------------------------------------------------------- | --------------- | ---------- | -------------------------------------------------------------- |
| $\beta_{front}$      | Brake bias to front axle                                   | 0.56            | M          | Per scope decision; F1 typical 0.55-0.58                       |
| $f_{friction,front}$ | Fraction of front-axle braking absorbed by friction brakes | 1.00            | H          | No regen on front axle (regulation: MGU-K only on rear)        |
| $f_{friction,rear}$  | Fraction of rear-axle braking absorbed by friction brakes  | N/A in Phase 1a | —          | Out of scope; will be a hidden state in Phase 1c (rear brakes) |

Front-axle brake energy per event:

$$
E_{brake,front,actual} = \beta_{front} \cdot (\Delta E_{kin} - E_{drag} - E_{roll} - E_{eng})
$$

And the friction-disc energy is the same since $f_{friction,front} = 1$.

---

## 8. Consolidated parameter table

For quick reference and direct import into code:

| Symbol          | Name                           | Value     | Units     |
| --------------- | ------------------------------ | --------- | --------- |
| $m_{car}$       | Vehicle mass (Q3)              | 850       | kg        |
| $A_f$           | Frontal area                   | 1.40      | m²        |
| $C_d$           | Drag coefficient (Z-mode)      | 0.95      | —         |
| $C_{rr}$        | Rolling resistance coefficient | 0.020     | —         |
| $g$             | Gravitational acceleration     | 9.81      | m/s²      |
| $a_{eng}$       | Engine braking deceleration    | 0.30      | m/s²      |
| $\beta_{front}$ | Brake bias front               | 0.56      | —         |
| $D_{disc}$      | Front disc outer diameter      | 0.330     | m         |
| $D_{inner}$     | Front disc inner diameter      | 0.180     | m         |
| $t_{disc}$      | Disc thickness                 | 0.032     | m         |
| $m_{disc}$      | Disc mass                      | 2.0       | kg        |
| $\rho_{cc}$     | C/C density                    | 1800      | kg/m³     |
| $c_p$           | C/C specific heat (~600°C)     | 1300      | J/(kg·K)  |
| $\varepsilon$   | Emissivity                     | 0.85      | —         |
| $h_{eff,0}$     | Lumped convective conductance  | 72        | W/K       |
| $v_0$           | Reference velocity             | 80        | m/s       |
| $n$             | Velocity exponent              | 0.7       | —         |
| $\sigma$        | Stefan-Boltzmann constant      | 5.67×10⁻⁸ | W/(m²·K⁴) |
| $k_{mech}$      | Mechanical wear coefficient    | 1.0×10⁻¹¹ | kg/J      |
| $k_{ox,0}$      | Oxidative pre-exponential      | 5.0×10⁻⁴  | kg/s      |
| $E_a$           | Activation energy              | 150_000   | J/mol     |
| $R_{gas}$       | Universal gas constant         | 8.314     | J/(mol·K) |

This will live in code as a `constants.py` module so that any change to a parameter is one edit, one commit, traceable.

---

## 9. Confidence summary

The parameters most likely to drive model error, in order:

1. **$h_{eff,0}$ (lumped convective conductance)** — L. Single largest source of uncertainty. Calibration target #1. Default value (72 W/K) deliberately biased toward less cooling for diagnostic asymmetry.
2. **$a_{eng}$ (engine braking)** — L. Affects energy balance in coast phases. Small absolute impact since coast-phase energies are low.
3. **$C_d$** — M at Monaco (Z-mode dominant). Would degrade to L at tracks with significant X-Mode use; restricted to Monaco only in Phase 1a.
4. **$c_p$ (specific heat as constant)** — M. Real value varies by ~2× over operating range. Temperature dependence may be needed in Phase 1b.

Parameters with H confidence form a defensible base; the model is most vulnerable where M and L parameters appear.

---

## 10. Decisions log (resolved 2026-06-14)

1. **$h$ vs $A_{cool,mult}$:** Lumped into single parameter $h_{eff,0}$ for Phase 1a. Joint unidentifiability means individual values are arbitrary; only the product affects predictions. Separation can be reintroduced in Phase 1b if data justifies it.
2. **Engine braking model:** Constant $a_{eng}$ retained. Misspecification matters most at low speed / coast phases where absolute energy is small. Revisit only if validation shows systematic coast-phase bias.
3. **Track scope for Phase 1a:** Monaco only. Z-mode dominant, single fixed $C_d$ defensible. Multi-track extension with X/Z-mode handling is a Phase 1b target.
4. **Cooling area multiplier basis:** 2× geometric (conservative on cooling, biased toward overestimating disc temperature). Diagnostic asymmetry: model failures will point clearly to which direction to adjust. Logged as a calibration priority alongside $h_{eff,0}$.

---

## 11. References (cited in this document)

- 2026 FIA Formula 1 Technical Regulations (chassis, power unit)
- Brembo: "Ventilation of Carbon Brake Discs in F1" (brembo.com/en/motorsport/formula1/ventilation-holes)
- Brembo F1 2026 brake specifications (public press materials)
- TotalSim: "Brake Cooling in F1" (totalsimulation.co.uk)
- F1Technical: "F1MATHS: A Technical Analysis of Formula One's 2026 Aerodynamic Regulations"
- Carbon/carbon thermal property references (research papers cited inline in §4.2)
- Formula 1 Dictionary: aerodynamics overview
- FastF1 documentation for telemetry and weather channels
