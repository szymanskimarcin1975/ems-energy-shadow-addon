"""Gateway-side verification of the existing household plan contract; no planning."""
import hashlib
import json
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path


def stamp(value):
    t = datetime.fromisoformat(value)
    if t.tzinfo is None:
        raise ValueError('PLAN_TIME_INVALID')
    return t.astimezone(timezone.utc)


def approved_request(report, config, request, now):
    try:
        issued, valid = stamp(report['generated_at']), stamp(report['valid_until'])
        if not 0 <= (now - issued).total_seconds() <= 360 or not now < valid <= issued + timedelta(seconds=360):
            raise ValueError('PLAN_EXPIRED')
        if (report.get('status') != 'ADVISORY_HOUSEHOLD_SCHEDULE_READY' or
                report.get('whole_building_schedule_approved') is not True or
                report.get('current_plan_usable_for_simulation') is not True or
                report.get('input_safety', {}).get('current_ha_set_valid') is not True):
            raise ValueError('PLAN_NOT_CONTROL_APPROVED')
        fingerprint = config['expected_fingerprint']
        if not isinstance(fingerprint, str) or len(fingerprint) != 64 or report.get('planning_config_fingerprint') != fingerprint:
            raise ValueError('PLAN_FINGERPRINT_UNCONFIRMED')
        future, scenario = config['future_day_type'], config['pv_scenario']
        if future not in ('workday', 'nonworkday') or scenario not in ('pv_estimate', 'pv_estimate10'):
            raise ValueError('PLAN_SCENARIO_UNCONFIRMED')
        choices = [d for d in report['household_advisory']['decisions'] if d['future_day_type'] == future and d['pv_scenario'] == scenario]
        if len(choices) != 1:
            raise ValueError('PLAN_SCENARIO_AMBIGUOUS')
        active = []; previous = None
        for row in choices[0]['schedule']:
            start = stamp(row['valid_for']); hours = row.get('hours', 1)
            if type(hours) not in (int, float) or not math.isfinite(hours) or not 0 < hours <= 1:
                raise ValueError('PLAN_DURATION_INVALID')
            end = stamp(row['valid_to']) if 'valid_to' in row else start + timedelta(hours=hours)
            if abs((end-start).total_seconds()-hours*3600) > .01 or (previous is not None and previous != start):
                raise ValueError('PLAN_GAP_OR_OVERLAP')
            previous = end
            if start <= now < end:
                active.append((row, start, end, hours))
        if len(active) != 1:
            raise ValueError('PLAN_SLOT_UNCONFIRMED')
        row, start, end, hours = active[0]
        charge, discharge, load, pv = (row[k] for k in ('charge_ac_kwh','discharge_ac_kwh','load_kwh','pv_kwh'))
        if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in (charge,discharge,load,pv)):
            raise ValueError('PLAN_ENERGY_INVALID')
        if charge > 1e-9 and discharge > 1e-9:
            raise ValueError('PLAN_SIMULTANEOUS_DIRECTIONS')
        if discharge > max(load-pv, 0)+1e-8 or max(charge, discharge) <= 1e-9:
            raise ValueError('PLAN_EXPORT_OR_HOLD')
        option = ('Charge from Solar Power' if charge <= max(pv-load,0)+1e-8 else 'Charge from Solar Power and Grid') if charge > 1e-9 else 'Discharge to Minimize Import'
        watts = math.floor(max(charge,discharge)/hours*1000+1e-7)
        epoch = request['owner_epoch']
        identity = dict(hour=start.replace(minute=0,second=0,microsecond=0).isoformat(), option=option,maximum_power_w=watts,epoch=epoch)
        request_id = 'plan_'+hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:48]
        basis = dict(fingerprint=fingerprint,future_day_type=future,pv_scenario=scenario,slot_start=start.isoformat(),slot_end=end.isoformat(),option=option,maximum_power_w=watts,epoch=epoch)
        plan_id = hashlib.sha256(json.dumps(basis,sort_keys=True,allow_nan=False).encode()).hexdigest()
        if request['request_id'] != request_id or request['plan_id'] != plan_id or request['option'] != option or not 0 < request['power_w'] <= watts <= 5000:
            raise ValueError('REQUEST_NOT_CURRENT_PLAN')
        if not now.timestamp() < request['expires_at'] <= min(valid.timestamp(),end.timestamp()):
            raise ValueError('REQUEST_OUTLIVES_PLAN')
    except (KeyError, TypeError, OverflowError):
        raise ValueError('PLAN_INVALID') from None


def read_approved_request(path, config, request, now):
    path = Path(path)
    if path.stat().st_size > 524288:
        raise ValueError('PLAN_TOO_LARGE')
    approved_request(json.loads(path.read_text()), config, request, now)
