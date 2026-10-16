"""Uncalibrated persistence estimate from actual contiguous register observations.
No synthetic training, temperature coefficient, billing or device commands.
"""
from weather_demand import stamp, number

def baseline(captures, issued_at, max_gap=45, minimum_seconds=900):
    now=stamp(issued_at)
    rows=[]
    for row in captures:
        try:
            t=stamp(row['captured_at']); e=number(row['register_kwh'])
            if t>now: continue
            valid=row['quality']=='valid' and e>=0
            if not valid:
                rows=[];continue
            if rows and (not 0<(t-rows[-1][0]).total_seconds()<=max_gap or e<rows[-1][1]):rows=[]
            rows.append((t,e,row.get('local',{}).get('temperature_c')))
        except (ValueError,TypeError,KeyError):rows=[]
    unavailable={'prediction_kwh':None,'status':'insufficient_contiguous_baseline','control_enabled':False}
    if len(rows)<2 or not 0<=(now-rows[-1][0]).total_seconds()<=max_gap:return unavailable
    seconds=(rows[-1][0]-rows[0][0]).total_seconds()
    if seconds<minimum_seconds:return unavailable
    delta=rows[-1][1]-rows[0][1]
    return dict(prediction_kwh=delta*3600/seconds,status='persistence_baseline_uncalibrated',
        control_enabled=False,temperature_used=False,temperature_response_identified=False,
        observed_seconds=seconds,observed_register_delta_kwh=delta,
        observed_start=rows[0][0].isoformat(),observed_end=rows[-1][0].isoformat(),
        local_temperature_c=rows[-1][2],uncertainty_calibrated=False,
        prediction_interval_kwh=None,valid_for_control=False,
        limitation='Persistence of recent boiler consumption; excludes house load; no inferred CO/CWU split')
