"""Offline candidate: blocking new commands never cancels an active command.

HA write timestamps are transport freshness only, not device measurement clocks.
Missing evidence fails closed. No actuator or network operations exist here.
"""
import math
from datetime import datetime

REQUIRED = {'m1_power': 'kW', 'b1_power': 'W', 'soc': '%'}

def snapshot(ha, sources, now):
    """Read current HA timestamps atomically. No actuator services."""
    try:
        if set(sources) != set(REQUIRED) or len(set(sources.values())) != 3:
            return 'TELEMETRY_SOURCES_UNCONFIRMED'
        raw = ha.current_states(sources.values())
        rows = {role: raw[entity] for role, entity in sources.items()}
        return evaluate(rows, now, communication_ok=True, inverter_unambiguous=True)
    except Exception:
        return 'TELEMETRY_READ_UNCONFIRMED'

def evaluate(rows, now, *, communication_ok, inverter_unambiguous,
             max_age=180, max_skew=5):
    if communication_ok is not True:
        return 'COMMUNICATION_UNCONFIRMED'
    if inverter_unambiguous is not True:
        return 'INVERTER_STATE_AMBIGUOUS'
    stamps = []
    for role, unit in REQUIRED.items():
        try:
            raw = rows[role]
            if raw.get('attributes', {}).get('unit_of_measurement') != unit:
                return 'TELEMETRY_UNIT_INVALID'
            value = float(raw['state'])
            if not math.isfinite(value) or (role == 'soc' and not 0 <= value <= 100):
                return 'TELEMETRY_VALUE_INVALID'
            stamp = datetime.fromisoformat(raw['last_reported'])
            if stamp.tzinfo is None or not 0 <= (now-stamp).total_seconds() <= max_age:
                return 'HA_TELEMETRY_STALE_OR_FUTURE'
            stamps.append(stamp)
        except (KeyError, TypeError, ValueError):
            return 'TELEMETRY_MISSING_OR_INVALID'
    if (max(stamps)-min(stamps)).total_seconds() > max_skew:
        return 'HA_SNAPSHOT_SKEW'
    return 'HA_TRANSPORT_CHECK_PASSED_NOT_DEVICE_PROOF'
