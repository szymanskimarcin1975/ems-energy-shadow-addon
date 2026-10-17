"""Pure passive B1 monitor. HA timestamps are not device measurement times."""
from datetime import datetime
import math
from b1_sample_window import B1Window
from b1_counter_diagnostic import evaluate_with_power_samples

class Monitor:
    def __init__(self):
        self.window=B1Window(max_samples=32,max_span_seconds=1800)
        self.baseline=None

    def observe(self, states):
        """One HA /states snapshot. Never reads network or writes devices."""
        ids=("sensor.solaredge_i1_b1_dc_power",
             "sensor.solaredge_i1_b1_energy_import",
             "sensor.solaredge_i1_b1_energy_export")
        try:
            power,imp,exp=(states[i] for i in ids)
            stamps=[datetime.fromisoformat(v["last_reported"]) for v in (power,imp,exp)]
            if any(t.tzinfo is None for t in stamps) or (max(stamps)-min(stamps)).total_seconds()>5:
                return {"status":"HA_REPORT_SKEW_OR_MISSING","advisory_only":True}
            timestamp=power["last_reported"]
            watts=float(power["state"])
            ci=float(imp["state"]);ce=float(exp["state"])
            if any(not math.isfinite(x) for x in (watts,ci,ce)) or ci<0 or ce<0:
                return {"status":"INVALID_MEASUREMENT","advisory_only":True}
            sample={"timestamp":timestamp,"import_kwh":ci,"export_kwh":ce}
            accepted=self.window.add(timestamp,watts)
            if accepted=="DUPLICATE_REPORT":
                return {"status":"WAITING_FOR_NEW_HA_REPORT","advisory_only":True,
                        "samples":len(self.window.get())}
            if accepted!="ACCEPTED":
                return {"status":accepted,"advisory_only":True}
            if self.baseline is None:
                self.baseline=sample
                return {"status":"BASELINE_CAPTURED","advisory_only":True,"samples":1}
            # Reset baseline after out-of-order counter movement; never hide reset result.
            result=evaluate_with_power_samples(self.baseline,sample,self.window.get())
            result["advisory_only"]=True
            result["samples"]=len(self.window.get())
            if result["status"] in ("COUNTERS_ADVANCING","COUNTER_DECREASED"):
                self.baseline=sample
            return result
        except (KeyError,TypeError,ValueError,OverflowError):
            return {"status":"UNAVAILABLE_OR_INVALID_HA_INPUT","advisory_only":True}
