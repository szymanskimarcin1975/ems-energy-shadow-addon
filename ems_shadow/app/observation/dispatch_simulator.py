"""Pure advisory battery dispatch. Verified input bundle required. No HA client.
All energy is AC-side kWh per slot. SOC is stored DC kWh. No battery export.
This does not schedule heat-pump CO or infer CWU loads from boiler consumption.
"""
import math

def simulate(slots, capacity_kwh, initial_kwh, minimum_kwh, charge_kw, discharge_kw,
             charge_eff, discharge_eff, topology_confirmed=False, step_kwh=.1):
    if topology_confirmed is not True:
        return {'status':'BLOCKED_UNCONFIRMED_BUILDING_LOAD','control_enabled':False}
    values=[capacity_kwh,initial_kwh,minimum_kwh,charge_kw,discharge_kw,charge_eff,discharge_eff,step_kwh]
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in values):raise ValueError('invalid_input')
    if not 0<=minimum_kwh<=initial_kwh<=capacity_kwh or not 0<charge_eff<=1 or not 0<discharge_eff<=1 or min(charge_kw,discharge_kw)<0 or step_kwh<=0:raise ValueError('invalid_constraints')
    # Exact initial energy; reachable states are indexed offsets from it.
    states={0:(0,[])}
    for slot in slots:
        for key in ('load_kwh','pv_kwh','price_pln_kwh','hours'):
            v=slot.get(key)
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0:raise ValueError('missing_or_invalid_slot')
        if slot['hours']<=0:raise ValueError('invalid_duration')
        nxt={}
        for old,(cost,path) in states.items():
            stored=initial_kwh+old*step_kwh
            max_steps=math.ceil(max(charge_kw*charge_eff,discharge_kw/discharge_eff)*slot['hours']/step_kwh)
            for movement in range(-max_steps,max_steps+1):
                delta=movement*step_kwh;after=stored+delta
                if not minimum_kwh-1e-9<=after<=capacity_kwh+1e-9:continue
                charge=max(delta,0)/charge_eff;discharge=max(-delta,0)*discharge_eff
                if charge>charge_kw*slot['hours']+1e-9 or discharge>discharge_kw*slot['hours']+1e-9:continue
                residual=slot['load_kwh']-slot['pv_kwh']
                # Discharge never exceeds on-site demand; no simultaneous charge/discharge.
                if discharge>max(residual,0)+1e-9:continue
                exchange=residual+charge-discharge
                imported=max(exchange,0);exported=max(-exchange,0)
                entry={'import_kwh':imported,'pv_export_kwh':exported,'charge_ac_kwh':charge,
                    'discharge_ac_kwh':discharge,'stored_kwh':after,'cost_pln':imported*slot['price_pln_kwh']}
                key=old+movement;newcost=cost+entry['cost_pln']
                if key not in nxt or newcost<nxt[key][0]:nxt[key]=(newcost,path+[entry])
        if not nxt:raise ValueError('infeasible')
        states=nxt
    cost,path=min(states.values(),key=lambda item:item[0])
    return {'status':'SIMULATION_ONLY','control_enabled':False,'cost_pln':cost,'schedule':path,
        'terminal_value_assumed_zero':True,'step_kwh':step_kwh,
        'limitations':['No forecast confidence calibration','No degradation cost','No CWU or CO control','Not production dispatch']}
