"""Offline, passive windowed B1 power evidence; no network or control calls."""
from datetime import datetime
import math

def _time(s):
    t=datetime.fromisoformat(s)
    if t.tzinfo is None: raise ValueError("timezone_required")
    return t

def window_mean_abs_power(samples, start, end, *, max_gap_seconds=180):
    """Conservative time-weighted |DC watts|; zero-order hold needs bounded gaps.

    Measurements must include a sample at the beginning and at the end of the
    observation window. Any gap > max_gap_seconds makes evidence unavailable.
    This is a consistency signal, not a battery efficiency estimate.
    """
    try:
        left,right=_time(start),_time(end)
        span=(right-left).total_seconds()
        if span<=0: return None
        points=[]
        for s in samples:
            t=_time(s["timestamp"])
            w=s["watts"]
            if isinstance(w,bool): return None
            w=float(w)
            if not math.isfinite(w): return None
            points.append((t,w))
        if len(points)<2 or points[0][0]!=left or points[-1][0]!=right:
            return None
        total=0.0
        previous=None
        for t,w in points:
            if previous is not None:
                elapsed=(t-previous[0]).total_seconds()
                if elapsed<=0 or elapsed>max_gap_seconds: return None
                total+=abs(previous[1])*elapsed
            previous=(t,w)
        return total/span
    except (KeyError,TypeError,ValueError,OverflowError):
        return None
