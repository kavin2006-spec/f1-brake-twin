"""
Unit tests for energy_balance.py

These tests use hand-computable cases and physical sanity checks.
Run with: pytest tests/test_energy_balance.py -v
"""

import numpy as np
import pytest
from src.physics.energy_balance import (
    air_density,
    drag_energy,
    rolling_resistance_energy,
    engine_braking_energy,
    decompose_braking_event,
)
from src.utils import constants as C


# ─────────────────────────────────────────────────────────────────────
# air_density
# ─────────────────────────────────────────────────────────────────────

def test_air_density_at_15C_sea_level():
    """Standard atmosphere at 15°C should give ~1.225 kg/m³."""
    rho = air_density(15.0)
    assert abs(rho - 1.225) < 0.01


def test_air_density_increases_with_cold():
    """Cold air is denser than warm air at same pressure."""
    rho_cold = air_density(0.0)
    rho_warm = air_density(30.0)
    assert rho_cold > rho_warm


# ─────────────────────────────────────────────────────────────────────
# drag_energy
# ─────────────────────────────────────────────────────────────────────

def test_drag_energy_constant_velocity():
    """At constant velocity, E_drag = 0.5·ρ·Cd·A·v³·t (analytical)."""
    v_const = 50.0  # m/s
    t_total = 10.0  # s
    t = np.linspace(0, t_total, 100)
    v = np.full_like(t, v_const)
    rho = 1.225

    expected = 0.5 * rho * C.CD * C.A_F * v_const**3 * t_total
    computed = drag_energy(v, t, rho)
    assert abs(computed - expected) / expected < 1e-6


def test_drag_energy_scales_with_v_cubed():
    """Doubling speed should multiply drag energy by 8 (2³)."""
    t = np.linspace(0, 1, 100)
    v_low = np.full_like(t, 30.0)
    v_high = np.full_like(t, 60.0)
    E_low = drag_energy(v_low, t, rho_air=1.225)
    E_high = drag_energy(v_high, t, rho_air=1.225)
    assert abs(E_high / E_low - 8.0) < 1e-3


# ─────────────────────────────────────────────────────────────────────
# rolling_resistance_energy
# ─────────────────────────────────────────────────────────────────────

def test_rolling_energy_constant_velocity():
    """E_roll = Crr·m·g·v·t at constant velocity."""
    v_const = 50.0
    t_total = 10.0
    t = np.linspace(0, t_total, 100)
    v = np.full_like(t, v_const)

    expected = C.CRR * C.M_CAR * C.G * v_const * t_total
    computed = rolling_resistance_energy(v, t)
    assert abs(computed - expected) / expected < 1e-6


def test_rolling_energy_scales_linearly_with_v():
    """Doubling speed should double rolling energy."""
    t = np.linspace(0, 1, 100)
    v_low = np.full_like(t, 30.0)
    v_high = np.full_like(t, 60.0)
    E_low = rolling_resistance_energy(v_low, t)
    E_high = rolling_resistance_energy(v_high, t)
    assert abs(E_high / E_low - 2.0) < 1e-3


# ─────────────────────────────────────────────────────────────────────
# engine_braking_energy
# ─────────────────────────────────────────────────────────────────────

def test_engine_braking_is_force_times_distance():
    """E_eng = m·a_eng·distance, where distance = ∫v dt."""
    t = np.linspace(0, 5, 100)
    v = np.full_like(t, 40.0)  # constant 40 m/s for 5 s → 200 m

    expected = C.M_CAR * C.A_ENG * 200.0
    computed = engine_braking_energy(v, t)
    assert abs(computed - expected) / expected < 1e-3


# ─────────────────────────────────────────────────────────────────────
# decompose_braking_event
# ─────────────────────────────────────────────────────────────────────

def _synthetic_event():
    """A reusable synthetic braking event: 80 → 30 m/s, linear, 3 s."""
    t = np.linspace(0, 3.0, 50)
    v = np.linspace(80.0, 30.0, 50)
    return v, t


def test_decompose_all_energies_positive():
    """All energy terms during a real braking event must be positive."""
    v, t = _synthetic_event()
    result = decompose_braking_event(v, t, rho_air=1.2)
    assert result['delta_KE_J'] > 0
    assert result['E_drag_J'] > 0
    assert result['E_roll_J'] > 0
    assert result['E_eng_J'] > 0
    assert result['E_brake_total_J'] > 0
    assert result['E_brake_front_J'] > 0


def test_decompose_energy_balance_closes():
    """Sum of all dissipation terms must equal ΔKE exactly (by construction)."""
    v, t = _synthetic_event()
    result = decompose_braking_event(v, t, rho_air=1.2)
    total = (result['E_drag_J'] + result['E_roll_J']
             + result['E_eng_J'] + result['E_brake_total_J'])
    assert abs(total - result['delta_KE_J']) < 1e-6  # essentially exact


def test_decompose_front_brake_is_bias_times_total():
    """Front brake energy must equal beta_front × total brake energy."""
    v, t = _synthetic_event()
    result = decompose_braking_event(v, t, rho_air=1.2)
    expected = C.BETA_FRONT * result['E_brake_total_J']
    assert abs(result['E_brake_front_J'] - expected) < 1e-6


def test_decompose_fractions_sum_to_one():
    """Fractional shares should sum to 1.0 by construction."""
    v, t = _synthetic_event()
    result = decompose_braking_event(v, t, rho_air=1.2)
    s = (result['frac_drag'] + result['frac_roll']
         + result['frac_eng'] + result['frac_brake_total'])
    assert abs(s - 1.0) < 1e-9


def test_decompose_brake_share_in_expected_range():
    """For a realistic braking event, brake share should be 60-90% of ΔKE."""
    v, t = _synthetic_event()
    result = decompose_braking_event(v, t, rho_air=1.2)
    assert 0.60 < result['frac_brake_total'] < 0.90