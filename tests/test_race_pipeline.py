"""Unit tests for race_pipeline.py — pure functions only.

run_race requires network/cache and is tested by a separate smoke script.
"""

import numpy as np
import pandas as pd
import pytest

from src.analysis.race_pipeline import (
    fuel_mass_at_lap,
    car_mass_at_lap,
    is_clean_racing_lap,
    is_bookend_lap,
)
from src.utils import constants as C


# ─────────────────────────────────────────────────────────────────────
# fuel_mass_at_lap
# ─────────────────────────────────────────────────────────────────────

def test_fuel_at_lap_1_equals_race_start():
    """At lap 1, fuel mass should equal max race-start fuel."""
    m = fuel_mass_at_lap(1, 78)
    expected_start = min(C.FUEL_KG_PER_LAP * 78, C.FUEL_MAX_KG)
    assert abs(m - expected_start) < 1e-9


def test_fuel_at_final_lap_equals_race_end():
    """At final lap, fuel mass should equal race-end reserve."""
    m = fuel_mass_at_lap(78, 78)
    assert abs(m - C.FUEL_END_KG) < 1e-9


def test_fuel_decreases_monotonically():
    """Fuel mass must never increase across laps."""
    masses = [fuel_mass_at_lap(k, 78) for k in range(1, 79)]
    diffs = np.diff(masses)
    assert np.all(diffs <= 0)


def test_fuel_cap_applies_for_long_race():
    """A 100-lap race would compute >70 kg start without the cap; cap should clamp it."""
    m_start = fuel_mass_at_lap(1, 100)
    assert m_start == C.FUEL_MAX_KG


def test_fuel_short_race_no_cap():
    """A 44-lap race (e.g. Spa) should be below the cap."""
    m_start = fuel_mass_at_lap(1, 44)
    expected = C.FUEL_KG_PER_LAP * 44
    assert abs(m_start - expected) < 1e-9
    assert m_start < C.FUEL_MAX_KG


# ─────────────────────────────────────────────────────────────────────
# car_mass_at_lap
# ─────────────────────────────────────────────────────────────────────

def test_car_mass_includes_fuel():
    """Car mass should equal (M_CAR - 5) + fuel_mass_at_lap."""
    m_car = car_mass_at_lap(40, 78)
    expected = (C.M_CAR - 5.0) + fuel_mass_at_lap(40, 78)
    assert abs(m_car - expected) < 1e-9


def test_car_mass_decreases_through_race():
    """Total car mass must decrease monotonically as fuel burns."""
    masses = [car_mass_at_lap(k, 78) for k in range(1, 79)]
    assert masses[0] > masses[-1]
    assert masses[0] - masses[-1] > 50.0  # at least 50 kg of fuel burned


# ─────────────────────────────────────────────────────────────────────
# is_clean_racing_lap
# ─────────────────────────────────────────────────────────────────────

def _fake_lap(lap_number=5, track_status='1', lap_time=pd.Timedelta(seconds=80),
               pit_in=None, pit_out=None):
    return pd.Series({
        'LapNumber': lap_number,
        'TrackStatus': track_status,
        'LapTime': lap_time,
        'PitInTime': pit_in,
        'PitOutTime': pit_out,
    })


def test_clean_lap_returns_true():
    is_clean, reason = is_clean_racing_lap(_fake_lap())
    assert is_clean is True
    assert reason == "clean"


def test_lap_1_is_excluded():
    is_clean, reason = is_clean_racing_lap(_fake_lap(lap_number=1))
    assert is_clean is False
    assert reason == "lap_1_standing_start"


def test_safety_car_lap_is_excluded():
    is_clean, reason = is_clean_racing_lap(_fake_lap(track_status='14'))
    assert is_clean is False
    assert reason.startswith("track_status_")


def test_no_lap_time_is_excluded():
    is_clean, reason = is_clean_racing_lap(_fake_lap(lap_time=pd.NaT))
    assert is_clean is False
    assert reason == "no_lap_time"


# ─────────────────────────────────────────────────────────────────────
# is_bookend_lap
# ─────────────────────────────────────────────────────────────────────

def test_normal_lap_is_not_bookend():
    assert is_bookend_lap(_fake_lap()) is False


def test_in_lap_is_bookend():
    lap = _fake_lap(pit_in=pd.Timedelta(seconds=85))
    assert is_bookend_lap(lap) is True


def test_out_lap_is_bookend():
    lap = _fake_lap(pit_out=pd.Timedelta(seconds=20))
    assert is_bookend_lap(lap) is True