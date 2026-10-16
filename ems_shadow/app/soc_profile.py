"""Owner planning approval only. Never grants device command permission."""
import json
from pathlib import Path
PROFILE_PATH=Path('/ha_config/ems_shadow/approved_initial_battery_profile_20261016_1154.yaml')
def load_profile():
    try:
        if PROFILE_PATH.stat().st_size>262144:return None
        return json.loads(PROFILE_PATH.read_text())
    except (OSError,ValueError):return None

def planning_policy(profile):
    bounds=profile.get('soc_operating_bounds',{}) if isinstance(profile,dict) else {}
    lo,hi=bounds.get('minimum'),bounds.get('maximum')
    approved=(bounds.get('owner_approved') is True and type(lo) in (int,float) and type(hi) in (int,float) and 0<=lo<hi<=100)
    return {'soc_min':lo if approved else None,'soc_max':hi if approved else None,'owner_approved':approved,'scope':'planning_only','bms_safety_confirmed':False}

