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

# ─────────────────────────────────────────────────────────────────────
# Sample-level power functions (Phase 1b chunk 2)
# ─────────────────────────────────────────────────────────────────────

from src.physics.energy_balance import (
    drag_power_instantaneous,
    rolling_resistance_power_instantaneous,
    engine_braking_power_instantaneous,
    kinetic_power_loss_instantaneous,
    brake_power_instantaneous,
)


def test_drag_power_inst_zero_at_zero_speed():
    """Drag power must be zero when not moving."""
    v = np.zeros(10)
    P = drag_power_instantaneous(v, rho_air=1.225)
    assert np.allclose(P, 0.0)


def test_drag_power_inst_scales_v_cubed():
    """Doubling v should give 8x drag power."""
    v_low = np.full(5, 30.0)
    v_high = np.full(5, 60.0)
    P_low = drag_power_instantaneous(v_low, rho_air=1.225)
    P_high = drag_power_instantaneous(v_high, rho_air=1.225)
    assert np.allclose(P_high / P_low, 8.0, rtol=1e-9)


def test_rolling_power_inst_linear_in_v():
    """Rolling power is linear in speed (constant force)."""
    v_low = np.full(5, 30.0)
    v_high = np.full(5, 60.0)
    P_low = rolling_resistance_power_instantaneous(v_low)
    P_high = rolling_resistance_power_instantaneous(v_high)
    assert np.allclose(P_high / P_low, 2.0, rtol=1e-9)


def test_engine_braking_power_inst_linear_in_v():
    """Engine braking power is force × velocity, force constant."""
    v = np.array([20.0, 40.0, 80.0])
    P = engine_braking_power_instantaneous(v)
    assert P[1] / P[0] == pytest.approx(2.0)
    assert P[2] / P[0] == pytest.approx(4.0)


def test_kinetic_power_loss_zero_for_constant_speed():
    """Constant speed → no kinetic energy change → zero power loss."""
    t = np.linspace(0, 5, 50)
    v = np.full_like(t, 60.0)
    P = kinetic_power_loss_instantaneous(v, t)
    assert np.allclose(P, 0.0, atol=1e-6)


def test_kinetic_power_loss_during_linear_deceleration():
    """Constant deceleration → P = m × v × a, decreasing as v decreases."""
    t = np.linspace(0, 5, 50)
    a = 20.0  # m/s² deceleration
    v = 80.0 - a * t
    P = kinetic_power_loss_instantaneous(v, t)
    # Expected: m × v × a at each point (in the interior, away from edges)
    expected_mid = C.M_CAR * v[25] * a
    assert P[25] == pytest.approx(expected_mid, rel=1e-3)
    # P should decrease as v decreases
    assert P[10] > P[40]


def test_kinetic_power_loss_zero_during_acceleration():
    """Accelerating → kinetic energy is gaining, not losing → returns zero."""
    t = np.linspace(0, 5, 50)
    v = 40.0 + 10.0 * t  # accelerating from 40 to 90
    P = kinetic_power_loss_instantaneous(v, t)
    assert np.all(P == 0.0)


def test_brake_power_zero_outside_braking():
    """If brake_bool is False everywhere, brake power should be zero."""
    t = np.linspace(0, 5, 50)
    a = 20.0
    v = 80.0 - a * t
    brake = np.zeros_like(t, dtype=bool)  # never braking
    P = brake_power_instantaneous(v, t, rho_air=1.225, brake_bool=brake)
    assert np.allclose(P, 0.0)


def test_brake_power_subtracts_non_brake_terms():
    """Brake power = kinetic loss − drag − rolling − engine braking."""
    t = np.linspace(0, 5, 50)
    a = 20.0
    v = 80.0 - a * t
    brake = np.ones_like(t, dtype=bool)
    
    P_brake = brake_power_instantaneous(v, t, rho_air=1.225, brake_bool=brake)
    P_kin = kinetic_power_loss_instantaneous(v, t)
    P_drag = drag_power_instantaneous(v, rho_air=1.225)
    P_roll = rolling_resistance_power_instantaneous(v)
    P_eng = engine_braking_power_instantaneous(v)
    
    expected = np.maximum(P_kin - P_drag - P_roll - P_eng, 0.0)
    # In the interior (away from gradient edge effects), should match
    assert np.allclose(P_brake[10:40], expected[10:40], rtol=1e-3)


def test_brake_power_event_integral_matches_event_level():
    """
    Critical consistency check: integrating P_brake over an event should
    give approximately the same result as the event-level decomposition.
    """
    from src.physics.energy_balance import decompose_braking_event
    
    # Synthetic event: 80 → 30 m/s over 3 s
    t = np.linspace(0, 3.0, 100)
    v = np.linspace(80.0, 30.0, 100)
    brake = np.ones_like(t, dtype=bool)
    
    # Event-level
    decomp = decompose_braking_event(v, t, rho_air=1.2)
    E_brake_total_event_level = decomp['E_brake_total_J']
    
    # Sample-level integrated
    P_brake = brake_power_instantaneous(v, t, rho_air=1.2, brake_bool=brake)
    E_brake_total_sample_level = np.trapezoid(P_brake, t)
    
    # Should agree within a few percent (gradient edge effects)
    assert abs(E_brake_total_event_level - E_brake_total_sample_level) \
        / E_brake_total_event_level < 0.05