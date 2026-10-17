"""Read-only DC energy estimates from consecutive B1 power reports.

Each accepted interval is bounded; missing reports create an explicit gap.
Positive power is treated as charge and negative as discharge for this
integration; estimates are NOT AC energy or BMS-approved meters.
"""
from datetime import datetime, timezone
import math

class EnergyEstimator:
    def __init__(self, max_gap_seconds=180):
        self.max_gap_seconds=max_gap_seconds
        self.previous=None
        self.charge_dc_kwh=0.0
        self.discharge_dc_kwh=0.0
        self.gaps=0
        self.intervals=0

    def observe(self, timestamp, power_w):
        try:
            t=datetime.fromisoformat(timestamp)
            if t.tzinfo is None or isinstance(power_w,bool):
                return self.report("INVALID_SAMPLE")
            w=float(power_w)
            if not math.isfinite(w):
                return self.report("INVALID_SAMPLE")
            if self.previous is None:
                self.previous=(t,w)
                return self.report("BASELINE")
            old_t,old_w=self.previous
            elapsed=(t-old_t).total_seconds()
            if elapsed<=0:
                return self.report("DUPLICATE_OR_OUT_OF_ORDER")
            self.previous=(t,w)
            if elapsed>self.max_gap_seconds:
                self.gaps+=1
                return self.report("GAP_SKIPPED")
            # Trapezoidal integral of signed DC power split at zero crossing.
            if old_w*w>=0:
                positive=max(0,(old_w+w)/2)*elapsed/3600000
                negative=max(0,-(old_w+w)/2)*elapsed/3600000
            else:
                zero_fraction=abs(old_w)/(abs(old_w)+abs(w))
                first=abs(old_w)*elapsed*zero_fraction/2/3600000
                second=abs(w)*elapsed*(1-zero_fraction)/2/3600000
                positive=(first if old_w>0 else second)
                negative=(first if old_w<0 else second)
            self.charge_dc_kwh+=positive
            self.discharge_dc_kwh+=negative
            self.intervals+=1
            return self.report("ESTIMATED_INTERVAL")
        except (TypeError,ValueError,OverflowError):
            return self.report("INVALID_SAMPLE")

    def report(self,status):
        return {"status":status,"charge_dc_kwh_estimated":round(self.charge_dc_kwh,6),
                "discharge_dc_kwh_estimated":round(self.discharge_dc_kwh,6),
                "accepted_intervals":self.intervals,"skipped_gaps":self.gaps,
                "advisory_only":True,"persistence":"MEMORY_ONLY_RESETS_ON_RESTART",
                "not_ac_meter":True,"no_control_authority":True}
