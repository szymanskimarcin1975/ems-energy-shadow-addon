"""Passive battery B1 counter integrity checks; never sends commands."""
from datetime import datetime
import math

def evaluate(previous, current, *, mean_abs_watts=None, min_elapsed_seconds=300,
             active_power_w=200, energy_tolerance_kwh=0.001):
    """Two ordered snapshots with timestamp, import_kwh and export_kwh.

    mean_abs_watts must represent the WHOLE observation window, not one reading.
    Results are advisory only; neither proof of failure nor control permission.
    """
    try:
        p = datetime.fromisoformat(previous["timestamp"])
        c = datetime.fromisoformat(current["timestamp"])
        if p.tzinfo is None or c.tzinfo is None:
            return {"status":"INVALID_TIMESTAMPS"}
        elapsed = (c-p).total_seconds()
        if elapsed <= 0:
            return {"status":"INVALID_ORDER"}
        deltas = []
        for key in ("import_kwh","export_kwh"):
            a, b = previous[key], current[key]
            if isinstance(a,bool) or isinstance(b,bool):
                return {"status":"INVALID_EVIDENCE"}
            a,b = float(a),float(b)
            if not all(math.isfinite(v) and v >= 0 for v in (a,b)):
                return {"status":"INVALID_EVIDENCE"}
            deltas.append(b-a)
        if min(deltas) < -energy_tolerance_kwh:
            return {"status":"COUNTER_DECREASED","elapsed_seconds":elapsed,"deltas_kwh":deltas}
        if elapsed < min_elapsed_seconds:
            return {"status":"INSUFFICIENT_WINDOW","elapsed_seconds":elapsed}
        if max(abs(d) for d in deltas) <= energy_tolerance_kwh:
            if mean_abs_watts is None:
                return {"status":"STATIONARY_UNCONFIRMED","elapsed_seconds":elapsed}
            watts=float(mean_abs_watts)
            if not math.isfinite(watts) or watts < 0:
                return {"status":"INVALID_POWER_EVIDENCE"}
            return {"status":("STATIONARY_WITH_ACTIVE_POWER" if watts >= active_power_w
                              else "STATIONARY_LOW_POWER"),"elapsed_seconds":elapsed}
        return {"status":"COUNTERS_ADVANCING","elapsed_seconds":elapsed,"deltas_kwh":deltas}
    except (KeyError,TypeError,ValueError,OverflowError):
        return {"status":"INVALID_EVIDENCE"}
