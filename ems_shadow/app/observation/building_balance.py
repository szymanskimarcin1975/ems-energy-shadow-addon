"""Instantaneous AC balance diagnostics, never energy integration or control.
HA timestamps do not prove device synchronisation or meter placement.
"""
from weather_demand import stamp, number

def inspect(ac, meter, captured_at, max_ha_age=240, max_ha_skew=2,
            topology_confirmed=False, device_times_confirmed=False):
    base={'control_enabled':False,'billing_approved':False,'energy_integration_enabled':False,
          'topology_confirmed':topology_confirmed is True,'device_times_confirmed':device_times_confirmed is True}
    try:
        if ac.get('attributes',{}).get('unit_of_measurement')!='W' or meter.get('attributes',{}).get('unit_of_measurement')!='kW':raise ValueError('unit_mismatch')
        a,m=number(ac['state']),number(meter['state'])*1000
        at,mt=stamp(ac['last_reported']),stamp(meter['last_reported'])
        now=stamp(captured_at)
        if not all(0<=(now-t).total_seconds()<=max_ha_age for t in (at,mt)):raise ValueError('stale_or_future_ha_state')
        if abs((at-mt).total_seconds())>max_ha_skew:raise ValueError('ha_skew')
        result=dict(base,candidate_building_w=a-m,ac_w=a,m1_w=m,battery_added_separately=False)
        if a-m<0:return dict(result,status='INCONSISTENT_NEGATIVE_LOAD')
        return dict(result,status='DIAGNOSTIC_ONLY' if not(topology_confirmed is True and device_times_confirmed is True) else 'CONFIRMED_INSTANTANEOUS_ONLY')
    except (ValueError,TypeError,KeyError) as exc:
        return dict(base,status='INVALID_INPUT',reason=str(exc),candidate_building_w=None)
