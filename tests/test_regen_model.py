"""Unit tests for regen_model.py"""

import numpy as np
import pytest

from src.physics.regen_model import (
    split_rear_brake_power,
    regen_energy_per_event,
    regen_fraction_per_event,
    mguk_binding_fraction,
)
from src.utils import constants as C


# ─────────────────────────────────────────────────────────────────────
# split_rear_brake_power
# ─────────────────────────────────────────────────────────────────────

def test_split_all_below_cap_all_to_regen():
    """If all power is below the cap, all goes to regen, none to friction."""
    P_rear = np.array([100_000.0, 200_000.0, 300_000.0])  # all below 350 kW
    P_regen, P_fric = split_rear_brake_power(P_rear)
    assert np.allclose(P_regen, P_rear)
    assert np.allclose(P_fric, 0.0)


def test_split_all_above_cap_cap_then_friction():
    """If all power is above the cap, regen is exactly the cap, friction takes rest."""
    P_rear = np.array([500_000.0, 600_000.0, 800_000.0])  # all above 350 kW
    P_regen, P_fric = split_rear_brake_power(P_rear)
    assert np.allclose(P_regen, C.MGUK_POWER_LIMIT)
    assert np.allclose(P_fric, P_rear - C.MGUK_POWER_LIMIT)


def test_split_mixed_above_and_below():
    """Mixed samples should each independently hit the right branch."""
    P_rear = np.array([100_000.0, 400_000.0, 250_000.0, 800_000.0])
    P_regen, P_fric = split_rear_brake_power(P_rear)
    # Sample 0: 100 kW, all to regen
    assert P_regen[0] == 100_000.0 and P_fric[0] == 0.0
    # Sample 1: 400 kW, regen capped at 350, friction takes 50
    assert P_regen[1] == C.MGUK_POWER_LIMIT
    assert P_fric[1] == pytest.approx(50_000.0)
    # Sample 2: 250 kW, all regen
    assert P_regen[2] == 250_000.0 and P_fric[2] == 0.0
    # Sample 3: 800 kW, regen 350, friction 450
    assert P_regen[3] == C.MGUK_POWER_LIMIT
    assert P_fric[3] == pytest.approx(450_000.0)


def test_split_conservation():
    """Regen + friction must equal input total at every sample."""
    P_rear = np.array([0.0, 100_000.0, 300_000.0, 350_000.0,
                        400_000.0, 1_000_000.0])
    P_regen, P_fric = split_rear_brake_power(P_rear)
    assert np.allclose(P_regen + P_fric, P_rear)


def test_split_friction_never_negative():
    """Friction power must be non-negative at every sample."""
    P_rear = np.array([0.0, 100.0, 350_000.0, 500_000.0])
    P_regen, P_fric = split_rear_brake_power(P_rear)
    assert np.all(P_fric >= 0)


def test_split_regen_never_exceeds_limit():
    """Regen must never exceed the MGU-K cap."""
    P_rear = np.linspace(0, 2_000_000, 100)
    P_regen, P_fric = split_rear_brake_power(P_rear)
    assert np.all(P_regen <= C.MGUK_POWER_LIMIT + 1e-9)


def test_split_clips_negative_input():
    """Negative input power should be clipped to zero (defensive)."""
    P_rear = np.array([-100.0, -50_000.0, 100_000.0])
    P_regen, P_fric = split_rear_brake_power(P_rear)
    assert P_regen[0] == 0.0 and P_fric[0] == 0.0
    assert P_regen[1] == 0.0 and P_fric[1] == 0.0
    assert P_regen[2] == 100_000.0


def test_split_custom_limit():
    """Caller can override the MGU-K limit (for sensitivity analysis)."""
    P_rear = np.array([200_000.0, 600_000.0])
    P_regen, P_fric = split_rear_brake_power(P_rear, mguk_limit_W=400_000.0)
    assert P_regen[0] == 200_000.0
    assert P_regen[1] == 400_000.0
    assert P_fric[1] == pytest.approx(200_000.0)


# ─────────────────────────────────────────────────────────────────────
# regen_energy_per_event
# ─────────────────────────────────────────────────────────────────────

def test_regen_energy_constant_power_event():
    """Constant regen power × duration → regen energy."""
    t = np.linspace(0, 5, 51)
    P_regen = np.full_like(t, 200_000.0)
    events = [{'start_idx': 10, 'end_idx': 30}]
    E_regen = regen_energy_per_event(P_regen, t, events)
    # Event from t=1.0 to t=3.0 = 2.0 s at 200 kW = 400 kJ
    assert E_regen[0] == pytest.approx(200_000.0 * 2.0, rel=1e-3)


def test_regen_energy_multiple_events():
    """Each event integrated independently."""
    t = np.linspace(0, 10, 101)
    P_regen = np.zeros_like(t)
    P_regen[10:21] = 100_000.0  # event 1: 1 s at 100 kW
    P_regen[40:61] = 200_000.0  # event 2: 2 s at 200 kW
    events = [
        {'start_idx': 10, 'end_idx': 20},
        {'start_idx': 40, 'end_idx': 60},
    ]
    E = regen_energy_per_event(P_regen, t, events)
    assert E[0] == pytest.approx(100_000.0 * 1.0, rel=1e-3)
    assert E[1] == pytest.approx(200_000.0 * 2.0, rel=1e-3)


# ─────────────────────────────────────────────────────────────────────
# regen_fraction_per_event
# ─────────────────────────────────────────────────────────────────────

def test_regen_fraction_all_regen():
    """If only regen is active, fraction must be 1.0."""
    t = np.linspace(0, 5, 51)
    P_regen = np.full_like(t, 200_000.0)
    P_fric = np.zeros_like(t)
    events = [{'start_idx': 10, 'end_idx': 30}]
    f = regen_fraction_per_event(P_regen, P_fric, t, events)
    assert f[0] == pytest.approx(1.0)


def test_regen_fraction_half_each():
    """Equal regen and friction → 0.5."""
    t = np.linspace(0, 5, 51)
    P_regen = np.full_like(t, 100_000.0)
    P_fric = np.full_like(t, 100_000.0)
    events = [{'start_idx': 10, 'end_idx': 30}]
    f = regen_fraction_per_event(P_regen, P_fric, t, events)
    assert f[0] == pytest.approx(0.5)


def test_regen_fraction_bounded():
    """Fraction must stay in [0, 1]."""
    t = np.linspace(0, 5, 51)
    P_regen = np.full_like(t, 350_000.0)
    P_fric = np.full_like(t, 150_000.0)
    events = [{'start_idx': 10, 'end_idx': 30}]
    f = regen_fraction_per_event(P_regen, P_fric, t, events)
    assert 0.0 <= f[0] <= 1.0


# ─────────────────────────────────────────────────────────────────────
# mguk_binding_fraction
# ─────────────────────────────────────────────────────────────────────

def test_binding_zero_when_never_above_limit():
    """If brake power never exceeds cap, binding fraction is zero."""
    t = np.linspace(0, 10, 100)
    P_rear = np.full_like(t, 200_000.0)
    f = mguk_binding_fraction(P_rear, t)
    assert f == 0.0


def test_binding_one_when_always_above_limit():
    """If always above cap, binding fraction is 1.0."""
    t = np.linspace(0, 10, 100)
    P_rear = np.full_like(t, 500_000.0)
    f = mguk_binding_fraction(P_rear, t)
    assert f == pytest.approx(1.0, rel=1e-3)


def test_binding_with_brake_bool():
    """When brake_bool is given, denominator is brake-on time only."""
    t = np.linspace(0, 10, 100)
    P_rear = np.zeros_like(t)
    brake = np.zeros_like(t, dtype=bool)
    # Brake on for samples 30-60, with power above cap for samples 30-45
    brake[30:60] = True
    P_rear[30:60] = 200_000.0  # below cap
    P_rear[30:45] = 500_000.0  # above cap
    f = mguk_binding_fraction(P_rear, t, brake_bool=brake)
    # 15 samples above cap / 30 samples braking ≈ 0.5
    assert f == pytest.approx(0.5, rel=0.05)