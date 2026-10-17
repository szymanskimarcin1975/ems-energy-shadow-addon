"""Bounded passive B1 sampling state: deduplicate HA reports, never issue commands."""
from collections import deque
from datetime import datetime
import math

class B1Window:
    def __init__(self, *, max_samples=128, max_span_seconds=3600):
        if max_samples < 2 or max_span_seconds <= 0:
            raise ValueError("invalid_limits")
        self.samples=deque(maxlen=max_samples)
        self.max_span_seconds=max_span_seconds

    def add(self, timestamp, power_w):
        """Only append new, timezone-aware HA report timestamps.

        A value change is not required. A duplicate timestamp is not a second
        physical sample. Nonmonotonic and invalid data is rejected.
        """
        try:
            t=datetime.fromisoformat(timestamp)
            if t.tzinfo is None or isinstance(power_w,bool):
                return "INVALID_SAMPLE"
            w=float(power_w)
            if not math.isfinite(w):
                return "INVALID_SAMPLE"
            if self.samples:
                prev=datetime.fromisoformat(self.samples[-1]["timestamp"])
                gap=(t-prev).total_seconds()
                if gap==0:
                    return "DUPLICATE_REPORT"
                if gap<0:
                    return "OUT_OF_ORDER"
            self.samples.append({"timestamp":timestamp,"watts":w})
            while len(self.samples)>1:
                newest=datetime.fromisoformat(self.samples[-1]["timestamp"])
                oldest=datetime.fromisoformat(self.samples[0]["timestamp"])
                if (newest-oldest).total_seconds()<=self.max_span_seconds:
                    break
                self.samples.popleft()
            return "ACCEPTED"
        except (TypeError,ValueError,OverflowError):
            return "INVALID_SAMPLE"

    def get(self):
        return list(self.samples)
