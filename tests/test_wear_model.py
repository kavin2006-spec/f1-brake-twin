"""
Unit tests for wear_model.py
"""

import numpy as np
import pytest
from src.physics.wear_model import (
    mechanical_wear_rate,
    oxidative_wear_rate,
    total_wear_rate,
    integrate_wear_lap,
)
from src.utils import constants as C


# ─────────────────────────────────────────────────────────────────────
# Mechanical wear
# ─────────────────────────────────────────────────────────────────────

def test_mechanical_wear_zero_at_zero_power():
    """No braking power = no mechanical wear."""
    assert mechanical_wear_rate(0.0) == 0.0


def test_mechanical_wear_scales_linearly():
    """Doubling power doubles mechanical wear rate."""
    w_low = mechanical_wear_rate(100_000.0)
    w_high = mechanical_wear_rate(200_000.0)
    assert abs(w_high / w_low - 2.0) < 1e-9


def test_mechanical_wear_uses_correct_coefficient():
    """At 1 W, wear rate equals k_mech (by definition)."""
    assert abs(mechanical_wear_rate(1.0) - C.K_MECH) < 1e-20


# ─────────────────────────────────────────────────────────────────────
# Oxidative wear
# ─────────────────────────────────────────────────────────────────────

def test_oxidative_wear_negligible_at_room_temperature():
    """At 300 K (27°C), oxidative wear should be effectively zero."""
    rate = oxidative_wear_rate(300.0)
    assert rate < 1e-25  # exp(-150000 / 8.314 / 300) is astronomically small


def test_oxidative_wear_nontrivial_at_brake_temperatures():
    """At 1000 K (727°C), oxidative wear should be well above numerical zero.

    Absolute magnitudes here depend on the L-confidence wear coefficients
    (see docs/02_parameter_derivation.md §5.5); our default calibration
    produces sub-microgram per-lap oxidative wear. We test only that the
    rate is non-trivial and physically bounded.
    """
    rate = oxidative_wear_rate(1000.0)
    lap_mass = rate * 72.0
    assert lap_mass > 1e-12  # well above numerical zero
    assert lap_mass < 1e-3   # well below disc mass (sanity)


def test_oxidative_wear_increases_with_temperature():
    """Higher temperature must give higher wear rate (Arrhenius)."""
    r_700 = oxidative_wear_rate(700.0)
    r_900 = oxidative_wear_rate(900.0)
    r_1100 = oxidative_wear_rate(1100.0)
    assert r_700 < r_900 < r_1100


def test_oxidative_wear_arrhenius_ratio():
    """Verify Arrhenius behavior: ratio at two temperatures matches exp form."""
    T1, T2 = 800.0, 1000.0
    r1 = oxidative_wear_rate(T1)
    r2 = oxidative_wear_rate(T2)
    expected_ratio = np.exp(-C.E_A / C.R_GAS * (1/T2 - 1/T1))
    actual_ratio = r2 / r1
    assert abs(actual_ratio - expected_ratio) / expected_ratio < 1e-6


def test_oxidative_wear_negative_temperature_returns_zero():
    """Defensive: negative absolute temperature must not crash."""
    assert oxidative_wear_rate(-10.0) == 0.0


# ─────────────────────────────────────────────────────────────────────
# Total wear
# ─────────────────────────────────────────────────────────────────────

def test_total_wear_sums_components():
    """Total wear rate equals sum of mechanical and oxidative."""
    P, T = 500_000.0, 900.0
    total = total_wear_rate(P, T)
    expected = mechanical_wear_rate(P) + oxidative_wear_rate(T)
    assert abs(total - expected) < 1e-20


# ─────────────────────────────────────────────────────────────────────
# Lap integration
# ─────────────────────────────────────────────────────────────────────

def _synthetic_lap():
    """Helper: 72 s lap, constant power, constant T."""
    t = np.linspace(0, 72, 540)
    P = np.full_like(t, 50_000.0)
    T = np.full_like(t, 900.0)
    return t, P, T


def test_integrate_returns_expected_keys():
    """Lap integration must return all documented keys."""
    t, P, T = _synthetic_lap()
    out = integrate_wear_lap(t, P, T)
    for key in ['W_mech_kg', 'W_ox_kg', 'W_total_kg',
                'W_total_mg', 'thickness_loss_um',
                'rate_mech_kg_per_s', 'rate_ox_kg_per_s']:
        assert key in out


def test_integrate_components_sum_to_total():
    """Mechanical + oxidative must equal total."""
    t, P, T = _synthetic_lap()
    out = integrate_wear_lap(t, P, T)
    assert abs(out['W_mech_kg'] + out['W_ox_kg'] - out['W_total_kg']) < 1e-20


def test_integrate_realistic_magnitudes():
    """For a Monaco-like lap, total wear should be in mg per lap range."""
    t = np.linspace(0, 72, 540)
    # Brakes active 25% of the time, average power 200 kW
    P = np.where(np.mod(np.arange(540), 4) == 0, 200_000.0, 0.0)
    T = np.full_like(t, 700.0)  # moderate steady temperature
    out = integrate_wear_lap(t, P, T)
    # Total wear per lap per disc: realistic if in mg range
    assert 0.001 < out['W_total_mg'] < 1000.0


def test_integrate_constant_power_constant_T_analytical():
    """For constant inputs, integration must give analytical answer."""
    t = np.linspace(0, 10, 100)
    P_const = 100_000.0
    T_const = 800.0
    P = np.full_like(t, P_const)
    T = np.full_like(t, T_const)
    out = integrate_wear_lap(t, P, T)
    duration = 10.0
    expected_mech = mechanical_wear_rate(P_const) * duration
    expected_ox = oxidative_wear_rate(T_const) * duration
    assert abs(out['W_mech_kg'] - expected_mech) / expected_mech < 1e-3
    assert abs(out['W_ox_kg'] - expected_ox) / expected_ox < 1e-3