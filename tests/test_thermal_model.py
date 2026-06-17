"""
Unit tests for thermal_model.py

Most tests use cases with closed-form analytical solutions. Where no
closed form exists, we test physical properties (signs, scaling, monotonicity).
"""

import numpy as np
import pytest
from src.physics.thermal_model import (
    h_eff,
    convective_loss,
    radiative_loss,
    dT_dt,
    build_input_power_per_disc,
    integrate_lap,
)
from src.utils import constants as C


# ─────────────────────────────────────────────────────────────────────
# h_eff
# ─────────────────────────────────────────────────────────────────────

def test_h_eff_at_reference_velocity_equals_h_eff_0():
    """At v = V_REF, the lumped conductance must equal H_EFF_0 exactly."""
    assert abs(h_eff(C.V_REF) - C.H_EFF_0) < 1e-9


def test_h_eff_scales_with_velocity_exponent():
    """Doubling v should multiply h_eff by 2^N_VEL."""
    h_low = h_eff(C.V_REF)
    h_high = h_eff(C.V_REF * 2)
    expected_ratio = 2.0 ** C.N_VEL
    assert abs(h_high / h_low - expected_ratio) < 1e-9


def test_h_eff_zero_speed_is_zero():
    """At v = 0 (or negative), h_eff should be zero (no forced convection)."""
    assert h_eff(0.0) == 0.0
    assert h_eff(-5.0) == 0.0  # guard against negative


# ─────────────────────────────────────────────────────────────────────
# convective_loss and radiative_loss
# ─────────────────────────────────────────────────────────────────────

def test_convective_loss_zero_at_thermal_equilibrium():
    """When T_disc = T_amb, convection is exactly zero."""
    assert convective_loss(300.0, 300.0, 50.0) == 0.0


def test_convective_loss_positive_when_hot():
    """When T_disc > T_amb, convection removes heat (positive = loss)."""
    assert convective_loss(800.0, 300.0, 50.0) > 0


def test_radiative_loss_zero_at_thermal_equilibrium():
    """Radiation is zero when T_disc = T_amb."""
    assert radiative_loss(300.0, 300.0) == 0.0


def test_radiative_loss_scales_with_T_fourth_power():
    """Radiation should grow much faster than T at high temperatures."""
    Q_500 = radiative_loss(500.0, 300.0)
    Q_1000 = radiative_loss(1000.0, 300.0)
    # 1000^4 / 500^4 = 16, but T_amb^4 subtraction shifts this
    # Just check that Q_1000 / Q_500 is much greater than 2 (linear scaling)
    assert Q_1000 / Q_500 > 10.0


def test_radiative_loss_significant_at_high_T():
    """At 1000K disc temp, radiation should be of order kW per disc."""
    Q_rad = radiative_loss(1000.0, 300.0)
    assert 1000.0 < Q_rad < 20000.0  # 1-20 kW per disc is realistic


# ─────────────────────────────────────────────────────────────────────
# dT_dt
# ─────────────────────────────────────────────────────────────────────

def test_dT_dt_pure_heating_rate():
    """With no cooling losses (T = T_amb), dT/dt = P_in / (m × c_p)."""
    P_in = 100_000.0  # 100 kW
    rhs = dT_dt(300.0, 300.0, 0.0, P_in)
    expected = P_in / (C.M_DISC * C.CP_CC)
    assert abs(rhs - expected) < 1e-6


def test_dT_dt_pure_cooling_when_no_input():
    """With no input, hot disc cools (dT/dt < 0)."""
    rhs = dT_dt(800.0, 300.0, 50.0, 0.0)
    assert rhs < 0


# ─────────────────────────────────────────────────────────────────────
# build_input_power_per_disc
# ─────────────────────────────────────────────────────────────────────

def test_build_input_power_uniform_distribution():
    """Energy is correctly distributed uniformly over event duration."""
    t = np.linspace(0, 10, 101)  # 0.1 s steps
    events = [{
        'start_idx': 10,   # t = 1.0 s
        'end_idx': 30,     # t = 3.0 s, duration = 2.0 s
        'E_brake_front_J': 800_000.0,  # 800 kJ total front
    }]
    P = build_input_power_per_disc(t, events)
    # Per disc: 400 kJ / 2 s = 200 kW; populated in [10, 30] inclusive
    assert np.all(P[:10] == 0)
    assert abs(P[15] - 200_000.0) < 1e-3
    assert np.all(P[31:] == 0)


def test_build_input_power_total_energy_preserved():
    """Integrating the power array recovers the per-disc event energy."""
    t = np.linspace(0, 10, 101)
    events = [{
        'start_idx': 10, 'end_idx': 30,
        'E_brake_front_J': 800_000.0,
    }]
    P = build_input_power_per_disc(t, events)
    integrated = np.trapezoid(P, t)
    expected_per_disc = 800_000.0 / 2  # 400 kJ
    assert abs(integrated - expected_per_disc) / expected_per_disc < 0.01


# ─────────────────────────────────────────────────────────────────────
# integrate_lap
# ─────────────────────────────────────────────────────────────────────

def test_integrate_no_input_at_ambient_stays_constant():
    """No input + start at ambient = no change in temperature."""
    t = np.linspace(0, 10, 100)
    v = np.full_like(t, 50.0)
    P = np.zeros_like(t)
    T = integrate_lap(t, v, P, T_amb_K=300.0, T_init_K=300.0)
    assert np.allclose(T, 300.0, atol=1e-6)


def test_integrate_no_input_hot_disc_decays_toward_ambient():
    """Newton's law of cooling: hot disc with no input cools toward ambient."""
    t = np.linspace(0, 60, 600)
    v = np.full_like(t, 50.0)
    P = np.zeros_like(t)
    T = integrate_lap(t, v, P, T_amb_K=300.0, T_init_K=800.0)
    # Temperature must decrease monotonically
    assert np.all(np.diff(T) < 0)
    # After 60 s (>1.5 thermal time constants), should be much closer to T_amb
    assert T[-1] < 500.0


def test_integrate_constant_input_reaches_steady_state():
    """At constant input and zero ambient losses initially, T should rise."""
    t = np.linspace(0, 30, 300)
    v = np.full_like(t, 50.0)
    P = np.full_like(t, 50_000.0)  # 50 kW constant per disc
    T = integrate_lap(t, v, P, T_amb_K=300.0, T_init_K=300.0)
    # Temperature rises (input exceeds losses while T near ambient)
    assert T[-1] > T[0]
    # Sanity: peaks should be physically reasonable (below 2000 K)
    assert T.max() < 2000.0


def test_integrate_realistic_peak_in_range():
    """A realistic Monaco-like power profile should give realistic peak T."""
    t = np.linspace(0, 3, 30)
    v = np.linspace(80, 30, 30)  # decelerating
    P = np.full_like(t, 500_000.0)  # 500 kW per disc — heavy Monaco event
    T = integrate_lap(t, v, P, T_amb_K=300.0, T_init_K=600.0)
    # Should reach hundreds of K above start, but not thousands
    assert 600 < T.max() < 1500