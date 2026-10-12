"""Prepared offline accounting core. No HA writes or device commands."""
import json
import math
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ZONE = ZoneInfo('Europe/Warsaw')
CATEGORIES = ('building', 'boiler', 'house', 'heatpump')
TARIFFS = ('dolina', 'szczyt_przedpoludniowy', 'szczyt_popoludniowy')

def tariff(t, workday):
    if workday not in ('on', 'off'):
        raise ValueError('workday_unknown')
    if workday == 'off':
        return 'dolina'
    local = t.astimezone(ZONE)
    h = local.hour + local.minute / 60 + local.second / 3600
    summer = 4 <= local.month <= 9
    if 7 <= h < 13:
        return TARIFFS[1]
    if (19 <= h < 22) if summer else (16 <= h < 21):
        return TARIFFS[2]
    return TARIFFS[0]

def number(x):
    if isinstance(x, bool) or x is None:
        raise ValueError('invalid_number')
    n = float(x)
    if not math.isfinite(n):
        raise ValueError('invalid_number')
    return n

def validate(s):
    t = datetime.fromisoformat(s['time'])
    if t.tzinfo is None:
        raise ValueError('timezone_required')
    # Both SolarEdge source timestamps must describe the same completed poll.
    ta = datetime.fromisoformat(s['inverter_time'])
    tg = datetime.fromisoformat(s['grid_time'])
    if abs((ta - tg).total_seconds()) > 2:
        raise ValueError('solaredge_unsynchronized')
    for key in ('inverter_time', 'grid_time', 'boiler_time', 'heatpump_time'):
        age = (t - datetime.fromisoformat(s[key])).total_seconds()
        if not 1 <= age <= 180:
            raise ValueError('unsettled_or_stale_' + key)
    p = number(s['inverter_w']) - 1000 * number(s['grid_kw'])
    boiler = number(s['boiler_w'])
    pump = number(s['heatpump_w'])
    if min(p, boiler, pump) < 0 or boiler > p or pump > boiler:
        raise ValueError('negative_or_inconsistent_power')
    for key in ('boiler_kwh', 'heatpump_kwh'):
        if number(s[key]) < 0:
            raise ValueError('negative_register')
    tariff(t, s['workday'])
    return t, p

def empty():
    return {'schema': 1, 'totals': dict.fromkeys(CATEGORIES, 0.0),
            'tariffs': {c: dict.fromkeys(TARIFFS, 0.0) for c in CATEGORIES},
            'unallocated': dict.fromkeys(CATEGORIES, 0.0), 'previous': None,
            'gaps': 0, 'seconds_observed': 0, 'status': 'not_started',
            'first_time': None, 'last_time': None}

def step(ledger, snapshot):
    """One 5-minute observation window. Reject, never clamp, invalid data.

    Energy is an estimate from sampled building power; raw meter deltas are
    measurements. Missing windows are explicitly excluded, never backfilled.
    """
    try:
        t, p = validate(snapshot)
    except (ValueError, KeyError, TypeError) as exc:
        ledger['previous'] = None
        ledger['gaps'] += 1
        ledger['status'] = str(exc)
        return ledger
    prev = ledger['previous']
    ledger['previous'] = snapshot
    ledger['last_time'] = snapshot['time']
    if ledger['first_time'] is None:
        ledger['first_time'] = snapshot['time']
    if prev is None:
        ledger['status'] = 'baseline_only'
        return ledger
    pt, pp = validate(prev)
    seconds = (t - pt).total_seconds()
    try:
        if not 240 <= seconds <= 360:
            raise ValueError('gap_or_restart')
        building = (p + pp) / 2 * seconds / 3600000
        boiler = number(snapshot['boiler_kwh']) - number(prev['boiler_kwh'])
        pump = number(snapshot['heatpump_kwh']) - number(prev['heatpump_kwh'])
        if boiler < 0 or pump < 0:
            raise ValueError('register_decreased_rebaseline')
        # Delayed or rounded physical registers can violate a short-window balance.
        # No zero substitution and no reclassification as actual consumption.
        if boiler > building or pump > boiler:
            raise ValueError('inconsistent_energy_window')
        deltas = {'building': building, 'boiler': boiler,
                  'house': building - boiler, 'heatpump': pump}
        # A meter increment spanning a tariff/day boundary cannot be assigned
        # exactly without a reading at the boundary. Preserve it as unallocated.
        start = pt.astimezone(ZONE)
        end = (t - timedelta(microseconds=1)).astimezone(ZONE)
        same = (start.date() == end.date() and
                prev['workday'] == snapshot['workday'] and
                tariff(pt, prev['workday']) == tariff(t - timedelta(microseconds=1), snapshot['workday']))
        for c, value in deltas.items():
            ledger['totals'][c] += value
            if same:
                ledger['tariffs'][c][tariff(pt, prev['workday'])] += value
            else:
                ledger['unallocated'][c] += value
        ledger['seconds_observed'] += seconds
        ledger['status'] = 'valid_sampled_window' if same else 'tariff_boundary_unallocated'
    except ValueError as exc:
        ledger['gaps'] += 1
        ledger['status'] = str(exc)
    return ledger

def save(path, data):
    temp = str(path) + '.tmp'
    with open(temp, 'w', encoding='utf8') as f:
        json.dump(data, f, allow_nan=False, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)

def load(path):
    with open(path, encoding='utf8') as f:
        data = json.load(f)
    if data['schema'] != 1:
        raise ValueError('unsupported_schema')
    # A process restart establishes a fresh baseline. No downtime extrapolation.
    data['previous'] = None
    return data
