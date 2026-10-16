"""Advisory weather-demand model. No API calls, device commands or legacy DB access."""
from datetime import datetime, timezone
from statistics import median
import math

def stamp(value):
    if not isinstance(value, str):
        raise ValueError('timestamp_required')
    value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        raise ValueError('timezone_required')
    return value.astimezone(timezone.utc)

def number(value):
    if isinstance(value, bool):
        raise ValueError('invalid_number')
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('invalid_number')
    return value

def local_temperature(state, entity, captured, max_age=900):
    try:
        if state.get('entity_id') != entity or state.get('attributes', {}).get('unit_of_measurement') != '°C':
            raise ValueError('wrong_source_or_unit')
        value = number(state.get('state'))
        age = (stamp(captured) - stamp(state.get('last_reported'))).total_seconds()
        if not 0 <= age <= max_age:
            raise ValueError('stale_or_future')
        if not -60 <= value <= 60:
            raise ValueError('outside_screening_range')
        return {'temperature_c': value, 'status': 'valid_ha_observation',
                'ha_reported_at': state['last_reported'], 'captured_at': captured,
                'device_measured_at': None}
    except (ValueError, TypeError, KeyError):
        return {'temperature_c': None, 'status': 'invalid_or_missing'}

def forecast_temperature(rows, issued_at, target_at, source, max_age=7200):
    now, target = stamp(issued_at), stamp(target_at)
    if target < now:
        raise ValueError('past_target')
    eligible = []
    for row in rows:
        try:
            retrieved = stamp(row['retrieved_at'])
            if row['source'] != source or stamp(row['valid_for']) != target:
                continue
            if not 0 <= (now - retrieved).total_seconds() <= max_age:
                continue
            if row.get('issued_at') and stamp(row['issued_at']) > retrieved:
                continue
            value = number(row['temperature_c'])
            if not -60 <= value <= 60:
                continue
            eligible.append((retrieved, value))
        except (ValueError, TypeError, KeyError):
            continue
    return max(eligible)[1] if eligible else None

def predict(rows, issued_at, slot, day_type, temperature, target='boiler', min_days=7):
    """Temperature neighbours; no extrapolation, no zero filling, no CO attribution.

    Training rows must be independently approved complete energy intervals with a
    co-temporal, quality-approved local temperature. Acquisition is a separate gate.
    """
    now = stamp(issued_at)
    valid = []
    days = set()
    for row in rows:
        try:
            if (row['target'] != target or row['slot'] != slot or row['day_type'] != day_type
                    or row['quality_approved'] is not True or row['coverage'] != 1
                    or row['temperature_quality'] != 'approved'
                    or stamp(row['end']) >= now or stamp(row['available_at']) > now):
                continue
            if stamp(row['start']) >= stamp(row['end']):
                continue
            kwh, temp = number(row['kwh']), number(row['temperature_c'])
            if kwh < 0 or not -60 <= temp <= 60:
                continue
            key = row['local_day']
            if key in days:
                raise RuntimeError('duplicate_training_slot')
            days.add(key)
            valid.append((temp, kwh, key))
        except (ValueError, TypeError, KeyError):
            continue
    base = {'target': target, 'training_days': len(days), 'control_enabled': False,
            'prediction_kwh': None, 'temperature_used': False}
    if len(days) < min_days:
        return dict(base, status='insufficient_data')
    fallback = median(x[1] for x in valid)
    try:
        temp = number(temperature)
    except (ValueError, TypeError):
        return dict(base, status='baseline_without_temperature', prediction_kwh=fallback)
    if not min(x[0] for x in valid) <= temp <= max(x[0] for x in valid):
        return dict(base, status='outside_training_temperature', baseline_kwh=fallback)
    nearest = sorted(valid, key=lambda x: (abs(x[0] - temp), x[2]))[:min_days]
    result = median(x[1] for x in nearest)
    return dict(base, status='advisory_uncalibrated', prediction_kwh=result,
                temperature_used=True, temperature_c=temp,
                empirical_range_kwh=[min(x[1] for x in nearest), max(x[1] for x in nearest)],
                uncertainty_calibrated=False)

def temperature_feature(local, forecast_c, issued_at, target_at):
    """Explicit experimental short-horizon local persistence; never a bias correction.
    Beyond two hours use the separate weather forecast. No learned response claimed.
    """
    lead=(stamp(target_at)-stamp(issued_at)).total_seconds()
    value=None
    try:
        if local.get('status')=='valid_ha_observation' and 0<=lead<=7200 and 0<=(stamp(issued_at)-stamp(local['ha_reported_at'])).total_seconds()<=900:
            v=number(local['temperature_c'])
            if -60<=v<=60:value=v
    except (ValueError,TypeError,KeyError):pass
    if value is not None:
        return {'temperature_c':value,'method':'LOCAL_PERSISTENCE_LEAD_UP_TO_2H_EXPERIMENTAL','local_input_used':True,'forecast_temperature_c':forecast_c,'accuracy_improvement_validated':False}
    try:
        value=number(forecast_c)
        if not -60<=value<=60:value=None
    except (ValueError,TypeError):value=None
    return {'temperature_c':value,'method':'SEPARATE_WEATHER_FORECAST' if value is not None else 'NO_TEMPERATURE_FEATURE','local_input_used':False,'forecast_temperature_c':forecast_c,'accuracy_improvement_validated':False}
