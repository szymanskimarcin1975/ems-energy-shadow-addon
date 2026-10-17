"""Passive Zigbee meter freshness classification. Never performs control or restarts."""
from datetime import datetime, timezone
import math

def classify(now_iso, readings, *, max_age_seconds=210):
    """readings maps logical source to {'state': value, 'last_reported': ISO date}.
    HA last_updated is deliberately not a replacement for last_reported.
    """
    now=datetime.fromisoformat(now_iso)
    if now.tzinfo is None:
        raise ValueError("timezone_required")
    details={}
    for name,data in readings.items():
        result={"status":"UNKNOWN","age_seconds":None}
        try:
            if not isinstance(data,dict) or data.get("state") in (None,"unknown","unavailable"):
                raise ValueError("invalid_state")
            stamp=datetime.fromisoformat(data["last_reported"])
            if stamp.tzinfo is None:raise ValueError("timezone_required")
            age=(now-stamp).total_seconds()
            if not math.isfinite(age) or age<1:
                result["status"]="UNSETTLED_OR_FUTURE"
            else:
                result["age_seconds"]=round(age,2)
                result["status"]="STALE" if age>max_age_seconds else "FRESH"
        except (KeyError,TypeError,ValueError,OverflowError):
            result["status"]="UNKNOWN"
        details[name]=result
    return {"status":"ALL_FRESH" if details and all(v["status"]=="FRESH" for v in details.values()) else "DEGRADED_OR_UNCONFIRMED",
            "sources":details,"advisory_only":True,"automatic_restart_permitted":False,
            "control_authority":False}
