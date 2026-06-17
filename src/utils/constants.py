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