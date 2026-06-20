"""
constants.py — Phase 1a physical parameters for the 2026 F1 brake digital twin.

All values are sourced and justified in docs/02_parameter_derivation.md.
Any change here must be reflected in that document with a justification.

Phase 1a scope: qualifying, front brakes only, Monaco only, generic 2026 car.
"""

import numpy as np

# ── Physical constants ──────────────────────────────────────────────
G = 9.81                    # m/s², gravitational acceleration
SIGMA_SB = 5.670374e-8      # W/(m²·K⁴), Stefan-Boltzmann constant
R_AIR = 287.05              # J/(kg·K), specific gas constant for dry air
P_ATM = 101325.0            # Pa, standard atmospheric pressure

# ── Vehicle parameters (qualifying, Phase 1a) ──────────────────────
M_CAR = 850.0               # kg, total mass during Q3 (chassis + driver + Q3 fuel)
A_F = 1.40                  # m², frontal area
CD = 0.95                   # —, drag coefficient (Z-mode, Monaco)
CRR = 0.020                 # —, rolling resistance coefficient

# ── Engine braking ─────────────────────────────────────────────────
A_ENG = 0.30                # m/s², equivalent deceleration from engine braking

# ── Brake bias ─────────────────────────────────────────────────────
BETA_FRONT = 0.56           # —, fraction of total brake energy to front axle

# ── Brake disc geometry (front, single disc) ───────────────────────
D_DISC_OUTER = 0.330        # m, outer diameter
D_DISC_INNER = 0.180        # m, inner diameter
T_DISC = 0.032              # m, disc thickness
M_DISC = 2.0                # kg, mass of one disc

# Geometric area: annulus, both faces (computed once at import)
A_DISC_GEOMETRIC = 2 * np.pi * (D_DISC_OUTER**2 - D_DISC_INNER**2) / 4  # m²

# ── Carbon-carbon material properties (~600°C mid-range values) ────
RHO_CC = 1800.0             # kg/m³, density
CP_CC = 1300.0              # J/(kg·K), specific heat capacity
EPSILON_DISC = 0.85         # —, emissivity (oxidized carbon at high T)

# ── Cooling: lumped convective conductance ─────────────────────────
H_EFF_0 = 72.0              # W/K, lumped (h × A_cool) at reference velocity
V_REF = 80.0                # m/s, reference velocity (~290 km/h)
N_VEL = 0.7                 # —, velocity exponent for convective scaling

# ── Wear model (L confidence — calibration targets) ────────────────
K_MECH = 1.0e-11            # kg/J, mechanical wear coefficient
K_OX_0 = 5.0e-4             # kg/s, oxidative pre-exponential factor
E_A = 150_000.0             # J/mol, activation energy for carbon oxidation
R_GAS = 8.314               # J/(mol·K), universal gas constant

# ── Race-condition parameters (Phase 1b chunk 1) ───────────────────
FUEL_KG_PER_LAP = 0.9       # kg/lap, average race fuel consumption
FUEL_MAX_KG = 70.0          # kg, 2026 regulatory cap
FUEL_END_KG = 3.0           # kg, minimum race-end fuel
T_RACE_START_C = 350.0      # °C, disc temp at start of lap 2 (first racing lap)

# ── Rear-axle parameters (Phase 1b chunk 2) ────────────────────────
BETA_REAR = 0.44                       # —, brake bias to rear (1 - BETA_FRONT)
D_DISC_OUTER_REAR = 0.270              # m, rear disc outer diameter
D_DISC_INNER_REAR = 0.150              # m, rear disc inner diameter
T_DISC_REAR = 0.032                    # m, rear disc thickness (same cap as front)
M_DISC_REAR = 1.4                      # kg, rear disc mass (geometric scaling from front)
H_EFF_0_REAR = 60.0                    # W/K, rear lumped convective conductance
MGUK_POWER_LIMIT = 350_000.0           # W, MGU-K peak harvest power (2026 regs)
MGUK_HARVEST_CAP_J = 7_000_000.0       # J, MGU-K harvest cap per lap (2026 regs)