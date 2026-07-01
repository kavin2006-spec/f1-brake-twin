"""
regen_model.py — MGU-K regenerative braking strategy for the rear axle.

Phase 1b chunk 2: greedy power-cap model.

At each telemetry sample where the rear is braking, regenerative braking
absorbs as much power as the MGU-K can handle, up to its 350 kW limit
(2026 regulation). Whatever exceeds the limit is taken by the rear
friction brakes.

This is the simplest model that produces non-trivial behavior. It is
deliberately scoped (see docs/06_phase_1b_chunk_2_scope.md §3.2):
- No battery state of charge tracking (harvest cap doesn't bind on
  available 2026 tracks — verified by scripts/peak_power_check.py)
- No strategic lookahead
- No deployment modeling

The model assumes the MGU-K is always available. Real failure modes
(motor unavailable, battery full, etc.) are out of scope for v1.
"""

import numpy as np
from src.utils import constants as C


# ─────────────────────────────────────────────────────────────────────
# Per-sample power split
# ─────────────────────────────────────────────────────────────────────

def split_rear_brake_power(P_brake_rear_W: np.ndarray,
                            mguk_limit_W: float = None) -> tuple:
    """
    Apply the greedy MGU-K power cap to split rear-axle braking power
    into regen and friction components.

    At each sample:
        P_regen = min(P_brake_rear, MGUK_POWER_LIMIT)
        P_friction = P_brake_rear - P_regen

    Parameters
    ----------
    P_brake_rear_W : array of rear-axle braking power demands (W).
        Each value is the total power the rear brakes (friction + regen
        combined) must absorb at that sample. Should already be non-negative
        and zeroed outside braking events.
    mguk_limit_W : MGU-K instantaneous power limit (W). Defaults to
        the 2026 regulatory cap of 350 kW.

    Returns
    -------
    P_regen_W : array of regen power at each sample (W), bounded by
        mguk_limit_W from above and 0 from below.
    P_friction_rear_W : array of rear friction brake power at each sample
        (W), equal to whatever exceeds the MGU-K cap.

    Both arrays are the same shape as P_brake_rear_W.
    """
    if mguk_limit_W is None:
        mguk_limit_W = C.MGUK_POWER_LIMIT

    # Clip input to non-negative (defensive — caller should already do this)
    P_brake_rear_W = np.maximum(P_brake_rear_W, 0.0)

    # Greedy: regen takes everything up to the cap
    P_regen_W = np.minimum(P_brake_rear_W, mguk_limit_W)

    # Friction takes the overflow
    P_friction_rear_W = P_brake_rear_W - P_regen_W

    return P_regen_W, P_friction_rear_W


# ─────────────────────────────────────────────────────────────────────
# Aggregate diagnostics
# ─────────────────────────────────────────────────────────────────────

def regen_energy_per_event(P_regen_W: np.ndarray, t_s: np.ndarray,
                            events: list) -> np.ndarray:
    """
    Integrate regen power over each braking event to get per-event
    regen energy (J).

    Parameters
    ----------
    P_regen_W : array of regen power at each sample (W)
    t_s : timestamps (s)
    events : list of dicts with 'start_idx' and 'end_idx' (inclusive)

    Returns
    -------
    Array of regen energies (J), one per event.
    """
    out = np.zeros(len(events))
    for i, ev in enumerate(events):
        s, e = ev['start_idx'], ev['end_idx']
        out[i] = np.trapezoid(P_regen_W[s:e + 1], t_s[s:e + 1])
    return out


def regen_fraction_per_event(P_regen_W: np.ndarray,
                              P_friction_rear_W: np.ndarray,
                              t_s: np.ndarray,
                              events: list) -> np.ndarray:
    """
    Compute the fraction of rear-axle braking energy absorbed by regen
    (vs friction) for each event.

    Returns
    -------
    Array of regen fractions in [0, 1], one per event. A value of 1.0
    means the MGU-K absorbed everything (no friction needed); 0.0 would
    mean nothing went to regen (only happens if rear is not braking at all,
    which shouldn't occur in a valid event).
    """
    out = np.zeros(len(events))
    for i, ev in enumerate(events):
        s, e = ev['start_idx'], ev['end_idx']
        E_regen = np.trapezoid(P_regen_W[s:e + 1], t_s[s:e + 1])
        E_friction = np.trapezoid(P_friction_rear_W[s:e + 1], t_s[s:e + 1])
        E_total = E_regen + E_friction
        if E_total > 0:
            out[i] = E_regen / E_total
        else:
            out[i] = 0.0
    return out


def mguk_binding_fraction(P_brake_rear_W: np.ndarray,
                           t_s: np.ndarray,
                           mguk_limit_W: float = None,
                           brake_bool: np.ndarray = None) -> float:
    """
    Fraction of braking time during which the MGU-K power limit is binding.

    A useful diagnostic — answers "how often was the cap actually active?"
    Returns a value in [0, 1].

    If brake_bool is provided, the denominator is the time spent braking;
    otherwise it's the total time.
    """
    if mguk_limit_W is None:
        mguk_limit_W = C.MGUK_POWER_LIMIT

    binding = P_brake_rear_W > mguk_limit_W

    if brake_bool is not None:
        denom = np.trapezoid(brake_bool.astype(float), t_s)
        numer = np.trapezoid((binding & brake_bool).astype(float), t_s)
    else:
        denom = t_s[-1] - t_s[0]
        numer = np.trapezoid(binding.astype(float), t_s)

    if denom <= 0:
        return 0.0
    return numer / denom

"""
split_rear_brake_power is the entire regen model. Three lines of substance — clip, minimum, subtract. Everything else in the module is diagnostics. This is the simplicity the chunk 2 scope promised: the strategy collapses to a clipping operation once the harvest cap is established as non-binding.
The diagnostics are what makes this useful for analysis. regen_fraction_per_event tells us which events were regen-dominated vs friction-dominated. mguk_binding_fraction answers "how often was the cap actually active?" — directly comparable to the 4.6% we predicted from the back-of-envelope diagnostic at Monaco Q.
No event-level energy decomposition needed here. Phase 1a's decompose_braking_event operates at the event-aggregate level and computes E_brake_total. The rear pipeline will call sample-level functions from energy_balance and feed the rear-axle share into split_rear_brake_power. Then the per-event friction energy comes from integrating P_friction_rear over each event window. No new event-aggregation logic needs to live in regen_model.
"""